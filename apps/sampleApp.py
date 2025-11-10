import json

from daemon import WeApRous

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
            #"status_code": 302,
            #"headers": {"Set-Cookie": "auth=true; Path=/", "Location": "/"},
            #"body": "",
            "body": open("www/index.html").read(),
            "status_code": 200,
            "headers": {"Set-Cookie": "auth=true", "Content-Type": "text/html"},
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
    
    
def create_sampleapp():
    return app