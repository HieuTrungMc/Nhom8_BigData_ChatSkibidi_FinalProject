import requests
from bs4 import BeautifulSoup
import time
import re
import json
import os # Để tạo thư mục và đường dẫn file
import traceback # Để in chi tiết lỗi

# URL mục tiêu (giữ nguyên từ code trước)
TARGET_URL = "https://thuvienphapluat.vn/van-ban/Giao-thong-Van-tai/Nghi-dinh-168-2024-ND-CP-xu-phat-vi-pham-hanh-chinh-an-toan-giao-thong-duong-bo-619502.aspx"

# Headers (giữ nguyên)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
    'Referer': 'https://thuvienphapluat.vn/',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

# Thư mục lưu file JSON
SAVE_DIR = "legal_json_data"
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

def extract_text_from_p(p_tag):
    """Lấy text từ thẻ p, cố gắng giữ lại định dạng cơ bản"""
    text = p_tag.get_text(separator='\n', strip=True)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def parse_legal_structure(content_div):
    """Phân tích cấu trúc HTML và tạo JSON lồng nhau"""
    structured_data = [] # Danh sách các Chương hoặc mục gốc
    current_chuong = None
    current_dieu = None
    current_khoan = None
    current_diem = None

    # Tìm tất cả thẻ <p> là con trực tiếp hoặc cháu gần của div.content1
    # Dùng recursive=True nhưng cần cẩn thận hơn khi thêm nội dung
    paragraphs = content_div.find_all('p') # Tìm tất cả <p> bên trong
    print(f"DEBUG: Tổng số thẻ <p> tìm thấy bên trong div.content1: {len(paragraphs)}")

    # Nếu không tìm thấy thẻ p nào, thoát sớm
    if not paragraphs:
        print("DEBUG: Không tìm thấy thẻ <p> nào bên trong div.content1.")
        return []

    for i, p in enumerate(paragraphs):
        p_text = extract_text_from_p(p)
        print(f"\nDEBUG [{i+1}/{len(paragraphs)}]: Processing p_text: '{p_text[:100]}...'") # In ra 100 ký tự đầu
        if not p_text:
            print("DEBUG: Thẻ <p> trống, bỏ qua.")
            continue

        bold_text_tag = p.find('b')
        bold_text = extract_text_from_p(bold_text_tag) if bold_text_tag else None
        # print(f"DEBUG: bold_text = {bold_text}") # Tạm ẩn để giảm log

        a_tag = p.find('a')
        name_attr = a_tag['name'] if a_tag and a_tag.has_attr('name') else None

        # --- Cập nhật Regex để linh hoạt hơn ---
        # Chương: Bắt đầu bằng "Chương", theo sau là số La Mã hoặc số thường, có thể có dấu chấm/hai chấm
        chuong_match = re.match(r'^(Chương\s+(?:[IVXLCDM]+|\d+))\s*[:.]?\s*(.*)', p_text, re.IGNORECASE)
        # Điều: Bắt đầu bằng "Điều", số, có thể có dấu chấm/hai chấm
        dieu_match = re.match(r'^(Điều\s+\d+)\s*[:.]?\s*(.*)', p_text, re.IGNORECASE)
        # Khoản: Bắt đầu bằng số và dấu chấm, theo sau là khoảng trắng HOẶC nếu chỉ có số đứng một mình (ít gặp hơn)
        khoan_match = re.match(r'^(\d+)\.\s+(.*)', p_text) or re.match(r'^(\d+)$', p_text) # Thêm trường hợp chỉ có số
        # Điểm: Bắt đầu bằng chữ cái thường/hoa và dấu ngoặc đơn/chấm, theo sau là khoảng trắng
        diem_match = re.match(r'^([a-zA-Z])\)\s+(.*)', p_text) or re.match(r'^([a-zA-Z])\.\s+(.*)', p_text)

        # print(f"DEBUG: chuong={bool(chuong_match)}, dieu={bool(dieu_match)}, khoan={bool(khoan_match)}, diem={bool(diem_match)}") # Tạm ẩn

        # --- Logic xử lý các cấp độ ---
        if chuong_match:
            marker = chuong_match.group(1).strip()
            # Ưu tiên lấy title từ thẻ bold nếu có và khác marker
            title_content = bold_text if bold_text and bold_text.strip().upper() != marker.upper() else chuong_match.group(2).strip()
            title = title_content if title_content else "" # Đảm bảo title là string

            full_title = f"{marker} {title}".strip()
            new_chuong = {"level": "chuong", "title": full_title, "marker": marker, "name_attr": name_attr, "children": []}
            structured_data.append(new_chuong)
            current_chuong = new_chuong
            current_dieu = None
            current_khoan = None
            current_diem = None
            print(f"-> Found Chuong: {full_title}")

        elif dieu_match:
            if not current_chuong: # Nếu điều nằm ngoài chương (văn bản không có chương)
                 # Tạo một "chương ảo" để chứa các điều này
                 print("DEBUG: Điều nằm ngoài Chương, tạo Chương ảo 'root'")
                 current_chuong = {"level": "root", "title": "Nội dung chính", "marker": "root", "name_attr": None, "children": []}
                 structured_data.append(current_chuong)

            marker = dieu_match.group(1).strip()
            title_content = bold_text if bold_text and bold_text.strip().upper() != marker.upper() else dieu_match.group(2).strip()
            title = title_content if title_content else ""

            full_title = f"{marker} {title}".strip()
            new_dieu = {"level": "dieu", "title": full_title, "marker": marker, "name_attr": name_attr, "children": []}
            current_chuong["children"].append(new_dieu)
            current_dieu = new_dieu
            current_khoan = None
            current_diem = None
            print(f"  -> Found Dieu: {full_title}")

        elif khoan_match and current_dieu:
            marker = khoan_match.group(1)
            content_start = ""
            if len(khoan_match.groups()) > 1 and khoan_match.group(2): # Nếu có group 2 (trường hợp số + chấm + nội dung)
                 marker += "."
                 content_start = khoan_match.group(2).strip()
            # Trường hợp chỉ có số (ít gặp), marker chỉ là số

            new_khoan = {"level": "khoan", "marker": marker, "children": []}
            if content_start:
                new_khoan["children"].append(content_start)
            current_dieu["children"].append(new_khoan)
            current_khoan = new_khoan
            current_diem = None
            print(f"    -> Found Khoan: {marker}")

        elif diem_match and current_khoan:
            marker = diem_match.group(1)
            content_start = ""
            # Xác định dấu kết thúc marker (ngoặc đơn hay chấm)
            if p_text.strip().startswith(marker + ')'):
                 marker += ")"
            elif p_text.strip().startswith(marker + '.'):
                 marker += "."
            # Lấy nội dung sau marker
            if len(diem_match.groups()) > 1 and diem_match.group(2):
                content_start = diem_match.group(2).strip()

            new_diem = {"level": "diem", "marker": marker, "children": []}
            if content_start:
                new_diem["children"].append(content_start)
            current_khoan["children"].append(new_diem)
            current_diem = new_diem
            print(f"      -> Found Diem: {marker}")

        else: # Nội dung thông thường
            print(f"DEBUG: Entering 'else' block for content.")
            # Xác định container để thêm nội dung
            target_container = None
            if current_diem: target_container = current_diem
            elif current_khoan: target_container = current_khoan
            elif current_dieu: target_container = current_dieu
            elif current_chuong: target_container = current_chuong
            # Nếu không có container nào, đây có thể là đoạn text mô tả đầu văn bản
            # Hoặc một cấu trúc không xác định được

            if target_container:
                print(f"DEBUG: Trying to add content to {target_container.get('level')}")
                # Kiểm tra trùng lặp đơn giản
                is_duplicate = False
                if target_container["children"]:
                    last_child = target_container["children"][-1]
                    # Chỉ kiểm tra trùng lặp nếu cả hai đều là string
                    if isinstance(last_child, str) and last_child == p_text:
                        is_duplicate = True

                if not is_duplicate:
                     target_container["children"].append(p_text)
                     print(f"        -> Added content to {target_container.get('level')}: {p_text[:50]}...")
                else:
                     print(f"        -> Content '{p_text[:50]}...' skipped (duplicate).")
            else:
                # Nếu chưa có container nào, có thể là phần mở đầu -> thêm vào gốc
                 print(f"DEBUG: No current container, adding orphan content to root list: {p_text[:50]}...")
                 structured_data.append({"level": "orphan", "text": p_text})


    return structured_data

def crawl_and_parse_tvpl(url):
    """Hàm chính: crawl và phân tích cấu trúc"""
    print(f"Đang crawl và phân tích URL: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        print(f"DEBUG: Response status code: {response.status_code}")
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # --- DEBUG: Tìm div.content1 ---
        content_div = soup.find('div', class_='content1')
        if content_div:
            print("DEBUG: Đã tìm thấy div.content1!")
            # print(f"DEBUG: HTML bên trong div.content1 (đầu): {str(content_div)[:500]}")
            # paragraphs_debug = content_div.find_all('p') # Tìm tất cả <p>
            # print(f"DEBUG: Số lượng thẻ <p> (recursive=True): {len(paragraphs_debug)}")
            # if not paragraphs_debug:
            #      print("DEBUG: WARNING - Không có thẻ <p> nào được tìm thấy bên trong div.content1.")
            #      return None
        else:
            print("DEBUG: KHÔNG tìm thấy div.content1.")
            # print(f"DEBUG: Toàn bộ HTML (đầu): {soup.prettify()[:2000]}")
            return None
        # --- KẾT THÚC DEBUG tìm div ---

        print("Bắt đầu phân tích cấu trúc...")
        structured_json_data = parse_legal_structure(content_div)

        if not structured_json_data:
            print("WARNING: Kết quả phân tích cấu trúc rỗng.")
            return None

        # Lưu kết quả JSON
        file_name_part = url.split('/')[-1].replace('.aspx', '')
        save_path = os.path.join(SAVE_DIR, f"{file_name_part}.json")

        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(structured_json_data, f, ensure_ascii=False, indent=4)
            print(f"\nĐã lưu cấu trúc JSON vào: {save_path}")
            return structured_json_data
        except Exception as e:
            print(f"Lỗi khi lưu file JSON: {e}")
            traceback.print_exc()
            return structured_json_data # Vẫn trả về dữ liệu dù không lưu được

    except requests.exceptions.Timeout:
        print("Lỗi: Request timed out.")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"Lỗi HTTP: {e.response.status_code} - {e}")
        if e.response.status_code == 403:
            print("Lỗi 403 Forbidden: Bị chặn bởi website.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Lỗi Request: {e}")
        return None
    except Exception as e:
        print(f"Lỗi không xác định khi xử lý: {e}")
        traceback.print_exc()
        return None

# Chạy hàm crawl và phân tích
if __name__ == "__main__":
    parsed_data = crawl_and_parse_tvpl(TARGET_URL)
    if parsed_data:
        print("\n--- Dữ liệu JSON đã phân tích (OK) ---")
        # print(json.dumps(parsed_data[:1], ensure_ascii=False, indent=2)) # In ra phần tử đầu tiên
    else:
        print("\n--- Quá trình crawl và phân tích thất bại hoặc không có dữ liệu ---")