import json
import argparse
import time
from daemon.weaprous import WeApRous
import threading

app = WeApRous()

# --------------------------
# Global data
# --------------------------
PEERS = {}  # {peer_id: {"ip":..., "port":..., "last_seen":...}}
CHANNELS = {}  # {channel_name: {"owner":..., "members": [peer_id,...]}}
LOCK_PEERS = threading.Lock()
LOCK_CHANNELS = threading.Lock()


@app.route("/login", methods=["POST"])
def login(headers, body):
    """
    Handle user login via POST request.
    Expect body as form-urlencoded: username=...&password=...
    """
    try:
        # Parse form-urlencoded body
        params = dict(pair.split("=", 1)
                      for pair in body.split("&") if "=" in pair)
        username = params.get("username")
        password = params.get("password")
    except Exception:
        username = password = None

    # Check credentials
    if username == "Tracker" and password == "29112005":
        print("[SampleApp] Login success for", username)
        return {
            "status_code": 302,
            "headers": {"Set-Cookie": "auth=true; Path=/", "Location": "/"},
            "body": "",
        }
    else:
        print("[SampleApp] Login failed for", username)
        return {
            "status_code": 401,
            "body": open("www/unauthorized.html").read(),
            "headers": {"Content-Type": "text/html"},
        }


@app.route("/login", methods=["GET"])
def login_page(headers, body):
    return {
        "body": open("www/login.html").read(),
        "status_code": 200,
        "headers": {"Content-Type": "text/html"},
    }


@app.route("/", methods=["GET"])
def index(headers, body):
    cookies = headers.get("cookie", "")
    if cookies and cookies.get("auth") == "true":
        return {
            "body": open("www/tracker.html").read(),
            "status_code": 200,
            "headers": {"Content-Type": "text/html"},
        }
    else:
        return {
            "body": open("www/unauthorized.html").read(),
            "status_code": 401,
            "headers": {"Content-Type": "text/html"},
        }


# --------------------------
# Peer management
# --------------------------
@app.route("/submit-info", methods=["POST"])
def submit_info(headers, body):
    """
    Peer submit its information to the tracker.
    Body: {"peer_id": "peer1", "ip": "127.0.0.1", "port": 9001}

    The tracker prefers the observed IP (from X-Forwarded-For or x-remote-addr)
    over the client-supplied IP, and returns the advertised IP in the response
    so peers can auto-detect their public IP.
    """
    try:
        data = json.loads(body)
        peer_id = data["peer_id"]

        # Prefer observed IP from proxy/connection over client-claimed IP
        # X-Forwarded-For takes precedence (set by proxy), then x-remote-addr (direct connection)
        observed_ip = None
        if isinstance(headers.get("x-forwarded-for"), str):
            # X-Forwarded-For may contain comma-separated IPs; take the first one
            observed_ip = headers.get("x-forwarded-for").split(",")[0].strip()
        elif headers.get("x-remote-addr"):
            observed_ip = headers.get("x-remote-addr")

        # Use observed IP if available, otherwise fall back to client-supplied IP
        ip = observed_ip if observed_ip else data.get("ip", "unknown")
        port = data["port"]

        with LOCK_PEERS:
            if peer_id not in PEERS:
                PEERS[peer_id] = {"ip": ip, "port": port, "last_seen": time.time()}
                print(f"[Tracker] Registered peer {peer_id} at {ip}:{port}")
                return {
                    "status_code": 200,
                    "body": json.dumps({"result": "ok", "advertised_ip": ip}),
                    "headers": {"Content-Type": "application/json"},
                }
            else:
                return {
                    "status_code": 400,
                    "body": json.dumps({"error": "Peer ID already registered"}),
                    "headers": {"Content-Type": "application/json"},
                }
    except Exception as e:
        return {
            "status_code": 400,
            "body": json.dumps({"error": str(e)}),
            "headers": {"Content-Type": "application/json"},
        }


@app.route("/get-list", methods=["GET"])
def get_list(headers, body):
    """Return current peer list and channel membership"""
    with LOCK_PEERS, LOCK_CHANNELS:
        response = {
            "peers": PEERS,
            "channels": {ch: data["members"] for ch, data in CHANNELS.items()},
        }
    return {
        "status_code": 200,
        "body": json.dumps(response),
        "headers": {"Content-Type": "application/json"},
    }


@app.route("/add-list", methods=["POST"])
def add_list(headers, body):
    """Merge multiple peer info into PEERS"""
    try:
        data = json.loads(body)
        added = 0
        with LOCK_PEERS:
            for pid, info in data.items():
                PEERS[pid] = info
                added += 1
        return {
            "status_code": 200,
            "body": json.dumps({"result": "ok", "added": added}),
            "headers": {"Content-Type": "application/json"},
        }
    except Exception as e:
        return {
            "status_code": 400,
            "body": json.dumps({"error": str(e)}),
            "headers": {"Content-Type": "application/json"},
        }


# --------------------------
# Channel management
# --------------------------
@app.route("/create-channel", methods=["POST"])
def create_channel(headers, body):
    """
    Body: {"channel_name": "room1", "peed_id": "peer1"}
    """
    try:
        data = json.loads(body)
        cname = data["channel_name"]
        owner = data["peer_id"]
        with LOCK_CHANNELS:
            if cname in CHANNELS:
                return {
                    "status_code": 400,
                    "body": json.dumps({"error": "Channel already exists"}),
                    "headers": {"Content-Type": "application/json"},
                }

            CHANNELS[cname] = {"owner": owner, "members": [owner]}
        print(f"[Tracker] Channel '{cname}' created by {owner}")
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


@app.route("/join-channel", methods=["POST"])
def join_channel(headers, body):
    """
    Body: {"channel_name": "room1", "peer_id": "peer2"}
    """
    try:
        data = json.loads(body)
        cname = data["channel_name"]
        pid = data["peer_id"]

        with LOCK_CHANNELS:
            if cname not in CHANNELS:
                return {
                    "status_code": 404,
                    "body": json.dumps({"error": "Channel not found"}),
                    "headers": {"Content-Type": "application/json"},
                }

            if pid not in CHANNELS[cname]["members"]:
                CHANNELS[cname]["members"].append(pid)
        print(f"[Tracker] {pid} joined channel '{cname}'")

        return {
            "status_code": 200,
            "body": json.dumps({"result": "ok", "members": CHANNELS[cname]["members"]}),
            "headers": {"Content-Type": "application/json"},
        }
    except Exception as e:
        return {
            "status_code": 400,
            "body": json.dumps({"error": str(e)}),
            "headers": {"Content-Type": "application/json"},
        }


@app.route("/heartbeat", methods=["POST"])
def heartbeat(headers, body):
    """Receive heartbeat from peer to indicate it's alive."""
    data = json.loads(body)
    peer_id = data["peer_id"]
    with LOCK_PEERS:
        if peer_id in PEERS:
            PEERS[peer_id]["last_seen"] = time.time()
            print(f"[Tracker] Received heartbeat from {peer_id}")
        else:
            print(f"[Tracker] Heartbeat from unknown peer {peer_id}")
    return {"ok": True}


def cleanup_peers():
    """Periodically check for dead peers and remove them."""
    MAX_INACTIVE = 6  # seconds
    while True:
        now = time.time()
        dead = []

        for pid, data in list(PEERS.items()):
            ts = data.get("last_seen", 0)
            if now - ts > MAX_INACTIVE:  # considered dead
                dead.append(pid)

        with LOCK_PEERS, LOCK_CHANNELS:
            for pid in dead:
                print(f"[Tracker] Peer {pid} timed out, removing.")
                PEERS.pop(pid, None)  # remove from peers list

            for ch, data in CHANNELS.items():
                members = data["members"]
                for pid in dead:
                    if pid in members:
                        members.remove(pid)
                    if data["owner"] == pid:
                        print(f"[Tracker] Channel '{ch}' owner {pid} timed out, deleting channel.")
                        CHANNELS.pop(ch, None)
                        break  # channel deleted, no need to check further

        time.sleep(3)


def create_tracker_app():
    threading.Thread(target=cleanup_peers, daemon=True).start()
    return app
