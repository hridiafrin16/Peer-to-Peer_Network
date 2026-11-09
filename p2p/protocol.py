"""
protocol.py - Application-level protocol for the P2P network.

Message framing (see assignment section 10.6):

    [4-byte length][JSON payload]

The 4-byte length is a big-endian unsigned integer giving the size of the
JSON payload in bytes. The receiver reads the 4-byte length first and then
reads exactly that many bytes.

Message types:
    hello      - sent by the peer that initiates a connection
    hello_ack  - reply to hello
    text       - a text message
    file       - file metadata (filename, filesize); the raw file bytes
                 follow immediately after this message on the same socket.
"""

import json
import struct

HELLO = "hello"
HELLO_ACK = "hello_ack"
TEXT = "text"
FILE = "file"

HEADER_SIZE = 4
MAX_MESSAGE_SIZE = 1024 * 1024  # a JSON control message is never this large
CHUNK_SIZE = 64 * 1024          # files are sent/received in 64 KB chunks


def make_hello(peer_id, peer_name, port):
    return {"type": HELLO, "peer_id": peer_id, "peer_name": peer_name, "port": port}


def make_hello_ack(peer_id, peer_name, port):
    return {"type": HELLO_ACK, "peer_id": peer_id, "peer_name": peer_name, "port": port}


def make_text(sender_id, sender_name, message):
    return {"type": TEXT, "sender_id": sender_id, "sender_name": sender_name,
            "message": message}


def make_file(sender_id, sender_name, filename, filesize):
    return {"type": FILE, "sender_id": sender_id, "sender_name": sender_name,
            "filename": filename, "filesize": filesize}


def encode_message(message):
    """Convert a dict into [4-byte length][JSON payload]."""
    payload = json.dumps(message).encode("utf-8")
    return struct.pack(">I", len(payload)) + payload


def recv_exact(sock, size):
    """
    Read exactly `size` bytes from the socket.
    A single recv() may return fewer bytes than requested, so loop until done.
    Raises ConnectionError if the peer closes the connection early.
    """
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("connection closed by peer")
        data.extend(chunk)
    return bytes(data)


def send_message(sock, message):
    sock.sendall(encode_message(message))


def recv_message(sock):
    """Read one framed JSON message and return it as a dict."""
    header = recv_exact(sock, HEADER_SIZE)
    (length,) = struct.unpack(">I", header)
    if length == 0 or length > MAX_MESSAGE_SIZE:
        raise ValueError("invalid message length: %d" % length)
    payload = recv_exact(sock, length)
    message = json.loads(payload.decode("utf-8"))
    if not isinstance(message, dict) or "type" not in message:
        raise ValueError("malformed message")
    return message
