import requests
from bs4 import BeautifulSoup
import time
import re
import os

# URL mục tiêu
TARGET_URL = "https://thuvienphapluat.vn/van-ban/Giao-thong-Van-tai/Nghi-dinh-168-2024-ND-CP-xu-phat-vi-pham-hanh-chinh-an-toan-giao-thong-duong-bo-619502.aspx"

# Giả lập User-Agent của trình duyệt thông thường
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
    'Referer': 'https://thuvienphapluat.vn/',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

def clean_paragraph_text(text):
    """Làm sạch text của một đoạn <p>: loại bỏ khoảng trắng thừa"""
    text = re.sub(r'\s+', ' ', text) # Thay nhiều khoảng trắng bằng 1
    return text.strip()

def crawl_content1_by_paragraph(url):
    """Crawl nội dung từ div.content1, lấy theo từng thẻ <p>"""
    print(f"Đang cố gắng crawl URL: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        content_div = soup.find('div', class_='content1')

        if content_div:
            print("Đã tìm thấy thẻ div.content1.")

            # --- THAY ĐỔI CHÍNH Ở ĐÂY ---
            # Tìm tất cả các thẻ <p> bên trong div.content1
            paragraphs = content_div.find_all('p')

            # Lấy text từ mỗi thẻ <p>, làm sạch và nối lại bằng dấu xuống dòng
            paragraph_texts = []
            for p_tag in paragraphs:
                # Lấy text của thẻ <p>, strip khoảng trắng đầu/cuối
                # Quan trọng: chỉ lấy text trực tiếp của <p> và các thẻ con đơn giản (strong, em,...)
                # Không nên dùng get_text() nếu <p> chứa các thẻ block khác như div, table...
                # Trong trường hợp này, văn bản pháp luật thường chỉ có text và thẻ inline đơn giản trong <p>
                text = clean_paragraph_text(p_tag.get_text())
                # Chỉ thêm vào nếu đoạn không rỗng sau khi làm sạch
                if text:
                    paragraph_texts.append(text)

            # Nối các đoạn văn bản lại bằng một dấu xuống dòng duy nhất
            final_content = "\n".join(paragraph_texts)
            # -----------------------------

            print("--- Nội dung đã crawl (theo từng đoạn <p>): ---")
            print(final_content)
            return final_content
        else:
            print("Không tìm thấy thẻ div với class 'content1'.")
            return None

    except requests.exceptions.Timeout:
        print("Lỗi: Request timed out.")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"Lỗi HTTP: {e.response.status_code} - {e}")
        if e.response.status_code == 403:
            print("Lỗi 403 Forbidden: Rất có thể đã bị chặn bởi website.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Lỗi Request: {e}")
        return None
    except Exception as e:
        print(f"Lỗi không xác định khi xử lý: {e}")
        return None

# Chạy hàm crawl
if __name__ == "__main__":
    # Đổi tên hàm gọi thành hàm mới
    crawled_data = crawl_content1_by_paragraph(TARGET_URL)

     # Đường dẫn tương đối là '../data'
    SAVE_DIRECTORY = "../data"
    # Tạo thư mục nếu nó chưa tồn tại
    # exist_ok=True nghĩa là không báo lỗi nếu thư mục đã có sẵn
    try:
        os.makedirs(SAVE_DIRECTORY, exist_ok=True)
        print(f"Thư mục lưu trữ được kiểm tra/tạo: {os.path.abspath(SAVE_DIRECTORY)}") # In đường dẫn tuyệt đối để kiểm tra
    except OSError as e:
        print(f"Lỗi khi tạo thư mục '{SAVE_DIRECTORY}': {e}")
        # Quyết định xem có nên dừng lại hay không nếu không tạo được thư mục
        exit() # Thoát nếu không tạo được thư mục lưu trữ
    if crawled_data:
        try:
            file_name = "nhom8_crawl_data_nghi_dinh_168.txt" # Đổi tên file output
            # Kết hợp đường dẫn thư mục ('../data') và tên file
            full_save_path = os.path.join(SAVE_DIRECTORY, file_name)
            # Mở file với đường dẫn đầy đủ để ghi
            with open(full_save_path, 'w', encoding='utf-8') as f:
                f.write(crawled_data)
            # In ra đường dẫn đầy đủ đã lưu
            print(f"\nĐã lưu nội dung đã định dạng vào file: {full_save_path}")
        except Exception as e:
            print(f"Lỗi khi lưu file vào '{full_save_path}': {e}")
    else:
        print("\nKhông crawl được dữ liệu.")