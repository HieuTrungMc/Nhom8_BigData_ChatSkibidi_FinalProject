import requests # thư viện dùng để gửi request đến server
from bs4 import BeautifulSoup # thư viện dùng để phân tích HTML
import time # thư viện dùng để thêm delay giữa các request
import re # thư viện dùng để xử lý chuỗi
import json # thư viện dùng để lưu file JSON
import os # thư viện dùng để tạo thư mục
from urllib.parse import urlparse # thư viện dùng để phân tích URL
# --- Cấu hình Headers ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
    'Referer': 'https://thuvienphapluat.vn/', # url trang chính chứa các trang con để crawl. -> Chọn trang thuvienphapluat. 
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

# --- Các hàm xử lý giữ nguyên ---
def clean_paragraph_text(text):
    """Làm sạch text: loại bỏ khoảng trắng thừa"""
    text = re.sub(r'\s+', ' ', text) 
    return text.strip() 

def parse_legal_document(html_content): # Hàm phân tích HTML và xây dựng cấu trúc JSON
    """Phân tích HTML và xây dựng cấu trúc JSON"""
    soup = BeautifulSoup(html_content, 'html.parser') 
    content_div = soup.find('div', class_='content1')

    if not content_div:
        print("  Lỗi: Không tìm thấy thẻ div với class 'content1'.") 
        return None

    document_structure = [] 
    current_chapter = None 
    current_article = None 
    current_clause = None 

    paragraphs = content_div.find_all('p') 
    for p_tag in paragraphs:
        p_text = clean_paragraph_text(p_tag.get_text()) 
        if not p_text: continue

        match_chapter = re.match(r"^(Chương\s+[IVXLCDM]+)(.*)", p_text, re.IGNORECASE) 
        match_article = re.match(r"^(Điều\s+\d+)\.(.*)", p_text) 
        match_clause = re.match(r"^(\d+)\.(.*)", p_text)
        match_point = re.match(r"^([a-zđ])\)(.*)", p_text) 
        if match_chapter:
            chapter_title_full = clean_paragraph_text(p_text)
            current_chapter = {"type": "chapter", "title": chapter_title_full, "articles": []}
            document_structure.append(current_chapter) 
            current_article = None 
            current_clause = None 

        elif match_article:
            article_number = match_article.group(1).strip()
            article_title_text = match_article.group(2).strip() 
            article_title_full = f"{article_number}. {article_title_text}".strip()
            current_article = {"type": "article", "title": article_title_full, "clauses": [], "content": []} 
            if current_chapter:
                current_chapter["articles"].append(current_article) 
            else:
                 if not document_structure or document_structure[-1].get("type") != "default_chapter":
                     default_chapter = {"type": "default_chapter", "title": "Nội dung chính", "articles": []}
                     document_structure.append(default_chapter)
                     current_chapter = default_chapter
                 current_chapter["articles"].append(current_article)
            current_clause = None
         
        elif match_clause:
            clause_number = match_clause.group(1).strip()
            clause_text = match_clause.group(2).strip()
            current_clause = {"type": "clause", "number": clause_number, "content_full": clause_text, "points": [], "sub_content": []}
            if current_article:
                current_article["clauses"].append(current_clause)
            else: pass
        elif match_point:
            point_letter = match_point.group(1).strip()
            point_text = match_point.group(2).strip()
            current_point = {"type": "point", "letter": point_letter, "content": point_text}
            if current_clause:
                current_clause["points"].append(current_point)
            elif current_article:
                 if "content" not in current_article: current_article["content"] = []
                 current_article["content"].append(f"{point_letter}) {point_text}")
            else: pass 
        elif not (match_chapter or match_article or match_clause or match_point):
             if current_clause and current_clause["points"]:
                 current_clause["points"][-1]["content"] += "\n" + p_text
             elif current_clause:
                  current_clause["sub_content"].append(p_text)
             elif current_article:
                  current_article["content"].append(p_text)
             else: pass 

    return document_structure

def crawl_and_save_json(url, save_path): # Hàm crawl và lưu kết quả thành file JSON cho một URL
    """Thực hiện crawl và lưu kết quả thành file JSON cho một URL"""
    print(f"  Bắt đầu xử lý: {url}")
    try:
        # Gửi request đến URL và lấy nội dung trang
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status() # Ném ra lỗi nếu trả về lỗi HTTP

        parsed_data = parse_legal_document(response.content) # Phân tích nội dung trang và xây dựng cấu trúc JSON   

        if parsed_data:
            try:
                save_dir = os.path.dirname(save_path)
                if save_dir: os.makedirs(save_dir, exist_ok=True)
                with open(save_path, 'w', encoding='utf-8') as f:
                    json.dump(parsed_data, f, ensure_ascii=False, indent=2)
                print(f"    Thành công: Đã lưu vào {save_path}")
                return True
            except Exception as e:
                print(f"    Lỗi khi lưu file JSON '{save_path}': {e}")
                return False
        else:
            print(f"    Thất bại: Không phân tích được dữ liệu từ {url}")
            return False

    except requests.exceptions.Timeout:
        print(f"    Lỗi: Request timed out cho {url}.")
        return False
    except requests.exceptions.HTTPError as e:
        print(f"    Lỗi HTTP {e.response.status_code} cho {url}: {e}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"    Lỗi Request cho {url}: {e}")
        return False
    except Exception as e:
        print(f"    Lỗi không xác định cho {url}: {e}")
        return False

# --- Hàm tạo tên file từ URL ---
def generate_filename_from_url(url): # Hàm tạo tên file hợp lệ từ URL
    """Tạo tên file hợp lệ từ URL"""
    try:
        path = urlparse(url).path
        base = os.path.basename(path)
        filename_part = os.path.splitext(base)[0]
        safe_filename = re.sub(r'[^\w\-]+', '_', filename_part)
        safe_filename = safe_filename[:100] 
        return f"{safe_filename}.json"
    except Exception as e:
        print(f"Warning: Không thể parse URL để tạo tên file ({e}). Sử dụng hash.")
        import hashlib
        return f"doc_{hashlib.md5(url.encode()).hexdigest()[:10]}.json"

# --- Chạy chương trình ---
if __name__ == "__main__":
    # --- DANH SÁCH CÁC URL CẦN CRAWL ---
    URLS_TO_CRAWL = [
        "https://thuvienphapluat.vn/van-ban/Giao-thong-Van-tai/Nghi-dinh-168-2024-ND-CP-xu-phat-vi-pham-hanh-chinh-an-toan-giao-thong-duong-bo-619502.aspx", # Nghị định 168 (Giao thông)
        "https://thuvienphapluat.vn/van-ban/Cong-nghe-thong-tin/Nghi-dinh-147-2024-ND-CP-quan-ly-cung-cap-su-dung-dich-vu-Internet-thong-tin-tren-mang-480755.aspx", #Nghị định 147 (Internet)
        # "https://thuvienphapluat.vn/van-ban/So-huu-tri-tue/Luat-So-huu-tri-tue-sua-doi-2022-458435.aspx", # Luật sở hữu trí tuệ
        # "https://thuvienphapluat.vn/van-ban/Cong-nghe-thong-tin/Luat-Giao-dich-dien-tu-2023-20-2023-QH15-513347.aspx", # luật giao dịch điện tử.
        # "https://thuvienphapluat.vn/van-ban/Cong-nghe-thong-tin/Luat-an-ninh-mang-2018-351416.aspx", # Luật an ninh mạng
        # "https://thuvienphapluat.vn/van-ban/Cong-nghe-thong-tin/Luat-cong-nghe-thong-tin-2006-67-2006-QH11-12987.aspx", # Luật công nghệ thông tin
        # "https://thuvienphapluat.vn/van-ban/Trach-nhiem-hinh-su/Luat-Phong-chong-ma-tuy-2021-445185.aspx", # Luật phòng chống ma tuý
        # "https://thuvienphapluat.vn/van-ban/Van-hoa-Xa-hoi/Luat-Phong-chong-bao-luc-gia-dinh-2022-490095.aspx" #Luật phòng chống bạo lực gia đình

        # "https://..."
    ]

    # --- THƯ MỤC LƯU TRỮ FILE JSON ---
    # Lưu vào thư mục con 'legal_json' bên trong '../data' để gọn gàng hơn
    SAVE_DIRECTORY_JSON = "../data" # Đổi tên thư mục lưu file json
    os.makedirs(SAVE_DIRECTORY_JSON, exist_ok=True) # Tạo thư mục nếu chưa có
    print(f"Các file JSON sẽ được lưu vào: {os.path.abspath(SAVE_DIRECTORY_JSON)}")

    total_urls = len(URLS_TO_CRAWL)
    success_count = 0
    fail_count = 0
    skip_count = 0

    print(f"\nBắt đầu crawl {total_urls} văn bản...")

    # --- LẶP QUA TỪNG URL ---
    for i, target_url in enumerate(URLS_TO_CRAWL):
        print(f"\n--- [{i+1}/{total_urls}] Đang xử lý URL: {target_url} ---")

        # Tạo tên file đích
        base_filename = generate_filename_from_url(target_url)
        full_save_path = os.path.join(SAVE_DIRECTORY_JSON, base_filename)

        # (Tùy chọn) Kiểm tra xem file đã tồn tại chưa để bỏ qua
        if os.path.exists(full_save_path):
            print(f"  Thông tin: File '{full_save_path}' đã tồn tại. Bỏ qua.")
            skip_count += 1
            continue # Chuyển sang URL tiếp theo

        # Gọi hàm crawl và lưu cho URL hiện tại
        success = crawl_and_save_json(target_url, full_save_path)

        if success:
            success_count += 1
        else:
            fail_count += 1

        # --- QUAN TRỌNG: Thêm độ trễ giữa các request đến cùng domain ---
        delay_seconds = 2 # Đặt độ trễ 2-5 giây là hợp lý
        print(f"  Tạm dừng {delay_seconds} giây...")
        time.sleep(delay_seconds)

    # --- In tổng kết ---
    print("\n--- HOÀN TẤT QUÁ TRÌNH CRAWL ---")
    print(f"Tổng số URL cần xử lý: {total_urls}")
    print(f"Số lượng crawl thành công: {success_count}")
    print(f"Số lượng crawl thất bại: {fail_count}")
    print(f"Số lượng bỏ qua (đã tồn tại): {skip_count}")
    print(f"Dữ liệu đã được lưu tại: {os.path.abspath(SAVE_DIRECTORY_JSON)}")