# run_peer.py
import argparse
import threading
from apps.peer import Peer

parser = argparse.ArgumentParser()
parser.add_argument("--peer-id", required=True)
parser.add_argument("--ip", default="0.0.0.0")
parser.add_argument("--p2p-port", type=int, required=True, help="port for P2P socket")
parser.add_argument("--http-port", type=int, required=True, help="port for web UI")
parser.add_argument("--tracker-host", default="127.0.0.1")
parser.add_argument("--tracker-port", type=int, default=8080)
args = parser.parse_args()

peer = Peer(
    peer_id=args.peer_id,
    ip=args.ip,
    p2p_port=args.p2p_port,
    http_port=args.http_port,
    tracker_host=args.tracker_host,
    tracker_port=args.tracker_port,
)
# run: this will start P2P server + tracker loop + HTTP UI (blocking)
peer.run()
