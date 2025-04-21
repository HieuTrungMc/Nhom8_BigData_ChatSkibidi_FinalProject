import requests
from bs4 import BeautifulSoup
import time
import re
import json # <<< Import thư viện json
import os

# URL mục tiêu
TARGET_URL = "https://thuvienphapluat.vn/van-ban/Giao-thong-Van-tai/Nghi-dinh-168-2024-ND-CP-xu-phat-vi-pham-hanh-chinh-an-toan-giao-thong-duong-bo-619502.aspx"

# Headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
    'Referer': 'https://thuvienphapluat.vn/',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

def clean_paragraph_text(text):
    """Làm sạch text: loại bỏ khoảng trắng thừa"""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def parse_legal_document(html_content):
    """Phân tích HTML và xây dựng cấu trúc JSON"""
    soup = BeautifulSoup(html_content, 'html.parser')
    content_div = soup.find('div', class_='content1')

    if not content_div:
        print("Không tìm thấy thẻ div với class 'content1'.")
        return None

    document_structure = [] # Danh sách chứa các chương hoặc các điều nếu không có chương rõ ràng
    current_chapter = None
    current_article = None
    current_clause = None
    # Có thể cần thêm phần preamble cho nội dung đầu (CHÍNH PHỦ...)

    paragraphs = content_div.find_all('p')

    for p_tag in paragraphs:
        p_text = clean_paragraph_text(p_tag.get_text())
        if not p_text: # Bỏ qua các thẻ <p> trống
            continue

        # --- Xác định loại nội dung bằng regex ---
        match_chapter = re.match(r"^(Chương\s+[IVXLCDM]+)(.*)", p_text, re.IGNORECASE)
        match_article = re.match(r"^(Điều\s+\d+)\.(.*)", p_text)
        match_clause = re.match(r"^(\d+)\.(.*)", p_text)
        # Thay đổi regex cho điểm thành "a)" thay vì "a."
        match_point = re.match(r"^([a-zđ])\)(.*)", p_text) # Giả sử điểm là a), b)...

        if match_chapter:
            chapter_title_full = clean_paragraph_text(p_text) # Lấy cả dòng làm title chương
            current_chapter = {
                "type": "chapter",
                "title": chapter_title_full,
                "articles": []
            }
            document_structure.append(current_chapter)
            current_article = None
            current_clause = None
            print(f"Found Chapter: {chapter_title_full}")
        elif match_article:
            article_number = match_article.group(1).strip()
            article_title_text = match_article.group(2).strip()
            # Kết hợp số điều và phần text còn lại thành title đầy đủ
            article_title_full = f"{article_number}. {article_title_text}".strip()

            current_article = {
                "type": "article",
                "title": article_title_full,
                # "number": article_number, # Có thể tách riêng nếu muốn
                # "title_text": article_title_text, # Có thể tách riêng nếu muốn
                "clauses": [],
                "content": [] # Nội dung chung của điều (ít gặp)
            }
            # Nếu chưa có chương nào được xác định, thêm trực tiếp vào document_structure
            if current_chapter:
                current_chapter["articles"].append(current_article)
            else:
                 # Xử lý trường hợp không có thẻ "Chương" rõ ràng
                 # Có thể tạo một chapter mặc định hoặc thêm article trực tiếp
                 if not document_structure or document_structure[-1].get("type") != "default_chapter":
                     default_chapter = {"type": "default_chapter", "title": "Nội dung chính", "articles": []}
                     document_structure.append(default_chapter)
                     current_chapter = default_chapter
                 current_chapter["articles"].append(current_article)


            current_clause = None
            print(f"  Found Article: {article_title_full}")
        elif match_clause:
            clause_number = match_clause.group(1).strip()
            clause_text = match_clause.group(2).strip()
            current_clause = {
                "type": "clause",
                "number": clause_number,
                "content_full": clause_text, # Lưu phần text đi kèm khoản
                "points": [],
                "sub_content": [] # Nội dung con nếu có (ít gặp)
            }
            if current_article:
                current_article["clauses"].append(current_clause)
                print(f"    Found Clause: {clause_number}. {clause_text[:50]}...")
            else:
                print(f"Warning: Found clause '{clause_number}' but no current article.")
        elif match_point:
            point_letter = match_point.group(1).strip()
            point_text = match_point.group(2).strip()
            current_point = {
                "type": "point",
                "letter": point_letter,
                "content": point_text
            }
            if current_clause:
                current_clause["points"].append(current_point)
                print(f"      Found Point: {point_letter}) {point_text[:50]}...")
            elif current_article:
                 # Nếu điểm nằm ngay dưới Điều mà không có Khoản (ít gặp)
                 # Có thể thêm vào content của Điều hoặc tạo cấu trúc riêng
                 print(f"Warning: Found point '{point_letter}' directly under article, adding to article content.")
                 if "content" not in current_article: current_article["content"] = []
                 current_article["content"].append(f"{point_letter}) {point_text}")
            else:
                 print(f"Warning: Found point '{point_letter}' but no current clause or article.")

        # Xử lý các dòng text không phải là tiêu đề Chương/Điều/Khoản/Điểm
        elif not (match_chapter or match_article or match_clause or match_point):
             # Ưu tiên thêm vào điểm gần nhất (nếu có)
             if current_clause and current_clause["points"]:
                 # Nối vào nội dung của điểm cuối cùng
                 current_clause["points"][-1]["content"] += "\n" + p_text
             # Nếu không có điểm, thêm vào nội dung của khoản gần nhất
             elif current_clause:
                  current_clause["sub_content"].append(p_text)
             # Nếu không có khoản, thêm vào nội dung của điều gần nhất
             elif current_article:
                  current_article["content"].append(p_text)
             # Nếu không có gì cả (ví dụ phần đầu văn bản), có thể bỏ qua hoặc thêm vào preamble
             else:
                  print(f"Info: Skipping preamble/unstructured text: {p_text[:100]}...")


    return document_structure

def crawl_and_save_json(url, save_path):
    """Thực hiện crawl và lưu kết quả thành file JSON"""
    print(f"Đang crawl URL để tạo JSON: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=30) # Tăng timeout
        response.raise_for_status()
        print("HTML content fetched successfully.")

        parsed_data = parse_legal_document(response.content)

        if parsed_data:
            print(f"\nĐang lưu cấu trúc JSON vào: {save_path}")
            try:
                # Đảm bảo thư mục lưu trữ tồn tại
                save_dir = os.path.dirname(save_path)
                if save_dir: # Chỉ tạo nếu có đường dẫn thư mục
                    os.makedirs(save_dir, exist_ok=True)

                with open(save_path, 'w', encoding='utf-8') as f:
                    # indent=2 hoặc 4 để dễ đọc file JSON
                    json.dump(parsed_data, f, ensure_ascii=False, indent=2)
                print("Lưu file JSON thành công!")
                return True
            except Exception as e:
                print(f"Lỗi khi lưu file JSON: {e}")
                return False
        else:
            print("Không phân tích được dữ liệu từ HTML.")
            return False

    except requests.exceptions.Timeout:
        print("Lỗi: Request timed out.")
        return False
    except requests.exceptions.HTTPError as e:
        print(f"Lỗi HTTP: {e.response.status_code} - {e}")
        if e.response.status_code == 403:
            print("Lỗi 403 Forbidden: Bị chặn.")
        return False
    except requests.exceptions.RequestException as e:
        print(f"Lỗi Request: {e}")
        return False
    except Exception as e:
        print(f"Lỗi không xác định: {e}")
        return False

# --- Chạy chương trình ---
if __name__ == "__main__":
    # Đường dẫn lưu file JSON vào thư mục '../data'
    SAVE_DIRECTORY_JSON = "../data"
    BASE_FILE_NAME_JSON = "nhom8_crawl_data_nghi_dinh_168.json" # Đổi tên file output
    full_save_path_json = os.path.join(SAVE_DIRECTORY_JSON, BASE_FILE_NAME_JSON)

    # Gọi hàm crawl và lưu JSON
    crawl_and_save_json(TARGET_URL, full_save_path_json)