import os
import json
import re
import logging
import sys
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ConfigurationError, OperationFailure
from dotenv import load_dotenv

# --- Cấu hình Logging ---
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Load Biến Môi trường ---
load_dotenv('../.env') # Load file .env từ thư mục cha

MONGO_URI = os.getenv("mongodb_atlat")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "legal_data_db")
# Đặt tên collection mới cho các chunks đã xử lý này
MONGODB_COLLECTION_PROCESSED = "chat_skibidi_chunks" # tên collections lưu các chunks

# Kiểm tra biến môi trường
if not MONGO_URI:
    logging.error("MONGO_URI không được thiết lập trong file .env")
    sys.exit(1)

# --- Đường dẫn Dữ liệu ---
# Script này nằm trong 'src', data nằm ở '../data'
JSON_DATA_DIR = "../data"

# --- Hàm xử lý ---
def clean_text(text):
    """Làm sạch text cơ bản"""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def process_json_file_to_chunks(filepath, filename):
    """Đọc 1 file JSON, phân tích và trả về list các chunk (dạng dict)"""
    chunks = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f) # data là list các chương
    except json.JSONDecodeError:
        logging.error(f"Lỗi giải mã JSON trong file: {filename}")
        return []
    except Exception as e:
        logging.error(f"Lỗi khi đọc file {filename}: {e}")
        return []

    # Lấy URL (nếu có) từ metadata chung của văn bản (giả sử có trong chương đầu)
    source_url = "N/A"
    if data and isinstance(data, list) and data[0].get("url"):
         source_url = data[0]["url"]

    current_chapter_title = "Không rõ chương"

    for chapter in data:
        chapter_title = chapter.get("title", "Không rõ chương")
        if chapter.get("type") == "chapter": # Cập nhật tên chương hiện tại
             current_chapter_title = chapter_title
        elif chapter.get("type") == "default_chapter": # Chương mặc định
             current_chapter_title = chapter.get("title", "Nội dung chính")

        for article in chapter.get("articles", []):
            article_title = article.get("title", "Không rõ điều")
            article_text_parts = [article_title] # Bắt đầu text của chunk bằng tiêu đề Điều

            # Thêm nội dung chung của Điều (nếu có)
            article_text_parts.extend(article.get("content", []))

            # Duyệt qua các Khoản và Điểm
            for clause in article.get("clauses", []):
                clause_full_text = f"Khoản {clause.get('number', '')}: {clause.get('content_full', '')}"
                article_text_parts.append(clause_full_text)
                # Thêm nội dung con của Khoản (nếu có)
                article_text_parts.extend(clause.get("sub_content", []))
                for point in clause.get("points", []):
                    point_text = f"{point.get('letter', '')}) {point.get('content', '')}"
                    article_text_parts.append(point_text)

            # Kết hợp thành text hoàn chỉnh cho Điều này
            full_article_text = "\n".join(article_text_parts)

            # Tạo dictionary cho chunk này (đại diện cho một Điều)
            chunk_doc = {
                "text": full_article_text,
                "metadata": {
                    "source_file": filename,
                    "source_url": source_url,
                    "chapter_title": current_chapter_title,
                    "article_title": article_title,
                    # Bạn có thể thêm các metadata khác nếu cần
                    # "doc_id": ... # Nếu có ID duy nhất cho văn bản gốc
                }
                # Không cần trường _id ở đây, MongoDB sẽ tự tạo
            }
            chunks.append(chunk_doc)

    return chunks

# --- Hàm chính ---
def main():
    logging.info("Bắt đầu quá trình xử lý JSON và lưu vào MongoDB...")

    # --- Kết nối MongoDB ---
    client = None # Khởi tạo client là None
    try:
        logging.info(f"Đang kết nối tới MongoDB Atlas (DB: {MONGODB_DATABASE})...")
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000) # Timeout 5 giây
        # Lệnh 'ismaster' (hoặc tương đương) sẽ kiểm tra kết nối
        client.admin.command('ismaster')
        logging.info("Kết nối MongoDB Atlas thành công.")
        db = client[MONGODB_DATABASE]
        collection = db[MONGODB_COLLECTION_PROCESSED]
        # (Tùy chọn) Tạo index trên metadata để tìm kiếm nhanh hơn sau này
        collection.create_index([("metadata.source_file", 1)])
        collection.create_index([("metadata.article_title", 1)])

    except (ConnectionFailure, ConfigurationError, OperationFailure) as e:
        logging.error(f"Lỗi kết nối hoặc xác thực MongoDB: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Lỗi không xác định khi kết nối MongoDB: {e}")
        sys.exit(1)

    # --- Xử lý các file JSON ---
    if not os.path.exists(JSON_DATA_DIR):
        logging.error(f"Thư mục dữ liệu JSON không tồn tại: {JSON_DATA_DIR}")
        if client: client.close()
        sys.exit(1)

    total_files = 0
    total_chunks_saved = 0
    processed_files = 0

    for filename in os.listdir(JSON_DATA_DIR):
        if filename.lower().endswith(".json"):
            total_files += 1
            filepath = os.path.join(JSON_DATA_DIR, filename)
            logging.info(f"[{processed_files+1}/{total_files}] Đang xử lý file: {filename}")

            chunks_to_save = process_json_file_to_chunks(filepath, filename)

            if chunks_to_save:
                try:
                    # Sử dụng insert_many để hiệu quả hơn
                    result = collection.insert_many(chunks_to_save)
                    saved_count = len(result.inserted_ids)
                    total_chunks_saved += saved_count
                    logging.info(f"  Đã lưu {saved_count} chunks vào collection '{MONGODB_COLLECTION_PROCESSED}'.")
                    processed_files += 1
                except Exception as e:
                    logging.error(f"  Lỗi khi lưu chunks từ file {filename} vào MongoDB: {e}")
            else:
                logging.warning(f"  Không có chunk nào được tạo từ file {filename}.")
                processed_files += 1 # Vẫn tính là đã xử lý file này (dù không có chunk)

    logging.info("--- Hoàn thành xử lý ---")
    logging.info(f"Tổng số file JSON được tìm thấy: {total_files}")
    logging.info(f"Tổng số file đã xử lý: {processed_files}")
    logging.info(f"Tổng số chunks đã lưu vào MongoDB: {total_chunks_saved}")

    # Đóng kết nối MongoDB
    if client:
        client.close()
        logging.info("Đã đóng kết nối MongoDB.")

if __name__ == "__main__":
    main()