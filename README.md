# HTTP Server and Hybrid Chat Application

This project implements a simple multi-process HTTP system.
It includes a proxy, a backend HTTP daemon, and a lightweight website framework called **WeApRous**.

## Architecture

```
Clients → Proxy (8080)
            ├──> Backend (9000): serves static HTML, handles cookies & authentication.
            └──> WeApRous (8000): RESTful API and chat logic.
```

- **Proxy**: Forwards client requests to backend or WeApRous based on `config/proxy.conf`.
- **Backend**: Basic HTTP server (socket-based), handles login and cookie session.
- **WeApRous**: Minimal RESTful framework to define custom routes and chat APIs.

## Run

### 1. Start Backend

```bash
python start_backend.py --server-ip 127.0.0.1 --server-port 9000
```

### 2. Start WeApRous

```bash
python start_proxy.py --server-ip 127.0.0.1 --server-port 8080
```

### 3. Start Proxy

```bash
python start_proxy.py --server-ip 127.0.0.1 --server-port 8080
```
