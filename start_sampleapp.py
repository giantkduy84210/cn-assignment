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

import json
import socket
import argparse

from daemon.weaprous import WeApRous

PORT = 8000  # Default port

app = WeApRous()


@app.route("/hello", methods=["PUT"])
def hello(headers, body):
    """
    Handle greeting via PUT request.

    This route prints a greeting message to the console using the provided headers
    and body.

    :param headers (str): The request headers or user identifier.
    :param body (str): The request body or message payload.
    """
    print("[SampleApp] ['PUT'] Hello in {} to {}".format(headers, body))
    return {"body": "<h1>Hello, {}!</h1>".format(body), "status_code": 200}


@app.route("/login", methods=["POST"])
def login(headers, body):
    """
    Handle user login via POST request.
    Expect body as form-urlencoded: username=...&password=...
    """
    try:
        # Parse form-urlencoded body
        params = dict(pair.split("=", 1) for pair in body.split("&") if "=" in pair)
        username = params.get("username")
        password = params.get("password")
    except Exception:
        username = password = None

    # Kiểm tra credentials
    if username == "kstl" and password == "29112005":
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
    cookies = headers.get("cookie", "")  # giả sử headers là dict
    if cookies and cookies.get("auth") == "true":
        return {
            "body": open("www/index.html").read(),
            "status_code": 200,
            "headers": {"Content-Type": "text/html"},
        }
    else:
        return {
            "body": open("www/unauthorized.html").read(),
            "status_code": 401,
            "headers": {"Content-Type": "text/html"},
        }


###################################################
###################### Task 2 #####################
###################################################
peers = {}


@app.route("/submit-info", methods=["POST"])
def submit_info(headers, body):
    """
    Peer submit its information to the server.
    The body should be a JSON object with keys: peer_id, ip, port.
    Example body: {"peer_id": "peer1", "ip": "192.168.1.1", "port": 5000}
    """
    try:
        data = json.loads(body)
        peer_id = data["peer_id"]
        ip = data["ip"]
        port = data["port"]
        peers[peer_id] = {"ip": ip, "port": port}
        return {
            "status_code": 200,
            "body": json.dumps({"result": "ok"}),
            "headers": {"Content-Type": "application/json"},
        }
    except:
        return {
            "status_code": 400,
            "body": "Invalid request",
            "headers": {"Content-Type": "text/plain"},
        }


@app.route("/get-list", methods=["GET"])
def get_list(headers, body):
    """Peer yêu cầu danh sách peer đang online"""
    return {
        "status_code": 200,
        "body": json.dumps(peers),
        "headers": {"Content-Type": "application/json"},
    }


@app.route("/add-list", methods=["POST"])
def add_list(headers, body):
    try:
        data = json.loads(body)
        # Ví dụ body: {"peer1": {"ip": "127.0.0.1", "port": 9001}, "peer2": {...}}
        added = 0
        for pid, info in data.items():
            peers[pid] = info
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


if __name__ == "__main__":
    # Parse command-line arguments to configure server IP and port
    parser = argparse.ArgumentParser(
        prog="Backend", description="", epilog="Beckend daemon"
    )
    parser.add_argument("--server-ip", default="0.0.0.0")
    parser.add_argument("--server-port", type=int, default=PORT)

    args = parser.parse_args()
    ip = args.server_ip
    port = args.server_port

    # Prepare and launch the RESTful application
    app.prepare_address(ip, port)
    app.run()
