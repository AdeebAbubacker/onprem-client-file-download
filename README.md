On-Demand File Download from Private On-Premise Clients

A lightweight system that allows a cloud server to download files from on-premise clients behind private networks.

This implementation demonstrates a practical architecture for NAT-restricted environments using persistent outbound connections and efficient streaming.


Overview

Many real-world systems deploy clients inside private networks (restaurants, stores, IoT devices, etc.). These clients are not reachable directly from the public internet.

This project demonstrates a simple pattern where:

- Clients initiate a connection to the server
- The server can trigger file downloads on demand
- Large files are transferred efficiently via streaming

The implementation supports multiple connected clients and server-triggered downloads through both HTTP API and CLI.


Architecture

Because clients are behind NAT or private networking, the server cannot open inbound connections to them.

Instead, each client maintains an outbound WebSocket connection to the server.


                API / CLI
                   |
                   v
              +---------+
              | SERVER  |
              | (Cloud) |
              +---------+
                   ^
                   | WebSocket (persistent)
                   |
      +--------------------------------+
      |        CLIENT (On-Prem)        |
      |  Private Network / Behind NAT  |
      +--------------------------------+


Download flow

1. Server receives a download request via API or CLI.
2. Server sends a "download_request" command to the client over WebSocket.
3. Client reads the requested file locally.
4. Client streams the file back to the server via HTTP PUT.
5. Server writes the stream directly to disk.

Large files are transferred in 1 MB chunks, avoiding high memory usage.


Why this design

This approach demonstrates several real-world system design principles.

Works behind NAT  
Clients initiate connections, so no inbound access is required.

Server-triggered operations  
Downloads can be initiated using an API or CLI.

Efficient streaming  
Large files are streamed instead of fully loaded into memory.

Scalable  
Supports multiple connected clients.


Project Structure

home_assignment/

client/
    client.py

server/
    cli.py
    server.py

create_test_file.py
downloads/
requirements.txt
README.md


Requirements

Python 3.11+
pip

Install dependencies:

pip install -r requirements.txt


Running the System Locally

1. Start the Server

python server/server.py --host 127.0.0.1 --port 8080

The server will start listening on:

http://127.0.0.1:8080


2. Create a Test File

This simulates the file located at:

$HOME/file_to_download.txt

Create a test file:

mkdir -p /tmp/client1_home
python create_test_file.py /tmp/client1_home/file_to_download.txt --size-mb 100

This generates a 100 MB file.


3. Start a Client

python client/client.py \
  --client-id client-1 \
  --server-url http://127.0.0.1:8080 \
  --home-override /tmp/client1_home

You can start multiple clients with different IDs.


Triggering Downloads

Downloads can be triggered using either a CLI tool or the HTTP API.


Option A — CLI

List connected clients:

python server/cli.py --server-url http://127.0.0.1:8080 list-clients


Download a file from a client:

python server/cli.py --server-url http://127.0.0.1:8080 download client-1


Download using a custom path:

python server/cli.py \
  --server-url http://127.0.0.1:8080 \
  download client-1 \
  --remote-path '$HOME/file_to_download.txt' \
  --output-name restaurant-1.txt


Option B — HTTP API

List connected clients:

curl http://127.0.0.1:8080/clients


Trigger a download:

curl -X POST http://127.0.0.1:8080/downloads/client-1 \
  -H "Content-Type: application/json" \
  -d '{"remote_path":"$HOME/file_to_download.txt","timeout_seconds":120}'


Downloaded Files

Successfully downloaded files are stored in:

downloads/


Example:

downloads/transfer_id-client-1-file_to_download.txt


API Summary

GET /clients

Returns currently connected client IDs.

Example response:

{
  "clients": ["client-1", "client-2"]
}


POST /downloads/{client_id}

Requests a file from a client.

Request body:

{
  "remote_path": "$HOME/file_to_download.txt",
  "output_name": "optional-name.txt",
  "timeout_seconds": 120
}


PUT /uploads/{transfer_id}

Internal endpoint used by clients to stream file data back to the server.


Possible Extensions

This implementation intentionally focuses on clarity and simplicity. In production environments, it could be extended with:

- mutual authentication / mTLS
- encrypted object storage instead of local disk
- resumable uploads
- per-client authorization
- checksums for integrity validation
- message broker for stronger delivery guarantees


Summary

This project demonstrates a clean solution for server-triggered file downloads from private network clients using:

- outbound client connections
- WebSockets for control
- streaming uploads for large files
- a simple API + CLI interface

The design works reliably even when clients are not directly accessible from the public internet.
