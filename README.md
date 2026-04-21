# On-demand file download from private on-premise clients

This project implements a simple, production-friendly pattern for downloading a large file from on-premise clients that are **not reachable from the public internet**.

## Architecture

Because the server cannot dial into a client behind NAT/private networking, the client opens and maintains an **outbound WebSocket connection** to the server.

When the server receives an API call or CLI command to fetch a file:

1. The server sends a `download_request` command over the existing WebSocket.
2. The client reads the local file.
3. The client streams the file back to the server over an HTTP `PUT` request in **1 MB chunks**.
4. The server writes the stream directly to disk without loading the full 100 MB file into memory.

This keeps the design simple, works behind NAT/firewalls, and demonstrates efficient transfer of large files.

## Why this design

- **No inbound access to clients is required**
- **Server-triggered** download is supported through both HTTP API and CLI
- **Streaming** avoids high memory usage on either side
- Works for **multiple connected clients**

---

## Project structure

```text
home_assignment/
├── client/
│   └── client.py
├── server/
│   ├── cli.py
│   └── server.py
├── create_test_file.py
├── downloads/
├── README.md
└── requirements.txt
```

## Requirements

- Python 3.11+
- pip

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run locally

### 1. Start the server

```bash
python server/server.py --host 127.0.0.1 --port 8080
```

### 2. Create a test file for a client

This simulates the file located at `$HOME/file_to_download.txt`.

```bash
mkdir -p /tmp/client1_home
python create_test_file.py /tmp/client1_home/file_to_download.txt --size-mb 100
```

### 3. Start a client

```bash
python client/client.py --client-id client-1 --server-url http://127.0.0.1:8080 --home-override /tmp/client1_home
```

You can start multiple clients with different ids and different home directories.

---

## Trigger downloads

### Option A: CLI

List connected clients:

```bash
python server/cli.py --server-url http://127.0.0.1:8080 list-clients
```

Download from a client:

```bash
python server/cli.py --server-url http://127.0.0.1:8080 download client-1
```

Download using a custom remote path:

```bash
python server/cli.py --server-url http://127.0.0.1:8080 download client-1 --remote-path '$HOME/file_to_download.txt' --output-name restaurant-1.txt
```

### Option B: HTTP API

List clients:

```bash
curl http://127.0.0.1:8080/clients
```

Trigger a download:

```bash
curl -X POST http://127.0.0.1:8080/downloads/client-1 \
  -H 'Content-Type: application/json' \
  -d '{"remote_path":"$HOME/file_to_download.txt","timeout_seconds":120}'
```

On success, the server saves the downloaded file under:

```text
downloads/
```

---

## API summary

### `GET /clients`
Returns currently connected client ids.

### `POST /downloads/{client_id}`
Requests a file from the specified client.

Request body:

```json
{
  "remote_path": "$HOME/file_to_download.txt",
  "output_name": "optional-custom-name.txt",
  "timeout_seconds": 120
}
```

### `PUT /uploads/{transfer_id}`
Internal endpoint used by the client to stream file contents back to the server.

---

## Notes / tradeoffs

This implementation is intentionally compact, but the same pattern can be extended with:

- mutual authentication / mTLS
- encrypted object storage instead of local disk
- resumable uploads
- per-client authorization
- stronger delivery guarantees with a message broker
- checksums for stronger integrity validation

For the assignment, this version demonstrates the core idea cleanly and efficiently.
