
# ChatSkibidi Law - Chatbot Luật

**ChatSkibidi** là một chatbot đơn giản được xây dựng bằng Python, sử dụng thư viện `tkinter` để tạo giao diện người dùng (GUI). Dự án này mang tính giải trí, cho phép người dùng tương tác trực tiếp với chatbot trong một không gian vui nhộn và thú vị.

---
## 🚀 Hướng Dẫn Sử Dụng

### 1. Build và khởi chạy tất cả các services
```bash
docker-compose up --build
```

### 2. Khởi chạy từng service riêng lẻ

- Chạy crawler:
  ```bash
  docker-compose up crawler
  ```
- Chạy server Flask:
  ```bash
  docker-compose up flask_server
  ```
- Chạy ứng dụng Streamlit:
  ```bash
  docker-compose up streamlit_app
  ```
### 3. Xem log của các service
- Log crawler:
  ```bash
  docker-compose logs -f crawler
  ```
- Log Flask server:
  ```bash
  docker-compose logs -f flask_server
  ```
- Log Streamlit app:
  ```bash
  docker-compose logs -f streamlit_app
  ```
### 4. Dừng tất cả các service
```bash
docker-compose down
```
---
💡 *Bạn có thể tùy chỉnh giao diện và chủ đề cho để tạo ra trải nghiệm cá nhân hóa màu sắc hơn.*
---
