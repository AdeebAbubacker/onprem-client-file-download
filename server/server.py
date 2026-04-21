import argparse
import asyncio
import json
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from aiohttp import WSMsgType, web

BASE_DIR = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class PendingTransfer:
    transfer_id: str
    client_id: str
    filename: str
    destination: Path
    expected_size: Optional[int] = None
    done: asyncio.Event = field(default_factory=asyncio.Event)
    error: Optional[str] = None
    bytes_received: int = 0


class DownloadServer:
    def __init__(self) -> None:
        self.clients: Dict[str, web.WebSocketResponse] = {}
        self.pending: Dict[str, PendingTransfer] = {}
        self.client_locks: Dict[str, asyncio.Lock] = {}

    def get_client_lock(self, client_id: str) -> asyncio.Lock:
        if client_id not in self.client_locks:
            self.client_locks[client_id] = asyncio.Lock()
        return self.client_locks[client_id]

    async def websocket_handler(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)

        client_id = None
        try:
            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    continue

                payload = json.loads(msg.data)
                msg_type = payload.get("type")

                if msg_type == "register":
                    client_id = payload["client_id"]
                    self.clients[client_id] = ws
                    await ws.send_json({"type": "registered", "client_id": client_id})
                    print(f"[server] client registered: {client_id}")
                elif msg_type == "pong":
                    # heartbeat message from client
                    pass
                else:
                    print(f"[server] unknown ws message from {client_id}: {payload}")
        finally:
            if client_id and self.clients.get(client_id) is ws:
                self.clients.pop(client_id, None)
                print(f"[server] client disconnected: {client_id}")
        return ws

    async def list_clients(self, request: web.Request) -> web.Response:
        return web.json_response({"clients": sorted(self.clients.keys())})

    async def trigger_download(self, request: web.Request) -> web.Response:
        client_id = request.match_info["client_id"]
        payload = await request.json() if request.can_read_body else {}
        timeout_seconds = int(payload.get("timeout_seconds", 120))
        remote_path = payload.get("remote_path", "$HOME/file_to_download.txt")
        output_name = payload.get("output_name") or f"{client_id}-{Path(remote_path).name}"

        ws = self.clients.get(client_id)
        if ws is None:
            return web.json_response({"error": f"client '{client_id}' is not connected"}, status=404)

        async with self.get_client_lock(client_id):
            transfer_id = secrets.token_hex(16)
            destination = DOWNLOAD_DIR / f"{transfer_id}-{output_name}"
            transfer = PendingTransfer(
                transfer_id=transfer_id,
                client_id=client_id,
                filename=output_name,
                destination=destination,
            )
            self.pending[transfer_id] = transfer

            try:
                await ws.send_json(
                    {
                        "type": "download_request",
                        "transfer_id": transfer_id,
                        "remote_path": remote_path,
                        "upload_url": str(request.url.with_path(f"/uploads/{transfer_id}").with_query({})),
                    }
                )

                try:
                    await asyncio.wait_for(transfer.done.wait(), timeout=timeout_seconds)
                except asyncio.TimeoutError:
                    transfer.error = f"timed out after {timeout_seconds}s waiting for client upload"

                if transfer.error:
                    if destination.exists():
                        destination.unlink(missing_ok=True)
                    return web.json_response({"status": "failed", "error": transfer.error}, status=504)

                return web.json_response(
                    {
                        "status": "completed",
                        "transfer_id": transfer_id,
                        "client_id": client_id,
                        "saved_to": str(destination),
                        "bytes_received": transfer.bytes_received,
                    }
                )
            finally:
                self.pending.pop(transfer_id, None)

    async def upload_stream(self, request: web.Request) -> web.Response:
        transfer_id = request.match_info["transfer_id"]
        transfer = self.pending.get(transfer_id)
        if transfer is None:
            return web.json_response({"error": "unknown or expired transfer id"}, status=404)

        error = request.headers.get("X-Transfer-Error")
        if error:
            transfer.error = error
            transfer.done.set()
            return web.json_response({"status": "error_received"}, status=400)

        expected_size = request.headers.get("X-File-Size")
        if expected_size:
            transfer.expected_size = int(expected_size)

        bytes_received = 0
        try:
            with transfer.destination.open("wb") as f:
                async for chunk in request.content.iter_chunked(1024 * 1024):
                    f.write(chunk)
                    bytes_received += len(chunk)
            transfer.bytes_received = bytes_received
            if transfer.expected_size is not None and bytes_received != transfer.expected_size:
                transfer.error = (
                    f"size mismatch: received {bytes_received} bytes, expected {transfer.expected_size}"
                )
                transfer.destination.unlink(missing_ok=True)
                return web.json_response({"status": "failed", "error": transfer.error}, status=400)

            transfer.done.set()
            return web.json_response({"status": "ok", "bytes_received": bytes_received})
        except Exception as exc:  # pragma: no cover
            transfer.error = str(exc)
            transfer.destination.unlink(missing_ok=True)
            transfer.done.set()
            return web.json_response({"status": "failed", "error": transfer.error}, status=500)
        finally:
            if transfer.done.is_set() is False and transfer.error:
                transfer.done.set()

    def create_app(self) -> web.Application:
        app = web.Application(client_max_size=1024**3)
        app.add_routes(
            [
                web.get("/ws", self.websocket_handler),
                web.get("/clients", self.list_clients),
                web.post("/downloads/{client_id}", self.trigger_download),
                web.put("/uploads/{transfer_id}", self.upload_stream),
            ]
        )
        return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Cloud server for on-prem client file downloads")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    server = DownloadServer()
    web.run_app(server.create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
