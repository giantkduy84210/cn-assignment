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
│   └── peer.py             # Định nghĩa lớp Peer và logic P2P + REST API
├── daemon/
│   └── weaprous.py         # Mini-framework HTTP xử lý route (WeApRous)
├── tracker_server.py       # Tracker Server quản lý peer & channel
├── reverse_proxy.py        # Proxy server khởi tạo daemon & routing
└── www/
    ├── chat.html           # Giao diện chat cho peer
    ├── tracker.html        # Giao diện theo dõi trên tracker
    ├── login.html          # Form đăng nhập
    └── unauthorized.html   # Trang thông báo chưa xác thực
```

---

## 🚀 Chạy chương trình

### 1️⃣ Chạy Tracker Server

```bash
python tracker_server.py --server-ip 127.0.0.1 --server-port 9000
```

Mặc định tracker sẽ chạy ở:  
📡 **http://127.0.0.1:9000**

Các endpoint chính:
- `POST /submit-info`: đăng ký peer.
- `GET /get-list`: trả về danh sách peer + channel.
- `POST /create-channel`: tạo kênh mới.
- `POST /join-channel`: tham gia kênh.

---

### 2️⃣ Chạy Peer Node

Ví dụ tạo 2 peer chạy song song:

```bash
python peers/peer.py peer1 127.0.0.1 10001 8001
python peers/peer.py peer2 127.0.0.1 10002 8002
```

Sau khi khởi động, mỗi peer:
- Đăng ký với tracker qua `/submit-info`
- Mở giao diện HTTP tại `http://127.0.0.1:800X`
- Mở server TCP để kết nối P2P trực tiếp giữa các peer

---

### 3️⃣ Giao diện web

Mỗi peer có trang chat riêng:  
➡️ `http://127.0.0.1:8001`  
➡️ `http://127.0.0.1:8002`  

Đăng nhập bằng:
```
username = <peer_id>
password = 29112005
```

Tracker có giao diện quản trị tại:  
➡️ `http://127.0.0.1:9000`  
Đăng nhập với:
```
username = Tracker
password = 29112005
```

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

