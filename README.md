# P2P Hybrid Chat System (WeApRous Release)

## Giới thiệu

Dự án này triển khai **ứng dụng hybrid chat** kết hợp giữa mô hình **Client-Server** và **Peer-to-Peer (P2P)**.  
Ứng dụng bao gồm 3 thành phần chính:

1. **Tracker Server**: giữ vai trò như một registry lưu trữ thông tin các peers và channels.
2. **Peer Node**: mỗi người dùng là một peer độc lập, có thể gửi/nhận tin nhắn trực tiếp hoặc theo channels.
3. **Reverse Proxy/Daemon Layer (WeApRous)**: cung cấp giao diện HTTP và định tuyến nội bộ.

---

## Cấu trúc thư mục

```python
.
├── peers/
│   └── peer.py              # Định nghĩa class Peer, xử lý logic P2P, giao tiếp TCP và REST API (WeApRous)
│
├── daemon/                  # Thư mục bao gồm các thành phần core của hệ thống HTTP daemon và framework WeApRous
│   ├── weaprous.py          # Framework RESTful mini (WeApRous): định nghĩa application, route, request/response handler
│   ├── backend.py           # Module backend xử lý HTTP cơ bản (socket server, cookie, MIME type, route cơ bản)
│   ├── dictionary.py        # Định nghĩa CaseInsensitiveDict để quản lý header & cookie (không phân biệt viết hoa/viết thường)
│   ├── httpadapter.py       # Bộ chuyển đổi HTTP request trở thành HTTP response (adapter layer giữa socket và handler)
│   ├── proxy.py             # Triển khai proxy server (route request dựa vào host header và cấu hình round-robin)
│   ├── request.py           # Parse HTTP request: method, path, headers, body
│   ├── response.py          # HTTP response: header, body, status code, MIME type, cookie
│   ├── utils.py             # Tiện ích hỗ trợ: get_auth_from_url,...
│
├── start_tracker.py         # Khởi động Tracker Server, lưu trữ danh sách peers & channels, cung cấp REST API
├── start_proxy.py           # Khởi động Proxy Server, config theo file config/proxy.conf, khởi tạo daemon proxy và định tuyến backend
├── start_p2p.py             # Khởi động Peer Node, khởi tạo P2P TCP server + HTTP server (WeApRous UI)
│
└── www/                     # Thư mục bao gồm các giao diện (frontend HTML)
    ├── chat.html            # Giao diện cho peer chat (sau khi đăng nhập)
    ├── tracker.html         # Giao diện theo dõi danh sách peers & channels trên tracker
    ├── login.html           # Form đăng nhập (username/password)
    └── unauthorized.html    # Trang thông báo khi người dùng chưa đăng nhập
```

---

## Khởi động chương trình

### Khởi động Tracker Server

```bash
python start_tracker.py --server-port 9000 --server-ip 127.0.0.1
```

Mặc định tracker sẽ khởi động ở:  
📡 **<http://127.0.0.1:9000>**

Đồng thời cũng có thể truy cập thông qua proxy:  
📡 **<http://127.0.0.1:8080>**

Endpoints:

- `POST /submit-info`: đăng ký peer.
- `GET /get-list`: trả về danh sách peer + channel.
- `POST /create-channel`: tạo kênh mới.
- `POST /join-channel`: tham gia kênh.

---

### Khởi động Proxy Server

```bash
python start_proxy.py --server-port 8080 --server-ip 127.0.0.1
```

---

### Khởi động Peer Node

Ví dụ khởi động 2 peers song song (trên cùng máy):

```bash
python start_p2p.py --peer-id peer1 --ip 0.0.0.0 --p2p-port 9001 --http-port 8101 --tracker-host 127.0.0.1 --tracker-port 9000
python start_p2p.py --peer-id peer2 --ip 0.0.0.0 --p2p-port 9002 --http-port 8102 --tracker-host 127.0.0.1 --tracker-port 9000
# Có thể thay đổi peer1, peer2 tuỳ ý (phân biệt)
...
```

**Lưu ý quan trọng về multi-machine:**

- `--ip` chỉ định địa chỉ bind (mặc định 0.0.0.0 để lắng nghe tất cả các interface)
- **Public IP được tự động phát hiện**: Tracker sẽ quan sát địa chỉ IP thực tế mà peer kết nối từ đó và trả về trong response. Peer sẽ tự động sử dụng IP này để quảng bá cho các peer khác.
- Điều này hoạt động cả khi kết nối trực tiếp đến tracker hoặc thông qua proxy (với X-Forwarded-For header)

Sau khi khởi động, mỗi peer:

- Đăng ký với tracker thông qua endpoint `/submit-info`
- Mở giao diện HTTP tại `http://127.0.0.1:<PORT>` (port của từng peer)
- Mở server TCP để kết nối P2P trực tiếp giữa các peers

---

### Giao diện

Mỗi peer có trang chat riêng biệt:

`http://127.0.0.1:8101`  
`http://127.0.0.1:8102`  
`...`

Đăng nhập:

```cpp
username = <peer_id>
password = 29112005
```

ở giao diện đăng nhập:

`http://127.0.0.1:8101/login`  
`http://127.0.0.1:8102/login`  
`...`

Tracker có giao diện quản lý tại:  
`http://127.0.0.1:9000` hoặc `http://127.0.0.1:8080` (thông qua proxy)

Đăng nhập với:

```cpp
username = Tracker
password = 29112005
```

ở giao diện đăng nhập:  
`http://127.0.0.1:9000/login` hoặc `http://127.0.0.1:8080/login` (thông qua proxy)

---

## Triển khai đa máy (Multi-machine Deployment)

Hệ thống hỗ trợ **tự động phát hiện Public IP**, cho phép triển khai trên nhiều máy khác nhau mà không cần cấu hình thủ công địa chỉ công khai.

### Cơ chế hoạt động

1. Peer gửi thông tin đăng ký đến Tracker
2. Tracker quan sát địa chỉ IP thực tế mà request đến từ đó (qua header `X-Forwarded-For` nếu có proxy, hoặc `x-remote-addr` từ kết nối trực tiếp)
3. Tracker sử dụng IP quan sát được thay vì IP mà peer tự khai báo
4. Tracker trả về `advertised_ip` trong response
5. Peer tự động cập nhật IP của mình với giá trị này

### Ví dụ triển khai

#### 1) Tracker Server (Máy A - IP: 192.168.1.10)

```bash
python start_tracker.py --server-ip 0.0.0.0 --server-port 9000
```

- Mở firewall cho port 9000
- Tracker sẽ tự động phát hiện IP của các peer kết nối đến

#### 2) Proxy Server (Máy B - IP: 192.168.1.20) [Tùy chọn]

Cập nhật `config/proxy.conf`:

```nginx
host "192.168.1.20:8080" {
    proxy_pass http://192.168.1.10:9000;
}
```

Chạy proxy:

```bash
python start_proxy.py --server-ip 0.0.0.0 --server-port 8080
```

#### 3) Peer Nodes (Các máy khác nhau)

**Peer 1 trên máy C (IP: 192.168.1.30):**

```bash
python start_p2p.py \
  --peer-id peer1 \
  --ip 0.0.0.0 \
  --p2p-port 9001 \
  --http-port 8101 \
  --tracker-host 192.168.1.10 \
  --tracker-port 9000
```

**Peer 2 trên máy D (IP: 192.168.1.40):**

```bash
python start_p2p.py  --peer-id peer2 --ip 0.0.0.0 --p2p-port 9001 --http-port 8101 --tracker-host 10.196.2.191 --tracker-port 9000
```

**Nếu sử dụng Proxy:**

```bash
python start_p2p.py \
  --peer-id peer1 \
  --ip 0.0.0.0 \
  --p2p-port 9001 \
  --http-port 8101 \
  --tracker-host 192.168.1.20 \
  --tracker-port 8080
```

### Lưu ý quan trọng

- **Firewall**: Mở các port cần thiết (tracker: 9000, proxy: 8080, peer: p2p-port và http-port)
- **NAT/Port Forwarding**: Nếu peer ở sau NAT, cần forward port và tracker sẽ thấy IP public của router
- **--ip 0.0.0.0**: Cho phép bind trên tất cả các network interface
- **Không cần --public-ip**: Tracker tự động phát hiện và thông báo lại cho peer
- **X-Forwarded-For**: Proxy tự động thêm header này để tracker biết IP gốc của client

---

## REST API trên Peer Node

| Endpoint          | Method | Mô tả                                        |
| ----------------- | ------ | -------------------------------------------- |
| `/get_list`       | GET    | Trả về danh sách peers & channels từ tracker |
| `/connect_peer`   | POST   | Kết nối tới 1 peer                           |
| `/send_peer`      | POST   | Gửi tin nhắn trực tiếp tới 1 peer            |
| `/broadcast_peer` | POST   | Gửi tin nhắn tới tất cả peers đã kết nối     |
| `/create_channel` | POST   | Khởi tạo 1 channel                           |
| `/join_channel`   | POST   | Tham gia 1 channel                           |
| `/send_channel`   | POST   | Gửi tin nhắn trong 1 channel                 |
| `/poll`           | GET    | Trả về danh sách các tin nhắn                |
| `/notifications`  | GET    | Trả về danh sách các tin nhắn mới            |

---

## Ghi chú

- Tất cả kết nối giữa các peers là **TCP full-duplex**.
- Tracker chỉ đóng vai trò **điều phối (metadata)**, không trung chuyển nội dung chat.
- Mỗi peer có **daemon WeApRous** riêng biệt, HTTP REST API phục vụ frontend.
- Hệ thống hỗ trợ **đa kênh (multi-channel)** và **giao tiếp trực tiếp (direct message)**.
- Thư mục `www/` chứa giao diện thông qua route `/` trong peer & tracker.

---

## Cấu hình ví dụ

Ví dụ Peer A và B cùng trong kênh `room1`:

```python
Peer A (127.0.0.1:10001, HTTP 8001)
Peer B (127.0.0.1:10002, HTTP 8002)
```

```bash

curl -X POST http://127.0.0.1:8001/create_channel -d '{"channel": "room1"}'
curl -X POST http://127.0.0.1:8002/join_channel -d '{"channel": "room1"}'
curl -X POST http://127.0.0.1:8001/send_channel -d '{"channel": "room1", "message": "Hello from A"}'
```

Kết quả: Peer B nhận tin nhắn `"Hello from A"` trực tiếp thông qua kết nối TCP.

---

## License

```markdown
Copyright (C) 2025 pdnguyen - HCMUT.
This project is released under the MIT License for educational purposes.
```
