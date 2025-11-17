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
daemon.httpadapter
~~~~~~~~~~~~~~~~~

This module provides a http adapter object to manage and persist 
http settings (headers, bodies). The adapter supports both
raw URL paths and RESTful route definitions, and integrates with
Request and Response objects to handle client-server communication.
"""

from .request import Request
from .response import Response
from .dictionary import CaseInsensitiveDict


class HttpAdapter:
    """
    A mutable :class:`HTTP adapter <HTTP adapter>` for managing client connections
    and routing requests.

    The `HttpAdapter` class encapsulates the logic for receiving HTTP requests,
    dispatching them to appropriate route handlers, and constructing responses.
    It supports RESTful routing via hooks and integrates with :class:`Request <Request>`
    and :class:`Response <Response>` objects for full request lifecycle management.

    Attributes:
        ip (str): IP address of the client.
        port (int): Port number of the client.
        conn (socket): Active socket connection.
        connaddr (tuple): Address of the connected client.
        routes (dict): Mapping of route paths to handler functions.
        request (Request): Request object for parsing incoming data.
        response (Response): Response object for building and sending replies.
    """

    __attrs__ = [
        "ip",
        "port",
        "conn",
        "connaddr",
        "routes",
        "request",
        "response",
    ]

    def __init__(self, ip, port, conn, connaddr, routes):
        """
        Initialize a new HttpAdapter instance.

        :param ip (str): IP address of the client.
        :param port (int): Port number of the client.
        :param conn (socket): Active socket connection.
        :param connaddr (tuple): Address of the connected client.
        :param routes (dict): Mapping of route paths to handler functions.
        """

        #: IP address.
        self.ip = ip
        #: Port.
        self.port = port
        #: Connection
        self.conn = conn
        #: Conndection address
        self.connaddr = connaddr
        #: Routes
        self.routes = routes
        #: Request
        self.request = Request()
        #: Response
        self.response = Response()

    def handle_client(self, conn, addr, routes):
        """
        Handle an incoming client connection.

        This method reads the request from the socket, prepares the request object,
        invokes the appropriate route handler if available, builds the response,
        and sends it back to the client.

        :param conn (socket): The client socket connection.
        :param addr (tuple): The client's address.
        :param routes (dict): The route mapping for dispatching requests.
        """

        # Connection handler
        self.conn = conn
        # Connection address
        self.connaddr = addr
        # Request handler
        req = self.request
        # Response handler
        resp = self.response

        # Handle the request
        msg = b""
        # Read until the end of headers
        while b"\r\n\r\n" not in msg:
            chunk = conn.recv(1024)
            if not chunk:
                break
            msg += chunk

        if not msg:
            conn.close()
            return

        header_part, _, rest = msg.partition(b"\r\n\r\n")

        req.prepare(header_part.decode("utf-8"), routes)

        content_length = int(req.headers.get("content-length", 0))

        body_data = rest
        while len(body_data) < content_length:
            chunk = conn.recv(1024)
            if not chunk:
                break
            body_data += chunk

        req.body = body_data.decode("utf-8")

        response = None
        # Handle request hook
        if req.hook:
            print(
                "[HttpAdapter] hook in route-path METHOD {} PATH {}".format(
                    req.hook._route_path, req.hook._route_methods
                )
            )
            # Inject the observed client IP so route handlers can use it
            # This allows tracker to determine peer's public IP automatically
            try:
                client_ip = addr[0] if isinstance(
                    addr, tuple) and len(addr) > 0 else None
                if client_ip:
                    req.headers["x-remote-addr"] = client_ip
            except Exception:
                pass

            result = req.hook(req.headers, req.body)
            #
            # TODO: Process the result from the hook
            #
            # Implementation ###############################################
            if isinstance(result, dict):
                status_code = int(result.get("status_code", 200))
                body = result.get("body", "")
                extra_headers = result.get("headers", {}) or {}

                # Ensure body is bytes
                if isinstance(body, str):
                    body_bytes = body.encode("utf-8")
                elif isinstance(body, bytes):
                    body_bytes = body
                else:
                    # if handler returned dict/list -> jsonify
                    import json

                    body_bytes = json.dumps(body).encode("utf-8")
                    extra_headers.setdefault(
                        "Content-Type", "application/json")

                resp.status_code = status_code
                resp.headers.update(extra_headers)
                resp._content = body_bytes
            else:
                conn.sendall(b"HTTP/1.1 500 Internal Server Error\r\n\r\n")
                conn.close()
                return
            ################################################################

        # Build response
        response = resp.build_response(req)

        # Assign request and response objects
        self.request = req
        self.response = resp

        # print(response)
        conn.sendall(response)
        conn.close()

    @property
    def extract_cookies(self, req, resp):
        """
        Build cookies from the :class:`Request <Request>` headers.

        :param req:(Request) The :class:`Request <Request>` object.
        :param resp: (Response) The res:class:`Response <Response>` object.
        :rtype: cookies - A dictionary of cookie key-value pairs.
        """
        cookies = {}
        for header, value in req.headers.items():
            if header.lower() == "cookie":
                cookie_pairs = value.split(";")
                for pair in cookie_pairs:
                    if "=" in pair:
                        key, val = pair.split("=", 1)
                        cookies[key.strip()] = val.strip()
        return cookies

    def build_response(self, req, resp):
        """Builds a :class:`Response <Response>` object

        :param req: The :class:`Request <Request>` used to generate the response.
        :param resp: The  response object.
        :rtype: Response
        """
        response = Response()

        # Set encoding
        response.encoding = resp.encoding
        response.raw = resp
        response.reason = response.raw.reason

        if isinstance(req.url, bytes):
            response.url = req.url.decode("utf-8")
        else:
            response.url = req.url

        # Add new cookies from the server
        response.cookies = self.extract_cookies(req)

        # Give the Response context of the request and connection
        response.request = req
        response.connection = self

        return response

    # def get_connection(self, url, proxies=None):
    # """Returns a url connection for the given URL.

    # :param url: The URL to connect to.
    # :param proxies: (optional) A Requests-style dictionary of proxies used on this request.
    # :rtype: int
    # """

    # proxy = select_proxy(url, proxies)

    # if proxy:
    # proxy = prepend_scheme_if_needed(proxy, "http")
    # proxy_url = parse_url(proxy)
    # if not proxy_url.host:
    # raise InvalidProxyURL(
    # "Please check proxy URL. It is malformed "
    # "and could be missing the host."
    # )
    # proxy_manager = self.proxy_manager_for(proxy)
    # conn = proxy_manager.connection_from_url(url)
    # else:
    # # Only scheme should be lower case
    # parsed = urlparse(url)
    # url = parsed.geturl()
    # conn = self.poolmanager.connection_from_url(url)

    # return conn

    def add_headers(self, request):
        """
        Add headers to the request.

        This method is intended to be overridden by subclasses to inject
        custom headers. It does nothing by default.


        :param request: :class:`Request <Request>` to add headers to.
        """
        pass

    def build_proxy_headers(self, proxy):
        """Returns a dictionary of the headers to add to any request sent
        through a proxy.

        :class:`HttpAdapter <HttpAdapter>`.

        :param proxy: The url of the proxy being used for this request.
        :rtype: dict
        """
        headers = {}
        #
        # TODO: build your authentication here
        #       username, password =...
        # we provide dummy auth here
        #
        # Implementation ###############################################
        # NOT IMPORTANT AT THE MOMENT
        # TO BE IMPLEMENTED
        ################################################################
        username, password = ("user1", "password")

        if username:
            headers["Proxy-Authorization"] = (username, password)

        return headers
