import requests
from bs4 import BeautifulSoup
import time
import re

# URL mục tiêu
TARGET_URL = "https://thuvienphapluat.vn/van-ban/Giao-thong-Van-tai/Nghi-dinh-168-2024-ND-CP-xu-phat-vi-pham-hanh-chinh-an-toan-giao-thong-duong-bo-619502.aspx"

# Giả lập User-Agent của trình duyệt thông thường
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36', # Sử dụng User-Agent phổ biến
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
    'Referer': 'https://thuvienphapluat.vn/', # Thêm Referer có thể giúp
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

def clean_text(text):
    """Làm sạch text cơ bản: loại bỏ khoảng trắng thừa"""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def crawl_content1(url):
    """Crawl nội dung từ div có class 'content1'"""
    print(f"Đang cố gắng crawl URL: {url}")
    try:
        # Thêm timeout và allow_redirects=True (mặc định)
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status() # Kiểm tra lỗi HTTP (4xx, 5xx)

        # Sử dụng html.parser hoặc lxml (nếu đã cài: pip install lxml)
        soup = BeautifulSoup(response.content, 'html.parser')

        # Tìm div có class là "content1"
        # Lưu ý: class có thể thay đổi, cần kiểm tra lại bằng Inspect Element (F12)
        content_div = soup.find('div', class_='content1')

        if content_div:
            print("Đã tìm thấy thẻ div.content1.")
            # Lấy toàn bộ text bên trong div, giữ lại cấu trúc xuống dòng tương đối
            # get_text(separator='\n') giúp giữ lại các dòng mới
            raw_text = content_div.get_text(separator='\n', strip=True)

            # Có thể bạn muốn làm sạch thêm hoặc xử lý text ở đây
            # Ví dụ: loại bỏ các dòng trống liên tiếp
            lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
            cleaned_content = "\n".join(lines)

            print("--- Nội dung đã crawl: ---")
            print(cleaned_content)
            return cleaned_content
        else:
            print("Không tìm thấy thẻ div với class 'content1'. Có thể cấu trúc HTML đã thay đổi hoặc nội dung được tải bằng JavaScript.")
            # In ra một phần HTML để debug nếu không tìm thấy
            # print("\n--- HTML Source (một phần): ---")
            # print(soup.prettify()[:2000]) # In 2000 ký tự đầu của HTML
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
    crawled_data = crawl_content1(TARGET_URL)

    if crawled_data:
        # Lưu nội dung vào file (tùy chọn)
        try:
            file_name = "nghi_dinh_168_2024_content.txt"
            with open(file_name, 'w', encoding='utf-8') as f:
                f.write(crawled_data)
            print(f"\nĐã lưu nội dung vào file: {file_name}")
        except Exception as e:
            print(f"Lỗi khi lưu file: {e}")
    else:
        print("\nKhông crawl được dữ liệu.")