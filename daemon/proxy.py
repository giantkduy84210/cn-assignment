#
# Copyright (C) 2025 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# WeApRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#

"""
daemon.proxy
~~~~~~~~~~~~~~~~~

This module implements a simple proxy server using Python's socket and threading libraries.
It routes incoming HTTP requests to backend services based on hostname mappings and returns
the corresponding responses to clients.

Requirement:
-----------------
- socket: provides socket networking interface.
- threading: enables concurrent client handling via threads.
- response: customized :class: `Response <Response>` utilities.
- httpadapter: :class: `HttpAdapter <HttpAdapter >` adapter for HTTP request processing.
- dictionary: :class: `CaseInsensitiveDict <CaseInsensitiveDict>` for managing headers and cookies.

"""
import socket
import threading
from .response import *
from .httpadapter import HttpAdapter
from .dictionary import CaseInsensitiveDict

import random
import itertools

#: A dictionary mapping hostnames to backend IP and port tuples.
#: Used to determine routing targets for incoming requests.
PROXY_PASS = {
    "192.168.56.103:8080": ("192.168.56.103", 9000),
    "app1.local": ("192.168.56.103", 9001),
    "app2.local": ("192.168.56.103", 9002),
}

_round_robin_counters = {}


def forward_request(host, port, request):
    """
    Forwards an HTTP request to a backend server and retrieves the response.

    :params host (str): IP address of the backend server.
    :params port (int): port number of the backend server.
    :params request (str): incoming HTTP request.

    :rtype bytes: Raw HTTP response from the backend server. If the connection fails, returns a 404 Not Found response.
    """

    backend = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        backend.connect((host, port))
        backend.sendall(request.encode())
        buffer = b""
        while b"\r\n\r\n" not in buffer:
            buffer += backend.recv(1024)
        header, rest = buffer.split(b"\r\n\r\n", 1)
        headers = header.decode().splitlines()
        content_length = 0
        for line in headers:
            if line.lower().startswith("content-length:"):
                content_length = int(line.split(":", 1)[1].strip())
        while len(rest) < content_length:
            rest += backend.recv(1024)
        response = header + b"\r\n\r\n" + rest
        return response
    except socket.error as e:
        print("Socket error: {}".format(e))
        return (
            "HTTP/1.1 404 Not Found\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: 13\r\n"
            "Connection: close\r\n"
            "\r\n"
            "404 Not Found"
        ).encode("utf-8")


def resolve_routing_policy(hostname, routes):
    """
    Handles an routing policy to return the matching proxy_pass.
    It determines the target backend to forward the request to.

    :params host (str): IP address of the request target server.
    :params port (int): port number of the request target server.
    :params routes (dict): dictionary mapping hostnames and location.
    """

    print("[Proxy] Resolving routing policy for hostname {}".format(hostname))
    proxy_map, policy = routes.get(hostname, ("127.0.0.1:9000", "round-robin"))
    print("Resolved proxy_map {} with policy {}".format(proxy_map, policy))

    proxy_host = ""
    proxy_port = "9000"
    if isinstance(proxy_map, list):
        if len(proxy_map) == 0:
            print("[Proxy] Emtpy resolved routing of hostname {}".format(hostname))
            print("[Proxy] Empty proxy_map result")
            # TODO: implement the error handling for non mapped host
            #       the policy is design by team, but it can be
            #       basic default host in your self-defined system
            # Use a dummy host to raise an invalid connection
            proxy_host = "127.0.0.1"
            proxy_port = "9000"
        elif len(proxy_map) == 1:
            print(
                "[Proxy] resolve route of hostname {} is a singular to".format(
                    hostname)
            )
            proxy_host, proxy_port = proxy_map[0].split(":", 2)
        elif policy == "round-robin":
            print(f"[Proxy] Applying round-robin policy for {hostname}")
            # Use a counter to track the last used backend for each hostname
            counter = _round_robin_counters.get(hostname, 0)
            backend = proxy_map[counter % len(proxy_map)]
            _round_robin_counters[hostname] = counter + 1
            proxy_host, proxy_port = backend.split(":", 1)
        elif policy == "random":
            backend = random.choice(proxy_map)
            proxy_host, proxy_port = backend.split(":", 1)
        else:
            # Out-of-handle mapped host
            proxy_host = "127.0.0.1"
            proxy_port = "9000"
    else:
        print("[Proxy] resolve route of hostname {} is a singular to".format(hostname))
        proxy_host, proxy_port = proxy_map.split(":", 2)

    return proxy_host, proxy_port


def handle_client(ip, port, conn, addr, routes):
    """
    Handles an individual client connection by parsing the request,
    determining the target backend, and forwarding the request.

    The handler extracts the Host header from the request to
    matches the hostname against known routes. In the matching
    condition,it forwards the request to the appropriate backend.

    The handler sends the backend response back to the client or
    returns 404 if the hostname is unreachable or is not recognized.

    :params ip (str): IP address of the proxy server.
    :params port (int): port number of the proxy server.
    :params conn (socket.socket): client connection socket.
    :params addr (tuple): client address (IP, port).
    :params routes (dict): dictionary mapping hostnames and location.
    """

    buffer = b""
    while b"\r\n\r\n" not in buffer:
        buffer += conn.recv(1024)
    header, rest = buffer.split(b"\r\n\r\n", 1)
    headers = header.decode().splitlines()
    content_length = 0
    for line in headers:
        if line.lower().startswith("content-length:"):
            content_length = int(line.split(":", 1)[1].strip())
    while len(rest) < content_length:
        rest += conn.recv(1024)

    # Inject X-Forwarded-For so backends can determine the original client IP
    # This is critical for tracker to auto-detect peer public IPs
    has_xff = any(h.lower().startswith("x-forwarded-for:")
                  for h in headers[1:])
    if not has_xff and len(addr) > 0:
        # Insert X-Forwarded-For before the blank line
        headers.append(f"X-Forwarded-For: {addr[0]}")

    request = "\r\n".join(headers) + "\r\n\r\n" + rest.decode()

    if not request.strip():
        # print(f"[Proxy] {addr} sent an empty request")
        conn.close()
        return

    # Extract hostname
    host_header = None
    for line in request.splitlines():
        if line.lower().startswith("host:"):
            host_header = line.split(":", 1)[1].strip()
            break

    if not host_header:
        # print(f"[Proxy] {addr} missing Host header")
        conn.sendall(
            (
                "HTTP/1.1 400 Bad Request\r\n"
                "Content-Type: text/plain\r\n"
                "Content-Length: 25\r\n"
                "Connection: close\r\n"
                "\r\n"
                "Missing Host header field"
            ).encode("utf-8")
        )
        conn.close()
        return
    
    if (routes.get(host_header) is None):
        hostname = host_header.split(":")[0]
    else:
        hostname = host_header

    print("[Proxy] {} at Host: {}".format(addr, hostname))

    # Resolve the matching destination in routes and need conver port
    # to integer value
    resolved_host, resolved_port = resolve_routing_policy(hostname, routes)
    try:
        resolved_port = int(resolved_port)
    except ValueError:
        print("Not a valid integer")

    if resolved_host:
        print(
            "[Proxy] Host name {} is forwarded to {}:{}".format(
                hostname, resolved_host, resolved_port
            )
        )
        response = forward_request(resolved_host, resolved_port, request)
    else:
        response = (
            "HTTP/1.1 404 Not Found\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: 13\r\n"
            "Connection: close\r\n"
            "\r\n"
            "404 Not Found"
        ).encode("utf-8")
    conn.sendall(response)
    conn.close()


def run_proxy(ip, port, routes):
    """
    Starts the proxy server and listens for incoming connections.

    The process dinds the proxy server to the specified IP and port.
    In each incomping connection, it accepts the connections and
    spawns a new thread for each client using `handle_client`.


    :params ip (str): IP address to bind the proxy server.
    :params port (int): port number to listen on.
    :params routes (dict): dictionary mapping hostnames and location.

    """

    proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        proxy.bind((ip, port))
        proxy.listen(50)
        print("[Proxy] Listening on IP {} port {}".format(ip, port))
        while True:
            conn, addr = proxy.accept()
            #
            #  TODO: implement the step of the client incomping connection
            #        using multi-thread programming with the
            #        provided handle_client routine
            #
            # Implementation #########################################
            client_thread = threading.Thread(
                target=handle_client, args=(ip, port, conn, addr, routes)
            )
            client_thread.start()
            ##########################################################
    except socket.error as e:
        print("Socket error: {}".format(e))


def create_proxy(ip, port, routes):
    """
    Entry point for launching the proxy server.

    :params ip (str): IP address to bind the proxy server.
    :params port (int): port number to listen on.
    :params routes (dict): dictionary mapping hostnames and location.
    """

    run_proxy(ip, port, routes)
