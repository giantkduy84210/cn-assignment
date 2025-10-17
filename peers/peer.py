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
    Peer class:
        - Persistent full-duplex TCP connections to other peers
        - P2P server for incoming connections
        - HTTP UI via WeApRous
        - Tracker registration & peer list updates
        - Channels: create/join + auto-connect all members
    """

    def __init__(self, peer_id, ip, p2p_port, http_port,
                tracker_host=DEFAULT_TRACKER_HOST, tracker_port=DEFAULT_TRACKER_PORT):
        self.peer_id = peer_id
        self.ip = ip
        self.p2p_port = p2p_port
        self.http_port = http_port
        self.tracker_host = tracker_host
        self.tracker_port = tracker_port

        self.peers = {}         # peer_id -> {ip, port, channels}
        self.peers_lock = threading.Lock()
        self.channels = set()   # channel names joined
        self.channels_lock = threading.Lock()

        self.inbox = []         # list of messages
        self.inbox_lock = threading.Lock()

        self.connections = {}   # peer_id -> socket
        self.conn_lock = threading.Lock()

        self._stop = threading.Event()
        self.app = WeApRous()

        self.password = "29112005"  # hardcoded password for demo
        self._install_routes()

    # ---------------------------
    # P2P server: accept incoming
    # ---------------------------
    def start_p2p_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.ip, self.p2p_port))
        server.listen(10)
        server.settimeout(1.0)
        print(f"[Peer {self.peer_id}] P2P listening on {self.ip}:{self.p2p_port}")

        def accept_loop():
            while not self._stop.is_set():
                try:
                    conn, addr = server.accept()
                    threading.Thread(target=self._handle_incoming, args=(conn, addr), daemon=True).start()
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"[Peer {self.peer_id}] accept error: {e}")
                    traceback.print_exc()
                    break
            try:
                server.close()
            except:
                pass

        threading.Thread(target=accept_loop, daemon=True).start()

    def _handle_incoming(self, conn, addr):
        """
        Handle incoming connection:
        - first line must be handshake JSON
        - then persistent newline-delimited JSON messages
        """
        buffer = ""
        peer_name = None
        try:
            data = conn.recv(4096)
            if not data:
                conn.close()
                return
            buffer += data.decode('utf-8', errors='ignore')
            if "\n" not in buffer:
                conn.close()
                return
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            hello = json.loads(line)
            if hello.get("type") != "handshake":
                conn.close()
                return
            peer_name = hello.get("from")
            print(f"[Peer {self.peer_id}] Incoming handshake from {peer_name}")

            # store connection if not exist
            with self.conn_lock:
                if peer_name in self.connections:
                    conn.close()
                    return
                self.connections[peer_name] = conn

            # start listen loop
            self._listen_loop(conn, peer_name, buffer)

        except Exception as e:
            print(f"[Peer {self.peer_id}] _handle_incoming error: {e}")
            try:
                conn.close()
            except:
                pass

    def _listen_loop(self, conn, peer_name, initial_buffer=""):
        buffer = initial_buffer
        try:
            while True:
                if "\n" not in buffer:
                    data = conn.recv(4096)
                    if not data:
                        break
                    buffer += data.decode('utf-8', errors='ignore')
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                        sender = payload.get("from")
                        msg = payload.get("message")
                        mtype = payload.get("type", "broadcast")
                        to = payload.get("to")
                    except Exception:
                        sender = None
                        msg = line
                        mtype = "broadcast"
                        to = None
                    ts = time.time()
                    with self.inbox_lock:
                        self.inbox.append({"from": sender, "message": msg, "ts": ts, "type": mtype, "to": to, "read": False})
                    print(f"[Peer {self.peer_id}] recv from {sender}: {msg}")
        except Exception:
            pass
        finally:
            with self.conn_lock:
                if peer_name in self.connections and self.connections[peer_name] is conn:
                    del self.connections[peer_name]
            try:
                conn.close()
            except:
                pass
            print(f"[Peer {self.peer_id}] connection closed {peer_name}")

    # ---------------------------
    # Connect outgoing
    # ---------------------------
    def connect_to_peer(self, target_id):
        with self.conn_lock:
            if target_id in self.connections:
                return True
        with self.peers_lock:
            info = self.peers.get(target_id)
        if not info:
            print(f"[Peer {self.peer_id}] connect_to_peer: no info for {target_id}")
            return False
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((info["ip"], int(info["port"])))
            hello = {"type": "handshake", "from": self.peer_id}
            s.sendall((json.dumps(hello) + "\n").encode('utf-8'))
            with self.conn_lock:
                self.connections[target_id] = s
            threading.Thread(target=self._listen_loop, args=(s, target_id, ""), daemon=True).start()
            print(f"[Peer {self.peer_id}] connected out to {target_id}")
            return True
        except Exception as e:
            print(f"[Peer {self.peer_id}] connect_to_peer error to {target_id}: {e}")
            try:
                s.close()
            except:
                pass
            return False

    def send_to_peer(self, peer_id, message, mtype="direct", to=None):
        with self.conn_lock:
            conn = self.connections.get(peer_id)
        if conn is None:
            # Deny sending if not connected
            print(f"[Peer {self.peer_id}] send_to_peer: not connected to {peer_id}")
            return False
        payload = {"from": self.peer_id, "message": message, "type": mtype}
        if to is not None:
            payload["to"] = to
        try:
            conn.sendall((json.dumps(payload) + "\n").encode('utf-8'))
            return True
        except Exception as e:
            print(f"[Peer {self.peer_id}] send_to_peer fail to {peer_id}: {e}")
            with self.conn_lock:
                if peer_id in self.connections:
                    try:
                        self.connections[peer_id].close()
                    except:
                        pass
                    del self.connections[peer_id]
            return False

    def broadcast(self, message):
        with self.conn_lock:
            keys = list(self.connections.keys())
        for pid in keys:
            if pid == self.peer_id:
                continue
            ok = self.send_to_peer(pid, message, "broadcast", pid)
            if not ok:
                print(f"[Peer {self.peer_id}] broadcast failed to {pid}")

    # ---------------------------
    # Send to channel
    # ---------------------------
    def send_to_channel(self, ch_name, message):
        with self.channels_lock:
            if ch_name not in self.channels:
                print(f"[Peer {self.peer_id}] send_to_channel: not joined {ch_name}")
                return False
        # Lấy danh sách peer trong channel từ self.peers
        with self.peers_lock:
            status, data = self.get_list_from_tracker()
            if status != 200 or not data:
                print(f"[Peer {self.peer_id}] send_to_channel: failed to get list from tracker")
                return False
            channels_data = data.get("channels", {})
            members = channels_data.get(ch_name, [])
            targets = [m for m in members if m != self.peer_id]
        
        if not targets:
            print(f"[Peer {self.peer_id}] send_to_channel: no peers in {ch_name}")
            return False

        ok_all = True
        for pid in targets:
            ok = self.send_to_peer(pid, message, "channel", ch_name)
            if not ok:
                ok_all = False
                print(f"[Peer {self.peer_id}] send_to_channel failed to {pid}")
        
        # Ghi inbox sau khi gửi
        ts = time.time()
        with self.inbox_lock:
            self.inbox.append({"from": self.peer_id, "message": message, "ts": ts, "type": "channel", "channel": ch_name, "to": "all", "read": True})
        
        return ok_all

    # ---------------------------
    # Tracker interactions
    # ---------------------------
    def register_to_tracker(self):
        url = f"http://{self.tracker_host}:{self.tracker_port}/submit-info"
        payload = {"peer_id": self.peer_id, "ip": self.ip, "port": self.p2p_port, "channels": list(self.channels)}
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

    # ---------------------------
    # Tracker interactions
    # ---------------------------

    def join_channel_tracker(self, ch_name):
        """Join a channel via tracker, and auto-connect to all members"""
        url = f"http://{self.tracker_host}:{self.tracker_port}/join-channel"
        payload = {"channel_name": ch_name, "peer_id": self.peer_id}
        try:
            r = requests.post(url, json=payload, timeout=3)
            if r.status_code == 200:
                members = r.json().get("members", [])
                print(f"[Peer {self.peer_id}] Joined channel '{ch_name}' with members: {members}")
                # add to local channels set
                with self.channels_lock:
                    self.channels.add(ch_name)
                # connect to all members in the channel
                for m in members:
                    if m != self.peer_id:
                        self.connect_to_peer(m)
                return True
            else:
                print(f"[Peer {self.peer_id}] join_channel_tracker failed {r.status_code}: {r.text}")
                return False
        except Exception as e:
            print(f"[Peer {self.peer_id}] join_channel_tracker exception: {e}")
            return False

    def create_channel_tracker(self, ch_name):
        """Create a channel via tracker and join it immediately"""
        url = f"http://{self.tracker_host}:{self.tracker_port}/create-channel"
        payload = {"channel_name": ch_name, "owner": self.peer_id}
        try:
            r = requests.post(url, json=payload, timeout=3)
            if r.status_code == 200:
                print(f"[Peer {self.peer_id}] Created channel '{ch_name}'")
                # add to local channels set
                with self.channels_lock:
                    self.channels.add(ch_name)
                return True
            else:
                print(f"[Peer {self.peer_id}] create_channel_tracker failed {r.status_code}: {r.text}")
                return False
        except Exception as e:
            print(f"[Peer {self.peer_id}] create_channel_tracker exception: {e}")
            return False

    def update_peer_list(self):
        """Get latest peer & channel info from tracker and connect to peers in joined channels"""
        url = f"http://{self.tracker_host}:{self.tracker_port}/get-list"
        try:
            r = requests.get(url, timeout=3)
            if r.status_code != 200:
                print(f"[Peer {self.peer_id}] update_peer_list failed: {r.status_code}")
                return
            data = r.json()
            peers_data = data.get("peers", {})
            channels_data = data.get("channels", {})

            # update known peers
            with self.peers_lock:
                self.peers = peers_data

            # auto-connect to peers in channels we joined
            with self.channels_lock:
                for ch in self.channels:
                    members = channels_data.get(ch, [])
                    for m in members:
                        if m != self.peer_id:
                            self.connect_to_peer(m)
        except Exception as e:
            print(f"[Peer {self.peer_id}] update_peer_list exception: {e}")

    # ---------------------------
    # HTTP routes
    # ---------------------------
    def _install_routes(self):
        # serve chat UI and inject peer_id into JS
        @self.app.route('/', methods=["GET"])
        def chat_page(headers="guest", body="anonymous"):
            cookies = headers.get("cookie", "")  # giả sử headers là dict
            if cookies and cookies.get("auth") == "true":
                html = read_html("chat.html")
                # inject peer_id into HTML for client-side display
                html = html.replace('const myName = "Peer";', f'const myName = "{self.peer_id}";')
                return {"status_code": 200, "body": html, "headers": {"Content-Type": "text/html; charset=utf-8"}}
            else:
                return {"body": read_html("unauthorized.html"), "status_code": 401, "headers": {"Content-Type": "text/html"}}

        @self.app.route('/login', methods=['POST'])
        def login(headers, body):
            """
            Handle user login via POST request.
            Expect body as form-urlencoded: username=...&password=...
            """
            print("[SampleApp] Login attempt with body:", body)
            try:
                # Parse form-urlencoded body
                params = dict(pair.split('=', 1) for pair in body.split('&') if '=' in pair)
                username = params.get("username")
                password = params.get("password")
            except Exception:
                username = password = None

            # Kiểm tra credentials
            if username == self.peer_id and password == self.password:
                print("[SampleApp] Login success for", username)
                # Sau khi đăng nhập thành công, chuyển hướng về trang chủ ("/")
                return {
                    "status_code": 302,
                    "headers": {
                        "Set-Cookie": "auth=true; Path=/",
                        "Location": "/"
                    },
                    "body": ""
                }
            else:
                print("[SampleApp] Login failed for", username)
                return {
                    "status_code": 401,
                    "body": read_html("unauthorized.html"),
                    "headers": {"Content-Type": "text/html"}
                }

        @self.app.route('/login', methods=['GET'])
        def login_page(headers, body):
            return {"body": read_html("login.html"), "status_code": 200, "headers": {"Content-Type": "text/html"}}

        @self.app.route('/get_list', methods=["GET"])
        def peers_api(headers, body):
            # Use get_list_from_tracker
            status, data = self.get_list_from_tracker()
            if status == 200:
                return {"status_code": 200, "body": json.dumps(data), "headers": {"Content-Type": "application/json"}}
            else:
                return {"status_code": 500, "body": json.dumps({"error": "Failed to get from tracker"}), "headers": {"Content-Type": "application/json"}}

        @self.app.route('/connect_peer', methods=["POST"])
        def connect_peer_api(headers, body):
            """
            body: {"peer_id": "peer1"}
            """ 
            try:
                data = json.loads(body)
                target_id = data.get("peer_id")
                if not target_id:
                    return {"status_code": 400, "body": json.dumps({"error":"peer_id required"}), "headers":{"Content-Type":"application/json"}}
                ok = self.connect_to_peer(target_id)
                return {"status_code":200 if ok else 500,"body":json.dumps({"result":"ok" if ok else "fail"}),"headers":{"Content-Type":"application/json"}}
            except Exception as e:
                return {"status_code":400,"body":json.dumps({"error": str(e)}),"headers":{"Content-Type":"application/json"}}

        @self.app.route('/send_peer', methods=["POST"])
        def send_peer_api(headers, body):
            """
            Body: {"peer_id": "peer1", "message": "Hello"}
            """
            try:
                data = json.loads(body)
                target = data.get("peer_id")
                msg = data.get("message")
                if not target or not msg:
                    return {"status_code":400,"body":json.dumps({"error":"peer_id/message required"}),"headers":{"Content-Type":"application/json"}}

                # gửi trước
                ok = self.send_to_peer(target, msg, "direct", target)
                if not ok:
                    return {"status_code":500,"body":json.dumps({"error":"failed to send"}),"headers":{"Content-Type":"application/json"}}

                # append inbox sau khi gửi thành công
                ts = time.time()
                with self.inbox_lock:
                    self.inbox.append({"from": self.peer_id,"message":msg,"ts":ts,"type":"direct","to":target, "read": True})

                return {"status_code":200,"body":json.dumps({"result":"ok"}),"headers":{"Content-Type":"application/json"}}
            except Exception as e:
                return {"status_code":400,"body":json.dumps({"error":str(e)}),"headers":{"Content-Type":"application/json"}}


        @self.app.route('/broadcast_peer', methods=["POST"])
        def broadcast_api(headers, body):
            """
            Body: {"message": "Hello all"}
            """
            try:
                j = json.loads(body)
                msg = j.get("message","")
            except Exception:
                msg = body or ""

            ok_all = True
            with self.peers_lock:
                for pid in self.connections.keys():
                    if pid == self.peer_id:
                        continue
                    ok = self.send_to_peer(pid, msg, "broadcast", pid)
                    if not ok:
                        ok_all = False
                        print(f"[Peer {self.peer_id}] broadcast failed to {pid}")

            if not ok_all:
                return {"status_code":500,"body":json.dumps({"error":"broadcast failed to some peers"}),"headers":{"Content-Type":"application/json"}}

            ts = time.time()
            with self.inbox_lock and self.peers_lock:
                for pid in self.connections.keys():
                    if pid == self.peer_id:
                        continue
                    self.inbox.append({"from": self.peer_id,"message":msg,"ts":ts,"type":"broadcast","to":pid, "read": True})

            return {"status_code":200,"body":json.dumps({"result":"ok"}),"headers":{"Content-Type":"application/json"}}

                    
        @self.app.route('/join_channel', methods=["POST"])
        def join_channel(headers, body):
            """
            Body: {"channel": "room1"}
            """
            try:
                data = json.loads(body)
                ch_name = data.get("channel")
                if not ch_name:
                    return {"status_code":400,"body":json.dumps({"error":"channel required"}),"headers":{"Content-Type":"application/json"}}

                ok = self.join_channel_tracker(ch_name)
                return {"status_code":200 if ok else 500,
                        "body": json.dumps({"result":"ok" if ok else "fail"}),
                        "headers": {"Content-Type":"application/json"}}
            except Exception as e:
                return {"status_code":400,"body":json.dumps({"error":str(e)}),"headers":{"Content-Type":"application/json"}}

        @self.app.route('/create_channel', methods=["POST"])
        def create_channel(headers, body):
            """
            Body: {"channel": "room1"}
            """
            try:
                data = json.loads(body)
                ch_name = data.get("channel")
                if not ch_name:
                    return {"status_code":400,"body":json.dumps({"error":"channel required"}),"headers":{"Content-Type":"application/json"}}

                ok = self.create_channel_tracker(ch_name)
                return {"status_code":200 if ok else 500,
                        "body": json.dumps({"result":"ok" if ok else "fail"}),
                        "headers": {"Content-Type":"application/json"}}
            except Exception as e:
                return {"status_code":400,"body":json.dumps({"error":str(e)}),"headers":{"Content-Type":"application/json"}}

        @self.app.route('/send_channel', methods=["POST"])
        def send_channel_api(headers, body):
            """
            Body: {"channel": "room1", "message": "Hello everyone"}
            """
            try:
                data = json.loads(body)
                ch_name = data.get("channel")
                msg = data.get("message")
                if not ch_name or not msg:
                    return {"status_code":400, "body": json.dumps({"error":"channel/message required"}), "headers":{"Content-Type":"application/json"}}

                ok = self.send_to_channel(ch_name, msg)
                return {"status_code":200 if ok else 500,
                        "body": json.dumps({"result":"ok" if ok else "fail"}),
                        "headers":{"Content-Type":"application/json"}}
            except Exception as e:
                return {"status_code":400, "body": json.dumps({"error": str(e)}), "headers":{"Content-Type":"application/json"}}

        @self.app.route('/poll', methods=["GET"])
        def poll_api(headers, body):
            with self.inbox_lock:
                msgs = list(self.inbox)
            return {"status_code":200,"body":json.dumps(msgs),"headers":{"Content-Type":"application/json"}}

        @self.app.route('/get_channels', methods=["GET"])
        def get_channels(headers, body):
            with self.channels_lock:
                ch_copy = list(self.channels)
            return {"status_code":200,"body":json.dumps(ch_copy),"headers":{"Content-Type":"application/json"}}

        @self.app.route('/get_connections', methods=["GET"])
        def get_connections(headers, body):
            with self.conn_lock, self.peers_lock, self.channels_lock:
                return {
                    "status_code": 200,
                    "body": json.dumps({
                        "all_peers": self.peers,                   # tất cả peer từ tracker
                        "connections": list(self.connections.keys()), # đã connect
                        "channels": { ch:list(self.get_channel_members(ch)) for ch in self.channels }
                    }),
                    "headers": {"Content-Type": "application/json"}
                }

        @self.app.route('/notifications', methods=["GET"])
        def notifications_api(headers, body):
            with self.inbox_lock:
                new_msgs = [m for m in self.inbox if not m.get("read")]
                # reset trạng thái read
                for m in self.inbox:
                    m["read"] = True
            return {
                "status_code": 200,
                "body": json.dumps(new_msgs),
                "headers": {"Content-Type": "application/json"}
            }

    def get_channel_members(self, ch_name):
        """Lấy members hiện tại từ tracker"""
        status, data = self.get_list_from_tracker()
        if status != 200:
            return []
        channels = data.get("channels", {})
        return channels.get(ch_name, [])
    
    # ---------------------------
    # Run peer
    # ---------------------------
    def run(self):
        self.start_p2p_server()
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

        self.app.prepare_address(self.ip, self.http_port)
        print(f"[Peer {self.peer_id}] HTTP UI on {self.ip}:{self.http_port}")
        self.app.run()

    # ---------------------------
    # Stop peer
    # ---------------------------
    def stop(self):
        self._stop.set()
        with self.conn_lock:
            for s in list(self.connections.values()):
                try:
                    s.close()
                except:
                    pass
            self.connections.clear()
