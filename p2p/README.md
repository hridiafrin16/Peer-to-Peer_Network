# P2P Network - Communication and File Sharing

CSE 434 - Blockchain & Distributed Security Lab, University of Asia Pacific

## Project Description

A lightweight peer-to-peer application written in Python. Every running copy is
one peer, and every peer is both a TCP server (accepts incoming connections)
and a TCP client (connects to other peers). There is no central server. Peers
connect directly using an IP address and a port number and can then exchange
text messages and files (text, images, audio, video, PDF, ZIP and any other
ordinary file).

## Requirements

- Python 3.9 or later
- Windows, Linux or macOS
- Tkinter (included with the standard Python installer; on some Linux systems
  install it with `sudo apt install python3-tk`)
- No third-party packages (see `requirements.txt`)

## Installation / Setup

1. Install Python 3.9 or later.
2. Extract the project folder.
3. Nothing else to install.

## How to Run

```
python main.py
```

Run it once per peer (open a separate terminal for each peer when testing on
one computer).

## How to Connect Two Peers

1. Peer A: enter a name (e.g. `Alice`) and port (e.g. `5000`), click **Start Peer**.
2. Peer B: enter a name (e.g. `Bob`) and a different port (e.g. `5001` on the
   same computer), click **Start Peer**.
3. Peer B: in "Connect to Another Peer" enter Peer A's IP and port
   (`127.0.0.1` / `5000` on the same computer, or A's LAN IP such as
   `192.168.1.10` on two computers) and click **Connect**.
4. Both peers now show each other in the **Connected Peers** list.

Different peers on the same computer must use different ports, because only one
program can listen on a given port.

To add a third peer (e.g. `Charlie`, port `5002`), start it and connect it to
Alice and to Bob.

## How to Send Text

Select a peer in the **Connected Peers** list, type in the **Send Text** box
and click **Send** (or press Enter).

## How to Transfer Files

Select a peer in the **Connected Peers** list, click **Choose File & Send** and
pick any file. The receiving peer stores it in the `downloads/` folder and the
event log shows `File received: <name>`.

## Project Structure

| File | Responsibility |
|------|----------------|
| `main.py` | Tkinter user interface |
| `p2p_node.py` | Server/client sockets, threads, connections, text and file transfer |
| `protocol.py` | Message framing and encoding/decoding of messages |
| `downloads/` | Received files |

## Protocol Summary

Every message is `[4-byte length][JSON payload]`.

- `hello` / `hello_ack`: handshake carrying `peer_id`, `peer_name`, `port`
- `text`: `sender_id`, `sender_name`, `message`
- `file`: `sender_id`, `sender_name`, `filename`, `filesize`. The raw file bytes
  follow directly after this message; the receiver reads exactly `filesize`
  bytes in 64 KB chunks.

## Error Handling

Invalid IP, invalid port, connection refused, unreachable peer, unexpected
disconnects, missing files, invalid file size and sending without selecting a
peer are all reported in the event log (e.g. `[ERROR] Connection failed: ...`)
without crashing the application.

## Example Screenshots

Add your own screenshots here before submission (Peer 1, Peer 2 and Peer 3
windows), e.g. `screenshots/peer1.png`.
