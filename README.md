# P2P Hybrid Chat System (WeApRous Release)

## 📘 Giới thiệu

Dự án này triển khai **ứng dụng chat lai (Hybrid Chat)** kết hợp giữa mô hình **Client-Server** và **Peer-to-Peer (P2P)**.  
Ứng dụng gồm 3 thành phần chính:
1. **Tracker Server** – đóng vai trò như một registry lưu thông tin các peer và kênh (channel).
2. **Peer Node** – mỗi người dùng là một peer độc lập, có thể gửi/nhận tin nhắn trực tiếp hoặc theo kênh.
3. **Reverse Proxy / Daemon Layer (WeApRous)** – cung cấp giao diện HTTP và định tuyến nội bộ.

---

## ⚙️ Cấu trúc thư mục

```
.
├── peers/
│   └── peer.py              # Định nghĩa lớp Peer, xử lý logic P2P, giao tiếp TCP và REST API (WeApRous)
│
├── daemon/                  # Thư mục chứa các thành phần lõi của hệ thống HTTP daemon & framework WeApRous
│   ├── weaprous.py          # Framework RESTful mini (WeApRous): định nghĩa app, route, request/response handler
│   ├── backend.py           # Mô-đun backend xử lý HTTP cơ bản (socket server, cookie, MIME type, route cơ bản)
│   ├── dictionary.py        # Định nghĩa CaseInsensitiveDict để quản lý header & cookie (không phân biệt hoa/thường)
│   ├── httpadapter.py       # Bộ chuyển đổi HTTP request → response (adapter layer giữa socket và handler)
│   ├── proxy.py             # Triển khai proxy server (route request dựa vào Host header và cấu hình round-robin)
│   ├── request.py           # Xử lý phân tích (parse) HTTP request: method, path, headers, body
│   ├── response.py          # Tạo HTTP response: header, body, status code, MIME type, cookie
│   ├── utils.py             # Tiện ích hỗ trợ: logging, parse query string, kiểm tra MIME, đọc file,...
│
├── start_tracker.py         # Khởi động Tracker Server — lưu trữ danh sách peers & channels, cung cấp REST API
├── start_proxy.py           # Khởi động Proxy Server — đọc config/proxy.conf, tạo daemon proxy và định tuyến backend
├── start_p2p.py             # Chạy từng Peer instance — tạo P2P TCP server + HTTP server (WeApRous UI)
│
└── www/                     # Thư mục chứa giao diện web (frontend HTML)
    ├── chat.html            # Giao diện chính cho peer chat (sau khi đăng nhập)
    ├── tracker.html         # Trang giao diện theo dõi danh sách peers & channels trên tracker
    ├── login.html           # Form đăng nhập (username/password)
    └── unauthorized.html    # Trang thông báo khi chưa xác thực hoặc sai thông tin đăng nhập
```

---

## 🚀 Chạy chương trình

### 1️⃣ Chạy Tracker Server

```bash
python start_tracker.py --server-port 9000 --server-ip 127.0.0.1
```

Mặc định tracker sẽ chạy ở:  
📡 **http://127.0.0.1:9000**

Đồng thời cũng có thể truy cập thông qua proxy:  
📡 **http://127.0.0.1:8080**

Các endpoint chính:
- `POST /submit-info`: đăng ký peer.
- `GET /get-list`: trả về danh sách peer + channel.
- `POST /create-channel`: tạo kênh mới.
- `POST /join-channel`: tham gia kênh.

---

### 2️⃣ Chạy Proxy Server

```bash
python start_proxy.py --server-port 8080 --server-ip 127.0.0.1
```

---

### 3️⃣ Chạy Peer Node

Ví dụ tạo 2 peer chạy song song:

```bash
python start_p2p.py --peer-id peer1 --ip 127.0.0.1 --p2p-port 9001 --http-port 8101
python start_p2p.py --peer-id peer2 --ip 127.0.0.2 --p2p-port 9002 --http-port 8102
# Có thể thay peer1, peer2 thành tên tuỳ ý (phân biệt)
...
```

Sau khi khởi động, mỗi peer:
- Đăng ký với tracker qua `/submit-info`
- Mở giao diện HTTP tại `http://127.0.0.1:810X`
- Mở server TCP để kết nối P2P trực tiếp giữa các peer

---

### 4️⃣ Giao diện web

Mỗi peer có trang chat riêng:  
➡️ `http://127.0.0.1:8101`  
➡️ `http://127.0.0.1:8102`  
➡️ `...`

Đăng nhập bằng:
```
username = <peer_id>
password = 29112005
```
tại giao diện đăng nhập:  
➡️ `http://127.0.0.1:8101/login`  
➡️ `http://127.0.0.1:8102/login`  
➡️ `...`

Tracker có giao diện quản trị tại:  
➡️ `http://127.0.0.1:9000`  hoặc `http://127.0.0.1:8080` (thông qua proxy)

Đăng nhập với:
```
username = Tracker
password = 29112005
```
tại giao diện đăng nhập:  
➡️ `http://127.0.0.1:9000/login`  hoặc `http://127.0.0.1:8080/login` (thông qua proxy)

---

## 🔗 REST API trên Peer Node

| Endpoint | Method | Mô tả |
|-----------|--------|-------|
| `/get_list` | GET | Lấy danh sách peer & channel từ tracker |
| `/connect_peer` | POST | Kết nối tới 1 peer khác |
| `/send_peer` | POST | Gửi tin nhắn trực tiếp tới 1 peer |
| `/broadcast_peer` | POST | Phát tin tới tất cả peer đã kết nối |
| `/create_channel` | POST | Tạo channel mới |
| `/join_channel` | POST | Tham gia channel |
| `/send_channel` | POST | Gửi tin nhắn trong 1 channel |
| `/poll` | GET | Lấy danh sách tin nhắn |
| `/notifications` | GET | Lấy tin chưa đọc |

---

## 💡 Ghi chú kỹ thuật

- Tất cả kết nối giữa các peer là **TCP full-duplex**, giữ persistent socket để truyền thông song công.
- Tracker chỉ đóng vai trò **điều phối (metadata)**, không trung chuyển nội dung chat.
- Mỗi peer có **daemon WeApRous** riêng chạy HTTP REST API phục vụ frontend.
- Hệ thống hỗ trợ **đa kênh (multi-channel)** và **giao tiếp trực tiếp (direct message)**.
- Thư mục `www/` chứa giao diện web được nhúng qua route `/` trong peer & tracker.

---

## 📂 Cấu hình mẫu

Ví dụ Peer A và B cùng trong kênh `room1`:

```
Peer A (127.0.0.1:10001, HTTP 8001)
Peer B (127.0.0.1:10002, HTTP 8002)
```

Chạy lệnh:
```bash
curl -X POST http://127.0.0.1:8001/create_channel -d '{"channel": "room1"}'
curl -X POST http://127.0.0.1:8002/join_channel -d '{"channel": "room1"}'
curl -X POST http://127.0.0.1:8001/send_channel -d '{"channel": "room1", "message": "Hello from A"}'
```

Kết quả: Peer B nhận tin `"Hello from A"` trực tiếp qua kết nối TCP.

---

## 🧩 License

```
Copyright (C) 2025 pdnguyen - HCMUT.
This project is released under the MIT License for educational purposes.
```

