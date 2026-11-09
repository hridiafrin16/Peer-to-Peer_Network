This is a Python-based P2P communication and file-sharing application where every running instance acts as both a server and a client. There is no central server.
- Technology: Python, Tkinter, TCP sockets
- Communication: Direct peer-to-peer connection using IP + port
- Features:
  - Connect multiple peers
  - Send text messages
  - Send files (images, videos, PDFs, ZIPs, etc.)
  - Receive files in the downloads/ folder
  - Detect and display connection errors/disconnections
- Main files:
  - main.py → User interface
  - p2p_node.py → Networking and file transfer
  - protocol.py → Message formatting/encoding
- Testing: Run python main.py multiple times using different ports.
- Error handling: Invalid IP/port, refused connections, disconnected peers, missing files, and sending without selecting a peer are handled through the event log.
In one sentence:  
A lightweight decentralized P2P application that enables multiple peers to connect directly and securely exchange text messages and files without relying on a central server.
