"""
p2p_node.py - Peer networking: every peer = TCP server + TCP client.

Server role : accepts incoming connections (one thread per connection).
Client role : connects to other peers by IP address and port.
"""

import ipaddress
import os
import socket
import threading
import uuid

import protocol

DOWNLOAD_DIR = "downloads"


def _close_socket(sock):
    """
    shutdown() first so that a thread blocked in recv()/accept() on this socket
    wakes up and the other side is told the connection is gone; then close().
    """
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        sock.close()
    except OSError:
        pass


class Peer:
    """One connected remote peer."""

    def __init__(self, sock, peer_id, name, address):
        self.sock = sock
        self.peer_id = peer_id
        self.name = name
        self.address = address            # (ip, port) of the TCP connection
        self.send_lock = threading.Lock()  # keeps text/file sends from interleaving

    def label(self):
        return "%s [%s] %s:%s" % (self.name, self.peer_id, self.address[0], self.address[1])


class P2PNode:
    def __init__(self, name, port, on_event, on_peers_changed):
        """
        on_event(kind, text): kind is "system", "message" or "error".
        on_peers_changed(): called whenever the connected peer list changes.
        """
        self.name = name
        self.port = port
        self.peer_id = uuid.uuid4().hex[:8]
        self.on_event = on_event
        self.on_peers_changed = on_peers_changed

        self.server_socket = None
        self.running = False
        self.peers = {}                    # peer_id -> Peer
        self.peers_lock = threading.Lock()

    # ------------------------------------------------------------------ start / stop
    def start(self):
        """Create the TCP server socket and start accepting connections."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind(("0.0.0.0", self.port))
            self.server_socket.listen()
        except OSError:
            self.server_socket.close()
            self.server_socket = None
            raise
        self.running = True
        threading.Thread(target=self._accept_loop, daemon=True).start()
        self.on_event("system", "Peer started: %s [%s] on port %d"
                      % (self.name, self.peer_id, self.port))

    def stop(self):
        """Close the server socket and all peer connections."""
        self.running = False
        if self.server_socket:
            _close_socket(self.server_socket)
            self.server_socket = None
        with self.peers_lock:
            peers = list(self.peers.values())
            self.peers.clear()
        for peer in peers:
            _close_socket(peer.sock)
        self.on_peers_changed()
        self.on_event("system", "Peer stopped")

    # ------------------------------------------------------------------ server role
    def _accept_loop(self):
        while self.running:
            try:
                conn, addr = self.server_socket.accept()
            except OSError:
                break  # server socket closed
            threading.Thread(target=self._handle_incoming, args=(conn, addr),
                             daemon=True).start()

    def _handle_incoming(self, conn, addr):
        """Server side of the handshake: receive HELLO, reply HELLO_ACK."""
        try:
            conn.settimeout(10)
            hello = protocol.recv_message(conn)
            if hello.get("type") != protocol.HELLO:
                raise ValueError("expected hello")
            protocol.send_message(conn, protocol.make_hello_ack(
                self.peer_id, self.name, self.port))
            conn.settimeout(None)
        except (OSError, ValueError, KeyError) as e:
            self.on_event("error", "Incoming handshake failed: %s" % e)
            conn.close()
            return
        peer = self._register(conn, addr, hello)
        if peer:
            self._receive_loop(peer)

    # ------------------------------------------------------------------ client role
    def connect(self, ip, port_text):
        """
        Connect to another peer. Returns True on success.
        Validation errors and network errors are reported through on_event.
        """
        try:
            ipaddress.ip_address(ip.strip())
        except ValueError:
            self.on_event("error", "Invalid IP address: %r" % ip)
            return False
        try:
            port = int(port_text)
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            self.on_event("error", "Invalid port: %r" % port_text)
            return False
        ip = ip.strip()

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(5)
            sock.connect((ip, port))
            protocol.send_message(sock, protocol.make_hello(
                self.peer_id, self.name, self.port))
            ack = protocol.recv_message(sock)
            if ack.get("type") != protocol.HELLO_ACK:
                raise ValueError("expected hello_ack")
            sock.settimeout(None)
        except (OSError, ValueError, KeyError) as e:
            sock.close()
            self.on_event("error", "Connection failed: %s" % e)
            return False

        peer = self._register(sock, (ip, port), ack)
        if not peer:
            return False
        threading.Thread(target=self._receive_loop, args=(peer,), daemon=True).start()
        return True

    # ------------------------------------------------------------------ peer table
    def _register(self, sock, addr, hello):
        peer_id = hello.get("peer_id")
        name = hello.get("peer_name", "?")
        if peer_id == self.peer_id:
            self.on_event("error", "Cannot connect to yourself")
            sock.close()
            return None
        with self.peers_lock:
            if peer_id in self.peers:
                self.on_event("error", "Already connected to %s" % name)
                sock.close()
                return None
            peer = Peer(sock, peer_id, name, addr)
            self.peers[peer_id] = peer
        self.on_event("system", "Connected to %s (%s:%s)" % (name, addr[0], addr[1]))
        self.on_peers_changed()
        return peer

    def _remove(self, peer):
        with self.peers_lock:
            removed = self.peers.pop(peer.peer_id, None) is peer
        _close_socket(peer.sock)
        if removed:
            self.on_event("system", "%s disconnected" % peer.name)
            self.on_peers_changed()

    def get_peers(self):
        with self.peers_lock:
            return list(self.peers.values())

    # ------------------------------------------------------------------ receiving
    def _receive_loop(self, peer):
        try:
            while self.running:
                msg = protocol.recv_message(peer.sock)
                kind = msg.get("type")
                if kind == protocol.TEXT:
                    self.on_event("message", "%s -> You: %s"
                                  % (peer.name, msg.get("message", "")))
                elif kind == protocol.FILE:
                    self._receive_file(peer, msg)
                else:
                    self.on_event("error", "Unknown message type from %s: %r"
                                  % (peer.name, kind))
        except (OSError, ValueError) as e:
            if self.running:
                self.on_event("error", "Connection with %s lost: %s" % (peer.name, e))
        finally:
            self._remove(peer)

    def _receive_file(self, peer, meta):
        """Read exactly `filesize` bytes (in chunks) and save to downloads/."""
        filesize = meta.get("filesize")
        if not isinstance(filesize, int) or filesize < 0:
            raise ValueError("invalid file size: %r" % (filesize,))
        # basename() prevents a malicious name such as ../../x from escaping downloads/
        filename = os.path.basename(str(meta.get("filename", ""))) or "received_file"

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        path = os.path.join(DOWNLOAD_DIR, filename)
        base, ext = os.path.splitext(path)
        n = 1
        while os.path.exists(path):  # do not overwrite existing files
            path = "%s (%d)%s" % (base, n, ext)
            n += 1

        remaining = filesize
        try:
            with open(path, "wb") as f:
                while remaining > 0:
                    chunk = peer.sock.recv(min(protocol.CHUNK_SIZE, remaining))
                    if not chunk:
                        raise ConnectionError("connection closed during file transfer")
                    f.write(chunk)
                    remaining -= len(chunk)
        except Exception:
            if os.path.exists(path):
                os.remove(path)  # remove the incomplete file
            raise
        self.on_event("message", "%s -> You: File received: %s (saved to %s)"
                      % (peer.name, filename, path))

    # ------------------------------------------------------------------ sending
    def _get_peer(self, peer_id):
        with self.peers_lock:
            return self.peers.get(peer_id)

    def send_text(self, peer_id, message):
        peer = self._get_peer(peer_id)
        if not peer:
            self.on_event("error", "Selected peer is not connected")
            return False
        try:
            with peer.send_lock:
                protocol.send_message(peer.sock, protocol.make_text(
                    self.peer_id, self.name, message))
        except OSError as e:
            self.on_event("error", "Send failed: %s" % e)
            self._remove(peer)
            return False
        self.on_event("message", "You -> %s: %s" % (peer.name, message))
        return True

    def send_file(self, peer_id, path):
        peer = self._get_peer(peer_id)
        if not peer:
            self.on_event("error", "Selected peer is not connected")
            return False
        if not os.path.isfile(path):
            self.on_event("error", "File does not exist: %s" % path)
            return False
        try:
            filesize = os.path.getsize(path)
            filename = os.path.basename(path)
            with peer.send_lock:
                protocol.send_message(peer.sock, protocol.make_file(
                    self.peer_id, self.name, filename, filesize))
                with open(path, "rb") as f:
                    while True:
                        chunk = f.read(protocol.CHUNK_SIZE)
                        if not chunk:
                            break
                        peer.sock.sendall(chunk)
        except OSError as e:
            self.on_event("error", "File send failed: %s" % e)
            self._remove(peer)
            return False
        self.on_event("message", "You -> %s: File sent: %s" % (peer.name, filename))
        return True
