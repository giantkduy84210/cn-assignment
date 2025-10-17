# tracker_server.py
import json
import argparse
from daemon.weaprous import WeApRous

# --------------------------
# Config
# --------------------------
DEFAULT_PORT = 8000
app = WeApRous()

# --------------------------
# Global data
# --------------------------
PEERS = {}      # {peer_id: {"ip":..., "port":...}}
CHANNELS = {}   # {channel_name: {"owner":..., "members": [peer_id,...]}}

# --------------------------
# Peer management
# --------------------------
@app.route('/submit-info', methods=['POST'])
def submit_info(headers, body):
    """
    Peer submit its information to the tracker.
    Body: {"peer_id": "peer1", "ip": "127.0.0.1", "port": 9001}
    """
    try:
        data = json.loads(body)
        peer_id = data["peer_id"]
        ip = data["ip"]
        port = data["port"]
        PEERS[peer_id] = {"ip": ip, "port": port}
        print(f"[Tracker] Registered peer {peer_id} at {ip}:{port}")
        return {"status_code": 200,
                "body": json.dumps({"result": "ok"}),
                "headers": {"Content-Type": "application/json"}}
    except Exception as e:
        return {"status_code": 400,
                "body": json.dumps({"error": str(e)}),
                "headers": {"Content-Type": "application/json"}}


@app.route('/get-list', methods=['GET'])
def get_list(headers, body):
    """Return current peer list and channel membership"""
    response = {
        "peers": PEERS,
        "channels": {ch: data["members"] for ch, data in CHANNELS.items()}
    }
    return {"status_code": 200,
            "body": json.dumps(response),
            "headers": {"Content-Type": "application/json"}}


@app.route('/add-list', methods=['POST'])
def add_list(headers, body):
    """Merge multiple peer info into PEERS"""
    try:
        data = json.loads(body)
        added = 0
        for pid, info in data.items():
            PEERS[pid] = info
            added += 1
        return {"status_code": 200,
                "body": json.dumps({"result": "ok", "added": added}),
                "headers": {"Content-Type": "application/json"}}
    except Exception as e:
        return {"status_code": 400,
                "body": json.dumps({"error": str(e)}),
                "headers": {"Content-Type": "application/json"}}

# --------------------------
# Channel management
# --------------------------
@app.route('/create-channel', methods=['POST'])
def create_channel(headers, body):
    """
    Body: {"channel_name": "room1", "owner": "peer1"}
    """
    try:
        data = json.loads(body)
        cname = data["channel_name"]
        owner = data["owner"]

        if cname in CHANNELS:
            return {"status_code": 400,
                    "body": json.dumps({"error": "Channel already exists"}),
                    "headers": {"Content-Type": "application/json"}}

        CHANNELS[cname] = {"owner": owner, "members": [owner]}
        print(f"[Tracker] Channel '{cname}' created by {owner}")
        return {"status_code": 200,
                "body": json.dumps({"result": "ok"}),
                "headers": {"Content-Type": "application/json"}}
    except Exception as e:
        return {"status_code": 400,
                "body": json.dumps({"error": str(e)}),
                "headers": {"Content-Type": "application/json"}}


@app.route('/join-channel', methods=['POST'])
def join_channel(headers, body):
    """
    Body: {"channel_name": "room1", "peer_id": "peer2"}
    """
    try:
        data = json.loads(body)
        cname = data["channel_name"]
        pid = data["peer_id"]

        if cname not in CHANNELS:
            return {"status_code": 404,
                    "body": json.dumps({"error": "Channel not found"}),
                    "headers": {"Content-Type": "application/json"}}

        if pid not in CHANNELS[cname]["members"]:
            CHANNELS[cname]["members"].append(pid)
        print(f"[Tracker] {pid} joined channel '{cname}'")

        return {"status_code": 200,
                "body": json.dumps({"result": "ok", "members": CHANNELS[cname]["members"]}),
                "headers": {"Content-Type": "application/json"}}
    except Exception as e:
        return {"status_code": 400,
                "body": json.dumps({"error": str(e)}),
                "headers": {"Content-Type": "application/json"}}


@app.route('/get-channels', methods=['GET'])
def get_channels(headers, body):
    """Return current channel list and members"""
    return {"status_code": 200,
            "body": json.dumps(CHANNELS),
            "headers": {"Content-Type": "application/json"}}

# --------------------------
# Run server
# --------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='Tracker', description='P2P Tracker Server')
    parser.add_argument('--server-ip', default='0.0.0.0')
    parser.add_argument('--server-port', type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    ip = args.server_ip
    port = args.server_port

    print(f"[Tracker] Starting on {ip}:{port}")
    app.prepare_address(ip, port)
    app.run()
