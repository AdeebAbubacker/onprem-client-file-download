import argparse
import json
import sys
import urllib.error
import urllib.request


def request(method: str, url: str, payload: dict | None = None) -> dict:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code}: {body}")


def main() -> None:
    parser = argparse.ArgumentParser(description="CLI for download server")
    parser.add_argument("--server-url", default="http://127.0.0.1:8080")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-clients", help="List connected clients")

    dl = sub.add_parser("download", help="Trigger a download from a specific client")
    dl.add_argument("client_id")
    dl.add_argument("--remote-path", default="$HOME/file_to_download.txt")
    dl.add_argument("--output-name", default=None)
    dl.add_argument("--timeout-seconds", type=int, default=120)

    args = parser.parse_args()

    base = args.server_url.rstrip("/")
    if args.command == "list-clients":
        result = request("GET", f"{base}/clients")
    else:
        result = request(
            "POST",
            f"{base}/downloads/{args.client_id}",
            {
                "remote_path": args.remote_path,
                "output_name": args.output_name,
                "timeout_seconds": args.timeout_seconds,
            },
        )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
