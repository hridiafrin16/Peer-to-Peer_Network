"""
main.py - Tkinter user interface for the P2P network.

Run with:  python main.py
"""

import queue
import threading
import tkinter as tk
from tkinter import filedialog, ttk

from p2p_node import P2PNode


class App:
    def __init__(self, root):
        self.root = root
        root.title("UAP P2P Network")
        root.geometry("900x600")

        self.node = None
        self.events = queue.Queue()   # worker threads put events here; the UI thread reads them
        self.peer_ids = []            # peer ids in the same order as the listbox rows

        self._build_ui()
        self.root.after(100, self._poll_events)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI layout
    def _build_ui(self):
        # --- My Peer
        f = ttk.LabelFrame(self.root, text="My Peer")
        f.pack(fill="x", padx=6, pady=3)
        ttk.Label(f, text="Name:").grid(row=0, column=0, padx=4, pady=4)
        self.name_var = tk.StringVar(value="Alice")
        self.name_entry = ttk.Entry(f, textvariable=self.name_var, width=16)
        self.name_entry.grid(row=0, column=1)
        ttk.Label(f, text="Port:").grid(row=0, column=2, padx=4)
        self.port_var = tk.StringVar(value="5000")
        self.port_entry = ttk.Entry(f, textvariable=self.port_var, width=8)
        self.port_entry.grid(row=0, column=3)
        self.start_btn = ttk.Button(f, text="Start Peer", command=self.start_peer)
        self.start_btn.grid(row=0, column=4, padx=6)
        self.stop_btn = ttk.Button(f, text="Stop", command=self.stop_peer, state="disabled")
        self.stop_btn.grid(row=0, column=5)
        self.info_label = ttk.Label(f, text="Not started")
        self.info_label.grid(row=1, column=0, columnspan=6, sticky="w", padx=4, pady=2)

        # --- Connect
        f = ttk.LabelFrame(self.root, text="Connect to Another Peer")
        f.pack(fill="x", padx=6, pady=3)
        ttk.Label(f, text="IP:").grid(row=0, column=0, padx=4, pady=4)
        self.ip_var = tk.StringVar(value="127.0.0.1")
        ttk.Entry(f, textvariable=self.ip_var, width=18).grid(row=0, column=1)
        ttk.Label(f, text="Port:").grid(row=0, column=2, padx=4)
        self.rport_var = tk.StringVar(value="5001")
        ttk.Entry(f, textvariable=self.rport_var, width=8).grid(row=0, column=3)
        ttk.Button(f, text="Connect", command=self.connect_peer).grid(row=0, column=4, padx=6)

        # --- Peer list + event log
        mid = ttk.Frame(self.root)
        # mid is packed at the end of this method, so the Send Text / Send File
        # boxes and the status bar below always stay visible on small windows.
        left = ttk.LabelFrame(mid, text="Connected Peers")
        left.pack(side="left", fill="y")
        self.peer_list = tk.Listbox(left, width=34, exportselection=False)
        self.peer_list.pack(fill="both", expand=True, padx=4, pady=4)
        right = ttk.LabelFrame(mid, text="Messages / Events")
        right.pack(side="left", fill="both", expand=True, padx=(6, 0))
        self.log = tk.Text(right, state="disabled", wrap="word")
        scroll = ttk.Scrollbar(right, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log.pack(fill="both", expand=True, padx=4, pady=4)

        # Bottom widgets are packed first (status bar, then file, then text) so
        # they keep their space; the peer list / log fills what is left.
        # --- Status bar
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status_var, relief="sunken",
                  anchor="w").pack(fill="x", side="bottom")

        # --- Send file
        f = ttk.LabelFrame(self.root, text="Send File (select a peer first)")
        f.pack(fill="x", side="bottom", padx=6, pady=3)
        ttk.Label(f, text="Text, image, audio, video, PDF, ZIP, etc.").pack(side="left", padx=4)
        ttk.Button(f, text="Choose File & Send", command=self.send_file).pack(side="right", padx=4, pady=4)

        # --- Send text
        f = ttk.LabelFrame(self.root, text="Send Text (select a peer first)")
        f.pack(fill="x", side="bottom", padx=6, pady=3)
        self.text_var = tk.StringVar()
        entry = ttk.Entry(f, textvariable=self.text_var)
        entry.pack(side="left", fill="x", expand=True, padx=4, pady=4)
        entry.bind("<Return>", lambda e: self.send_text())
        ttk.Button(f, text="Send", command=self.send_text).pack(side="right", padx=4)

        mid.pack(fill="both", expand=True, padx=6, pady=3)

    # ------------------------------------------------------------------ thread-safe callbacks
    def _on_event(self, kind, text):
        self.events.put(("event", kind, text))

    def _on_peers_changed(self):
        self.events.put(("peers", None, None))

    def _poll_events(self):
        try:
            while True:
                what, kind, text = self.events.get_nowait()
                if what == "event":
                    self._log(kind, text)
                else:
                    self._refresh_peers()
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _log(self, kind, text):
        prefix = {"system": "[SYSTEM] ", "error": "[ERROR] "}.get(kind, "")
        self.log.configure(state="normal")
        self.log.insert("end", prefix + text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")
        self.status_var.set(prefix + text)

    def _refresh_peers(self):
        self.peer_list.delete(0, "end")
        self.peer_ids = []
        if self.node:
            for peer in self.node.get_peers():
                self.peer_list.insert("end", peer.label())
                self.peer_ids.append(peer.peer_id)

    # ------------------------------------------------------------------ button handlers
    def start_peer(self):
        name = self.name_var.get().strip()
        if not name:
            self._log("error", "Peer name is required")
            return
        try:
            port = int(self.port_var.get())
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            self._log("error", "Invalid port: %r" % self.port_var.get())
            return
        node = P2PNode(name, port, self._on_event, self._on_peers_changed)
        try:
            node.start()
        except OSError as e:
            self._log("error", "Could not start peer on port %d: %s" % (port, e))
            return
        self.node = node
        self.info_label.config(text="%s | ID: %s | Port: %d" % (name, node.peer_id, port))
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.name_entry.config(state="disabled")
        self.port_entry.config(state="disabled")

    def stop_peer(self):
        if self.node:
            self.node.stop()
            self.node = None
        self.info_label.config(text="Not started")
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.name_entry.config(state="normal")
        self.port_entry.config(state="normal")
        self._refresh_peers()

    def connect_peer(self):
        if not self.node:
            self._log("error", "Start your peer first")
            return
        ip, port = self.ip_var.get(), self.rport_var.get()
        # connecting can block, so do it in a thread to keep the UI responsive
        threading.Thread(target=self.node.connect, args=(ip, port), daemon=True).start()

    def _selected_peer_id(self):
        if not self.node:
            self._log("error", "Start your peer first")
            return None
        sel = self.peer_list.curselection()
        if not sel or sel[0] >= len(self.peer_ids):
            self._log("error", "Select a peer from the list first")
            return None
        return self.peer_ids[sel[0]]

    def send_text(self):
        peer_id = self._selected_peer_id()
        if peer_id is None:
            return
        message = self.text_var.get().strip()
        if not message:
            return
        self.text_var.set("")
        threading.Thread(target=self.node.send_text, args=(peer_id, message),
                         daemon=True).start()

    def send_file(self):
        peer_id = self._selected_peer_id()
        if peer_id is None:
            return
        path = filedialog.askopenfilename(
            title="Choose a file to send",
            filetypes=[("All files", "*.*"),
                       ("Images", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
                       ("PDF", "*.pdf"),
                       ("Video", "*.mp4 *.mkv *.avi *.mov *.webm"),
                       ("Audio", "*.mp3 *.wav *.ogg *.m4a *.flac"),
                       ("ZIP / archives", "*.zip *.rar *.7z"),
                       ("Text", "*.txt *.md *.csv")])
        if not path:
            return
        threading.Thread(target=self.node.send_file, args=(peer_id, path),
                         daemon=True).start()

    def _on_close(self):
        if self.node:
            self.node.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
