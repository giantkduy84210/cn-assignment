# tracker_server.py
import argparse
from apps.tracker import create_tracker_app
# --------------------------
# Config
# --------------------------
DEFAULT_PORT = 9000

# --------------------------
# Run server
# --------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="Tracker", description="P2P Tracker Server")
    parser.add_argument("--server-ip", default="0.0.0.0")
    parser.add_argument("--server-port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    ip = args.server_ip
    port = args.server_port

    app = create_tracker_app()

    print(f"[Tracker] Starting on {ip}:{port}")
    app.prepare_address(ip, port)
    app.run()
