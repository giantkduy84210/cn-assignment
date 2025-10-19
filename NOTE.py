# peers/peer.py
import socket
import threading
import json
import time
import os
import traceback
import requests

from daemon.weaprous import WeApRous

DEFAULT_TRACKER_HOST = "127.0.0.1"
DEFAULT_TRACKER_PORT = 8000


def read_html(filename):
    base = os.path.join(os.path.dirname(__file__), "..", "www")
    path = os.path.join(base, filename)
    with open(os.path.abspath(path), encoding="utf-8") as f:
        return f.read()


class Peer:
    """
    Peer with:
        - persistent TCP connections to other peers (connection pool)
        - P2P server for accepting incoming persistent connections
        - HTTP UI & REST endpoints via WeApRous
        - periodic register/update with tracker
    """

    def __init__(
        self,
        peer_id,
        ip,
        p2p_port,
        http_port,
        tracker_host=DEFAULT_TRACKER_HOST,
        tracker_port=DEFAULT_TRACKER_PORT,
    ):
        self.peer_id = peer_id
        self.ip = ip
        self.p2p_port = p2p_port
        self.http_port = http_port
        self.tracker_host = tracker_host
        self.tracker_port = tracker_port

        # peer registry from tracker: {peer_id: {"ip":..., "port":...}}
        self.peers = {}
        self.peers_lock = threading.Lock()

        # inbox of received messages
        # each item: {"from":..., "message":..., "ts":..., "type":..., "to":...}
        self.inbox = []
        self.inbox_lock = threading.Lock()

        # persistent outgoing connections: peer_id -> socket
        self.connections = {}
        self.conn_lock = threading.Lock()

        # server listening socket thread
        self._stop = threading.Event()

        # web app
        self.app = WeApRous()
        self._install_routes()

    # ---------------------------
    # P2P server (accept and handle persistent connections)
    # ---------------------------
    def start_p2p_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.ip, self.p2p_port))
        server.listen(10)
        server.settimeout(1.0)
        print(
            f"[Peer {self.peer_id}] P2P server listening on {self.ip}:{self.p2p_port}"
        )

        def accept_loop():
            while not self._stop.is_set():
                try:
                    conn, addr = server.accept()
                    # start a listener thread for this connection
                    threading.Thread(
                        target=self._handle_incoming_connection,
                        args=(conn, addr),
                        daemon=True,
                    ).start()
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"[Peer {self.peer_id}] P2P accept error: {e}")
                    traceback.print_exc()
                    break
            try:
                server.close()
            except:
                pass

        threading.Thread(target=accept_loop, daemon=True).start()

    def _handle_incoming_connection(self, conn, addr):
        """
        Accept a persistent connection from another peer.
        Protocol: newline-delimited JSON messages. Each message is a JSON object.
        """
        peer_addr = f"{addr[0]}:{addr[1]}"
        buffer = ""
        conn.settimeout(None)  # blocking
        try:
            # read loop
            while True:
                data = conn.recv(4096)
                if not data:
                    # peer closed connection
                    # print(f"[Peer {self.peer_id}] incoming connection closed by {peer_addr}")
                    break
                try:
                    chunk = data.decode("utf-8", errors="ignore")
                except Exception:
                    chunk = data.decode(errors="ignore")
                buffer += chunk
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                        sender = payload.get("from")
                        message = payload.get("message")
                        msg_type = payload.get("type", "broadcast")
                        to_peer = payload.get("to", None)
                    except Exception:
                        # if not JSON, treat entire line as message text
                        sender = None
                        message = line
                        msg_type = "broadcast"
                        to_peer = None

                    ts = time.time()
                    with self.inbox_lock:
                        self.inbox.append(
                            {
                                "from": sender,
                                "message": message,
                                "ts": ts,
                                "type": msg_type,
                                "to": to_peer,
                            }
                        )
                    print(
                        f"[Peer {self.peer_id}] Received P2P {msg_type} from {sender} : {message}"
                    )
        except Exception as e:
            # connection error
            # print(f"[Peer {self.peer_id}] incoming connection error from {peer_addr}: {e}")
            pass
        finally:
            try:
                conn.close()
            except:
                pass

    # ---------------------------
    # Connection management (outgoing persistent connections)
    # ---------------------------
    def connect_to_peer(self, target_id):
        """
        Ensure we have a persistent connection to target peer_id.
        Returns True if connected (existing or newly created), False otherwise.
        """
        with self.conn_lock:
            if target_id in self.connections:
                # check socket still alive? naive approach: try sending a zero-length ping
                return True

        with self.peers_lock:
            target_info = self.peers.get(target_id)

        if not target_info:
            print(
                f"[Peer {self.peer_id}] connect_to_peer: target {target_id} info not found"
            )
            return False

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((target_info["ip"], int(target_info["port"])))
            s.settimeout(None)  # blocking after connected
            # register and start listen thread
            with self.conn_lock:
                self.connections[target_id] = s
            threading.Thread(
                target=self._listen_outgoing_connection,
                args=(s, target_id),
                daemon=True,
            ).start()
            print(
                f"[Peer {self.peer_id}] Connected to peer {target_id} at {target_info['ip']}:{target_info['port']}"
            )
            return True
        except Exception as e:
            print(f"[Peer {self.peer_id}] connect_to_peer {target_id} failed: {e}")
            try:
                s.close()
            except:
                pass
            return False

    def _listen_outgoing_connection(self, conn, peer_id):
        """
        Listen on an outgoing connection (we keep it open and read messages from peer).
        Mirror of incoming handling: parse newline-delimited JSON.
        """
        buffer = ""
        try:
            while True:
                data = conn.recv(4096)
                if not data:
                    break
                try:
                    chunk = data.decode("utf-8", errors="ignore")
                except:
                    chunk = data.decode(errors="ignore")
                buffer += chunk
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                        sender = payload.get("from")
                        message = payload.get("message")
                        msg_type = payload.get("type", "broadcast")
                        to_peer = payload.get("to", None)
                    except Exception:
                        sender = None
                        message = line
                        msg_type = "broadcast"
                        to_peer = None
                    ts = time.time()
                    with self.inbox_lock:
                        self.inbox.append(
                            {
                                "from": sender,
                                "message": message,
                                "ts": ts,
                                "type": msg_type,
                                "to": to_peer,
                            }
                        )
                    print(
                        f"[Peer {self.peer_id}] (outgoing-conn) Received from {peer_id}: {message}"
                    )
        except Exception:
            pass
        finally:
            # cleanup
            with self.conn_lock:
                if peer_id in self.connections and self.connections[peer_id] is conn:
                    try:
                        conn.close()
                    except:
                        pass
                    del self.connections[peer_id]
            # print(f"[Peer {self.peer_id}] outgoing connection to {peer_id} closed")

    def send_to_peer(self, peer_id, message, msg_type="direct", to=None):
        """
        Send message to a connected peer (peer_id). If not connected, try to connect.
        Message is JSON with fields: from, message, type, to. Messages terminated by '\n'.
        Returns True if sent, False otherwise.
        """
        with self.conn_lock:
            conn = self.connections.get(peer_id)

        if conn is None:
            ok = self.connect_to_peer(peer_id)
            if not ok:
                return False
            with self.conn_lock:
                conn = self.connections.get(peer_id)

        payload = {"from": self.peer_id, "message": message, "type": msg_type}
        if to is not None:
            payload["to"] = to
        try:
            data = json.dumps(payload) + "\n"
            conn.sendall(data.encode("utf-8"))
            return True
        except Exception as e:
            print(f"[Peer {self.peer_id}] send_to_peer {peer_id} failed: {e}")
            # cleanup broken connection
            with self.conn_lock:
                try:
                    conn.close()
                except:
                    pass
                if peer_id in self.connections:
                    del self.connections[peer_id]
            return False

    def broadcast(self, message):
        """
        Broadcast message to all known peers (attempt persistent send).
        Will try to connect to peers if not already connected.
        """
        with self.peers_lock:
            peers_copy = dict(self.peers)
        for pid in peers_copy:
            if pid == self.peer_id:
                continue
            sent = self.send_to_peer(pid, message, msg_type="broadcast", to="all")
            # best-effort; log failures
            if not sent:
                print(f"[Peer {self.peer_id}] broadcast -> failed to {pid}")

    # ---------------------------
    # Tracker interactions
    # ---------------------------
    def register_to_tracker(self):
        url = f"http://{self.tracker_host}:{self.tracker_port}/submit-info"
        payload = {"peer_id": self.peer_id, "ip": self.ip, "port": self.p2p_port}
        try:
            r = requests.post(url, json=payload, timeout=3)
            print(f"[Peer {self.peer_id}] register_to_tracker -> {r.status_code}")
            return r.status_code, r.text
        except Exception as e:
            print(f"[Peer {self.peer_id}] register_to_tracker failed: {e}")
            return None, str(e)

    def get_list_from_tracker(self):
        url = f"http://{self.tracker_host}:{self.tracker_port}/get-list"
        try:
            r = requests.get(url, timeout=3)
            if r.status_code == 200:
                return 200, r.json()
            else:
                return r.status_code, None
        except Exception as e:
            return None, str(e)

    def update_peer_list(self):
        status, data = self.get_list_from_tracker()
        if status == 200 and isinstance(data, dict):
            with self.peers_lock:
                if data != self.peers:
                    self.peers = data
                    print(
                        f"[Peer {self.peer_id}] updated peers: {list(self.peers.keys())}"
                    )
        else:
            print(f"[Peer {self.peer_id}] get-list status {status} error {data}")

    # ---------------------------
    # HTTP routes (WeApRous)
    # ---------------------------
    def _install_routes(self):
        # serve chat UI and inject peer_id into JS
        @self.app.route("/", methods=["GET"])
        def chat_page(headers="guest", body="anonymous"):
            cookies = headers.get("cookie", "")  # giả sử headers là dict
            if cookies and cookies.get("auth") == "true":
                html = read_html("chat.html")
                # inject peer_id into HTML for client-side display
                html = html.replace(
                    'const myName = "Peer";', f'const myName = "{self.peer_id}";'
                )
                return {
                    "status_code": 200,
                    "body": html,
                    "headers": {"Content-Type": "text/html; charset=utf-8"},
                }
            else:
                return {
                    "body": read_html("unauthorized.html"),
                    "status_code": 401,
                    "headers": {"Content-Type": "text/html"},
                }

        @self.app.route("/login", methods=["POST"])
        def login(headers, body):
            """
            Handle user login via POST request.
            Expect body as form-urlencoded: username=...&password=...
            """
            try:
                # Parse form-urlencoded body
                params = dict(
                    pair.split("=", 1) for pair in body.split("&") if "=" in pair
                )
                username = params.get("username")
                password = params.get("password")
            except Exception:
                username = password = None

            # Kiểm tra credentials
            if username == self.peer_id and password == "29112005":
                print("[SampleApp] Login success for", username)
                # Sau khi đăng nhập thành công, chuyển hướng về trang chủ ("/")
                return {
                    "status_code": 302,
                    "headers": {"Set-Cookie": "auth=true; Path=/", "Location": "/"},
                    "body": "",
                }
            else:
                print("[SampleApp] Login failed for", username)
                return {
                    "status_code": 401,
                    "body": read_html("unauthorized.html"),
                    "headers": {"Content-Type": "text/html"},
                }

        @self.app.route("/login", methods=["GET"])
        def login_page(headers, body):
            return {
                "body": read_html("login.html"),
                "status_code": 200,
                "headers": {"Content-Type": "text/html"},
            }

        # connect to a peer and keep connection
        @self.app.route("/connect-peer", methods=["POST"])
        def connect_peer_api(headers, body):
            try:
                data = json.loads(body)
                target_id = data.get("peer_id")
                if not target_id:
                    return {
                        "status_code": 400,
                        "body": json.dumps({"error": "peer_id required"}),
                        "headers": {"Content-Type": "application/json"},
                    }
                with self.peers_lock:
                    if target_id not in self.peers:
                        return {
                            "status_code": 404,
                            "body": json.dumps({"error": "peer not found"}),
                            "headers": {"Content-Type": "application/json"},
                        }
                ok = self.connect_to_peer(target_id)
                return {
                    "status_code": 200 if ok else 500,
                    "body": json.dumps({"result": "ok" if ok else "fail"}),
                    "headers": {"Content-Type": "application/json"},
                }
            except Exception as e:
                return {
                    "status_code": 400,
                    "body": json.dumps({"error": str(e)}),
                    "headers": {"Content-Type": "application/json"},
                }

        # broadcast (via P2P persistent connections)
        @self.app.route("/broadcast-peer", methods=["POST"])
        def broadcast_api(headers, body):
            try:
                j = json.loads(body)
                msg = j.get("message", "")
            except Exception:
                msg = body or ""
            # push into local inbox (own message)
            ts = time.time()
            with self.inbox_lock:
                self.inbox.append(
                    {
                        "from": self.peer_id,
                        "message": msg,
                        "ts": ts,
                        "type": "broadcast",
                        "to": "all",
                    }
                )
            # send to peers (background)
            threading.Thread(target=self.broadcast, args=(msg,), daemon=True).start()
            return {
                "status_code": 200,
                "body": json.dumps({"result": "ok"}),
                "headers": {"Content-Type": "application/json"},
            }

        # send to a single peer (direct)
        @self.app.route("/send-peer", methods=["POST"])
        def send_to_single_peer(headers, body):
            """
            Body expected: {"peer_id":"peerB", "message":"Hello"}
            """
            try:
                data = json.loads(body)
                target_id = data.get("peer_id")
                msg = data.get("message", "")
                if not target_id:
                    return {
                        "status_code": 400,
                        "body": json.dumps({"error": "peer_id required"}),
                        "headers": {"Content-Type": "application/json"},
                    }
                with self.peers_lock:
                    if target_id not in self.peers:
                        return {
                            "status_code": 404,
                            "body": json.dumps(
                                {"error": f"Peer {target_id} not found"}
                            ),
                            "headers": {"Content-Type": "application/json"},
                        }
                # store locally as outgoing message
                ts = time.time()
                with self.inbox_lock:
                    self.inbox.append(
                        {
                            "from": self.peer_id,
                            "message": msg,
                            "ts": ts,
                            "type": "direct",
                            "to": target_id,
                        }
                    )
                # send in background
                threading.Thread(
                    target=self.send_to_peer,
                    args=(target_id, msg, "direct", target_id),
                    daemon=True,
                ).start()
                return {
                    "status_code": 200,
                    "body": json.dumps({"result": "ok"}),
                    "headers": {"Content-Type": "application/json"},
                }
            except Exception as e:
                return {
                    "status_code": 400,
                    "body": json.dumps({"error": str(e)}),
                    "headers": {"Content-Type": "application/json"},
                }

        # return local peer list
        @self.app.route("/get-list", methods=["GET"])
        def peers_api(headers, body):
            with self.peers_lock:
                peers_copy = dict(self.peers)
            return {
                "status_code": 200,
                "body": json.dumps(peers_copy),
                "headers": {"Content-Type": "application/json"},
            }

        # allow manual submit-info to tracker from this peer (POST)
        @self.app.route("/submit-info", methods=["POST"])
        def submit_info_api(headers, body):
            try:
                data = json.loads(body)
                # override if missing
                peer_id = data.get("peer_id", self.peer_id)
                ip = data.get("ip", self.ip)
                port = data.get("port", self.p2p_port)
                payload = {"peer_id": peer_id, "ip": ip, "port": port}
                url = f"http://{self.tracker_host}:{self.tracker_port}/submit-info"
                r = requests.post(url, json=payload, timeout=3)
                return {
                    "status_code": r.status_code,
                    "body": r.text,
                    "headers": {"Content-Type": "application/json"},
                }
            except Exception as e:
                return {
                    "status_code": 500,
                    "body": json.dumps({"error": str(e)}),
                    "headers": {"Content-Type": "application/json"},
                }

        # poll for messages
        @self.app.route("/poll", methods=["GET"])
        def poll_api(headers, body):
            with self.inbox_lock:
                msgs = list(self.inbox)
                # optionally clear inbox if you want "consume"
                # self.inbox.clear()
            return {
                "status_code": 200,
                "body": json.dumps(msgs),
                "headers": {"Content-Type": "application/json"},
            }

    # ---------------------------
    # Run: start p2p server, tracker loop, and HTTP app
    # ---------------------------
    def run(self):
        # start P2P server (accept incoming persistent connections)
        self.start_p2p_server()

        # tracker loop: register once, then periodically update peer list
        def tracker_loop():
            try:
                self.register_to_tracker()
            except Exception as e:
                print(f"[Peer {self.peer_id}] register_to_tracker error: {e}")
            while True:
                try:
                    self.update_peer_list()
                except Exception as e:
                    print(f"[Peer {self.peer_id}] update_peer_list error: {e}")
                time.sleep(3)

        threading.Thread(target=tracker_loop, daemon=True).start()

        # start http UI
        self.app.prepare_address(self.ip, self.http_port)
        print(f"[Peer {self.peer_id}] Starting HTTP UI on {self.ip}:{self.http_port}")
        self.app.run()

    # ---------------------------
    # Helper for graceful stop (optional)
    # ---------------------------
    def stop(self):
        self._stop.set()
        # close outgoing connections
        with self.conn_lock:
            for s in list(self.connections.values()):
                try:
                    s.close()
                except:
                    pass
            self.connections.clear()
