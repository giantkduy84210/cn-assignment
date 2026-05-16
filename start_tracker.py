# tracker_server.py
import argparse
import socket
from apps.tracker import create_tracker_app

# --------------------------
# Helper functions
# --------------------------


def get_local_ip():
    """Get the local IP that other machines on the network can reach"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Connect to a remote address (doesn't actually send data)
        # This determines which interface would be used for routing
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except:
            ip = '127.0.0.1'
    finally:
        s.close()
    return ip


# --------------------------
# Config
# --------------------------
DEFAULT_PORT = 9000

# --------------------------
# Run server
# --------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="Tracker", description="P2P Tracker Server")
    parser.add_argument("--server-ip", default="0.0.0.0")
    parser.add_argument("--server-port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    ip = args.server_ip
    port = args.server_port

    app = create_tracker_app()

    # Detect and display network information
    local_ip = get_local_ip()
    print(f"[Tracker] Starting on {ip}:{port}")
    print(f"[Tracker] Local IP address: {local_ip}")
    print(f"[Tracker] Other machines should connect to: {local_ip}:{port}")
    print(f"[Tracker] Web interface: http://{local_ip}:{port}")

    app.prepare_address(ip, port)
    app.run()
