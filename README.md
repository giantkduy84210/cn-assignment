# Hybrid P2P Chat System — CO3093 / CO3094 Project

This project implements a **hybrid chat system** combining **Client–Server** and **Peer-to-Peer (P2P)** approaches.  
It demonstrates how a lightweight HTTP/REST layer (WeApRous + Tracker + Proxy) and long-lived socket P2P connections can work together to build a chat application.

---

## Table of Contents

- [Architecture & Components](#architecture--components)
- [Prerequisites](#prerequisites)
- [Project layout](#project-layout)
- [How to run (examples)](#how-to-run-examples)
- [APIs / Endpoints](#apis--endpoints)
- [Typical usage / test flow](#typical-usage--test-flow)
- [Design notes & behavior details](#design-notes--behavior-details)
- [Troubleshooting](#troubleshooting)
- [Authors & License](#authors--license)

---

## Architecture & Components

High level:

```
Clients (Browser)  →  Proxy (HTTP reverse-proxy)  →  Backend / Tracker / Peer HTTP
                                   │
                           Tracker (REST API)
                                   │
                        Peers (P2P socket connections)
```

**Main components:**

- **Tracker server** — central REST server that manages peer registration and provides peer lists (`start_tracker.py`).
- **Proxy server** — simple socket-based reverse proxy that forwards HTTP requests to appropriate backends (`start_proxy.py`, `daemon/proxy.py`).
- **Peer nodes** — each peer runs:
  - a small HTTP UI + REST endpoints (WeApRous)
  - a P2P socket server for persistent connections to other peers  
  Implementation: `peers/peer.py` and `start_p2p.py`.

---

## Prerequisites

- Python 3.9+  
- `requests` Python package (used by peers & tracker client code)

Install dependency:

```bash
pip install requests
```

---

## Project layout (example)

```
.
├── daemon/
│   ├── proxy.py
│   ├── weaprous.py
│   ├── httpadapter.py
│   ├── request.py
│   ├── response.py
│   └── dictionary.py
│
├── peers/
│   └── peer.py
│
├── www/                 # static HTML: login.html, chat.html, index.html, unauthorized.html, static/
├── start_tracker.py
├── start_proxy.py
├── start_p2p.py
└── README.md
```

(Your repository may have slightly different names; adjust commands accordingly.)

---

## How to run (examples)

**1) Start the Tracker**

Tracker default: `--server-ip 127.0.0.1`, `--server-port 9000` (example)

```bash
python start_tracker.py --server-ip 127.0.0.1 --server-port 9000
```

**2) Start the Proxy**

Proxy default: `--server-ip 127.0.0.1`, `--server-port 8080`

```bash
python start_proxy.py --server-ip 127.0.0.1 --server-port 8080
```

**3) Start Peer nodes**

Each peer takes `--peer-id`, `--ip`, `--p2p-port` (socket server), `--http-port` (UI + REST)

Examples:

```bash
python start_p2p.py --peer-id Vinh --ip 127.0.0.1 --p2p-port 9001 --http-port 8101
python start_p2p.py --peer-id Duy  --ip 127.0.0.1 --p2p-port 9002 --http-port 8102
python start_p2p.py --peer-id Lan  --ip 127.0.0.1 --p2p-port 9003 --http-port 8103
```

Open the HTTP UI for each peer in browser:

- Peer Vinh UI: `http://127.0.0.1:8101/`
- Peer Duy UI:  `http://127.0.0.1:8102/`

**Note:** If you run the Proxy and want to reach the Tracker via proxy, point your client at `127.0.0.1:8080`. Proxy routing depends on `daemon.proxy` configuration.

---

## APIs / Endpoints (summary)

Tracker / backend endpoints (examples):

- `POST /login`  
  - Body: `application/x-www-form-urlencoded` — `username=...&password=...`  
  - Success: returns index/chat HTML + `Set-Cookie: auth=true` (or redirects).  
  - Failure: returns 401 Unauthorized page.

- `POST /submit-info`  
  - Body: JSON `{"peer_id":"id", "ip":"x.x.x.x", "port": p}`  
  - Registers peer info at tracker (used by peers).

- `GET /get-list`  
  - Returns JSON map of registered peers `{ peer_id: { ip, port }, ... }`.

Peer HTTP endpoints (served by the peer process):

- `GET /` — chat UI (requires cookie `auth=true` if setup enforces)
- `GET /login` — login page (HTML)
- `POST /login` — login form submit (form-urlencoded)
- `POST /connect-peer` — request peer connection (body JSON `{"peer_id":"..."} `)
- `POST /broadcast-peer` — broadcast to all peers (body JSON `{"message":"..."} `)
- `POST /send-peer` — send direct message (body JSON `{"peer_id":"target", "message":"..."} `)
- `GET /poll` — poll for messages (returns JSON list of messages)
- `GET /peers` — peer's local view of tracker-provided peer list

P2P socket protocol (between peers):

- Persistent TCP connections.
- Messages are **newline-delimited JSON** objects, e.g.:
  ```json
  {"from":"Vinh","message":"hello","type":"broadcast"}
  ```
- Each JSON message ends with `\n`. Receivers parse by lines and `json.loads`.

---

## Typical usage / test flow

1. Start tracker:
   ```bash
   python start_tracker.py --server-ip 127.0.0.1 --server-port 9000
   ```

2. Start two peers:
   ```bash
   python start_p2p.py --peer-id Vinh --ip 127.0.0.1 --p2p-port 9001 --http-port 8101
   python start_p2p.py --peer-id Duy  --ip 127.0.0.1 --p2p-port 9002 --http-port 8102
   ```

3. Each peer registers to tracker automatically (or call `POST /submit-info` manually).

4. From Peer Vinh web UI:
   - Open `http://127.0.0.1:8101/`, login if required.
   - Use UI to broadcast or send direct message to `Duy`.
   - The peer server will attempt to establish persistent TCP connection to Duy (using `connect-to-peer`) and then send newline-delimited JSON messages.

5. On Peer Duy UI:
   - Open `http://127.0.0.1:8102/` and poll `/poll` to see incoming messages.

---

## Design notes & behavior details

- **Cookies & login flow**
  - When server sets `Set-Cookie: auth=true`, browsers automatically store it for the origin. To avoid a cookie being present during tests, use a private/incognito window or clear cookies in the browser or use a client tool configured not to store cookies.
  - If you want the server to require cookie-based access, check incoming request headers for `Cookie` and parse it (implementation may provide a case-insensitive headers dict).

- **Persistent connections**
  - Peers maintain **persistent outgoing sockets** in a connection pool keyed by `peer_id`. This reduces connect/close overhead.
  - Incoming connections are accepted and handled in separate threads. Both incoming & outgoing sockets parse newline-delimited JSON messages.

- **Message types**
  - `broadcast` — message to everyone (peers will generally forward or send to all known peers).
  - `direct` — message to a specific peer (payload should include `to` field).

- **Concurrency**
  - Each server socket accept/connection handling runs in its own thread.
  - Shared data structures (peer list, inbox, connection pool) use `threading.Lock` to avoid race conditions.

- **Proxy routing**
  - `daemon.proxy` supports mapping hostnames to backend `host:port`. It can apply simple policies (single, round-robin, random). If `Host:` header is missing, proxy should return an error.

---

## Troubleshooting

- **`ValueError: not enough values to unpack (expected 3, got 2)` when parsing request line**  
  - Means the raw request line couldn't be parsed into `METHOD PATH VERSION`. Ensure the HTTP client sends a proper request line (e.g., `GET /path HTTP/1.1`). Tools or malformed requests (including empty reads) may trigger this. Add guards in `request.extract_request_line()` to return a clear 400/close behavior when parsing fails.

- **Empty / idle connection logs and duplicate connections during form submit**
  - Browsers may open multiple connections (redirects, favicon requests, preflight, etc.). Log raw requests to see what the client is actually sending. Ensure response includes `Content-Length` or `Connection: close` where appropriate; otherwise clients may keep sockets open.

- **Cookie appears when you didn't set it**
  - Remember: if any prior response included `Set-Cookie: auth=true`, the browser stores it. Use a fresh incognito window or clear cookies to test "no-cookie" behavior.

- **FileNotFoundError when reading `www/...`**
  - Use absolute or robust relative path logic (e.g., `os.path.join(os.path.dirname(__file__), '..', 'www', 'login.html')`) so modules can find `www` regardless of current working directory.

- **Proxy: `UnboundLocalError: hostname`**
  - The proxy expects a `Host:` header. Validate and handle the case where `Host:` is missing. Return `400 Bad Request` in that case.

---

## Security / limitations

- This project is educational. The authentication is **not secure** (plain text username/password, no TLS). Do **not** run on untrusted networks.
- Input parsing is fairly permissive; sanitize and validate inputs if extending.
- No rate limiting or DoS protections included.

---

## Authors & License

- Authors: pdnguyen (HCMC University of Technology, VNU-HCM) and course participants (CO3093/CO3094).
- Educational use; please refer to the repository LICENSE or course assignment agreement for permitted usage.
