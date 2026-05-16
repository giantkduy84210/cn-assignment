#
# Copyright (C) 2025 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course,
# and is released under the "MIT License Agreement". Please see the LICENSE
# file that should have been included as part of this package.
#
# WeApRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#


"""
start_sampleapp
~~~~~~~~~~~~~~~~~

This module provides a sample RESTful web application using the WeApRous framework.

It defines basic route handlers and launches a TCP-based backend server to serve
HTTP requests. The application includes a login endpoint and a greeting endpoint,
and can be configured via command-line arguments.
"""
import argparse
import socket

from daemon.weaprous import WeApRous
from apps.sampleApp import create_sampleapp

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

PORT = 9000  # Default port

if __name__ == "__main__":
    # Parse command-line arguments to configure server IP and port
    parser = argparse.ArgumentParser(
        prog="Backend", description="", epilog="Backend daemon"
    )
    parser.add_argument("--server-ip", default="0.0.0.0")
    parser.add_argument("--server-port", type=int, default=PORT)

    args = parser.parse_args()
    ip = args.server_ip
    port = args.server_port

    app = create_sampleapp()

    # Detect and display network information
    local_ip = get_local_ip()
    print(f"[SampleApp] Starting on {ip}:{port}")
    print(f"[SampleApp] Local IP address: {local_ip}")
    print(f"[SampleApp] Other machines should connect to: {local_ip}:{port}")
    print(f"[SampleApp] Web interface: http://{local_ip}:{port}")

    # Prepare and launch the RESTful application
    app.prepare_address(ip, port)
    app.run()
