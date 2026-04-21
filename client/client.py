import argparse
import asyncio
import os
from pathlib import Path

import aiohttp


async def stream_file(path: Path, session: aiohttp.ClientSession, upload_url: str) -> None:
    file_size = path.stat().st_size

    async def file_sender():
        with path.open("rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk

    async with session.put(
        upload_url,
        data=file_sender(),
        headers={
            "Content-Type": "application/octet-stream",
            "X-File-Size": str(file_size),
            "X-File-Name": path.name,
        },
    ) as resp:
        body = await resp.text()
        if resp.status >= 300:
            raise RuntimeError(f"upload failed: {resp.status} {body}")


async def send_error(session: aiohttp.ClientSession, upload_url: str, message: str) -> None:
    async with session.put(upload_url, headers={"X-Transfer-Error": message}) as resp:
        await resp.text()


async def run_client(server_url: str, client_id: str, home_override: str | None = None) -> None:
    connector = aiohttp.TCPConnector(limit=0)
    timeout = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=None)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        ws_url = f"{server_url.rstrip('/')}/ws"
        async with session.ws_connect(ws_url, heartbeat=30) as ws:
            await ws.send_json({"type": "register", "client_id": client_id})
            ack = await ws.receive_json()
            print(f"[client {client_id}] connected: {ack}")

            async for msg in ws:
                if msg.type != aiohttp.WSMsgType.TEXT:
                    continue

                payload = msg.json()
                if payload.get("type") != "download_request":
                    continue

                transfer_id = payload["transfer_id"]
                remote_path = payload["remote_path"]
                upload_url = payload["upload_url"]

                resolved = Path(os.path.expandvars(remote_path))
                if str(resolved).startswith("$HOME"):
                    # fallback if HOME wasn't expanded by env vars
                    resolved = Path(str(resolved).replace("$HOME", os.path.expanduser("~"), 1))
                if home_override and remote_path.startswith("$HOME"):
                    resolved = Path(remote_path.replace("$HOME", home_override, 1))

                print(f"[client {client_id}] transfer {transfer_id}: preparing {resolved}")
                if not resolved.exists():
                    await send_error(session, upload_url, f"file not found: {resolved}")
                    continue

                try:
                    await stream_file(resolved, session, upload_url)
                    print(f"[client {client_id}] transfer {transfer_id}: upload finished")
                except Exception as exc:
                    await send_error(session, upload_url, str(exc))
                    print(f"[client {client_id}] transfer {transfer_id}: failed: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="On-premise client agent")
    parser.add_argument("--server-url", default="http://127.0.0.1:8080")
    parser.add_argument("--client-id", required=True)
    parser.add_argument(
        "--home-override",
        default=None,
        help="Override $HOME for local testing, e.g. /tmp/client1_home",
    )
    args = parser.parse_args()

    asyncio.run(run_client(args.server_url, args.client_id, args.home_override))


if __name__ == "__main__":
    main()
