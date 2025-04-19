from pymongo import MongoClient
import re
import os
import json
from llama_index.core.schema import Document

# Thiết lập MongoDB
def get_mongo_collection():
    mongo_url = os.getenv("mongo_uri_2", "mongodb://localhost:27017/")
    client = MongoClient(mongo_url)
    db = client["final"]
    return db["chunks"]

# Chia json thành các chunk
def parse_articles_as_chunks(json_data, source="unknown.json"):
    documents = []

    def parse_point(point):
        return f"{point.get('letter', '')}. {point.get('content', '')}"

    def parse_clause(clause):
        parts = [f"Khoản {clause.get('number')}: {clause.get('content_full')}"]
        for point in clause.get("points", []):
            parts.append(f"   {parse_point(point)}")
        return "\n".join(parts)

    def parse_article(article, chapter_title=None):
        parts = []
        if chapter_title:
            parts.append(f"{chapter_title}")
        parts.append(f"{article.get('title', '')}")
        for clause in article.get("clauses", []):
            parts.append(parse_clause(clause))
        return "\n\n".join(parts)

    if isinstance(json_data, list):  # multiple chapters
        for chapter in json_data:
            chapter_title = chapter.get("title", "")
            for article in chapter.get("articles", []):
                text = parse_article(article, chapter_title=chapter_title)
                documents.append(Document(
                    text=text,
                    metadata={
                        "title": article.get("title"),
                        "chapter": chapter_title,
                        "source": source
                    }
                ))
    elif isinstance(json_data, dict) and json_data.get("type") == "chapter":
        chapter_title = json_data.get("title", "")
        for article in json_data.get("articles", []):
            text = parse_article(article, chapter_title=chapter_title)
            documents.append(Document(
                text=text,
                metadata={
                    "title": article.get("title"),
                    "chapter": chapter_title,
                    "source": source
                }
            ))
    elif isinstance(json_data, dict) and json_data.get("type") == "article":
        text = parse_article(json_data)
        documents.append(Document(
            text=text,
            metadata={
                "title": json_data.get("title"),
                "source": source
            }
        ))

    return documents

#Chia văn bản txt thành các chunk
def parse_txt_as_chunks(txt_content: str, source="unknown.txt"):
    documents = []

    # Dùng regex để tìm từng "Điều" và nội dung tiếp theo nó
    pattern = r"(Điều\s+\d+\.?.*?)(?=\nĐiều\s+\d+\.|\Z)"  # Bắt đầu bằng "Điều x." đến "Điều y." tiếp theo
    matches = re.findall(pattern, txt_content, flags=re.DOTALL)

    for match in matches:
        lines = match.strip().split("\n", 1)
        title = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        documents.append(Document(
            text=match.strip(),
            metadata={
                "title": title,
                "source": source
            }
        ))

    return documents

# Hàm đọc dữ liệu từ thư mục "data"
def load_documents_from_data_folder(folder_path="data"):
    docs = []
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if filename.endswith(".pdf"):
            docs.extend(SimpleDirectoryReader(input_files=[file_path]).load_data())

        elif filename.endswith(".txt"):
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
                documents = parse_txt_as_chunks(text, source=filename)
                docs.extend(documents)

        elif filename.endswith(".json"):
            with open(file_path, "r", encoding="utf-8") as f:
                json_data = json.load(f)
                documents = parse_articles_as_chunks(json_data, source=filename)
                docs.extend(documents)
    return docs


# Hàm tiền xử lý văn bản: chỉ chuẩn hóa khoảng trắng
def clean_text(text):
    # Loại bỏ khoảng trắng thừa ở đầu, cuối, và giữa các từ
    text = re.sub(r'\s+', ' ', text).strip()
    return text

documents = load_documents_from_data_folder("data")

# Lưu dữ liệu vào MongoDB
def save_to_mongodb(collection, nodes):
    if collection.count_documents({}) == 0:
        print("Chưa có dữ liệu trong MongoDB, tiến hành lưu...")
        documents_to_save = []
        for node in nodes:
            node.text = clean_text(node.text)
            doc = {
                "node_id": node.node_id,
                "text": node.text,
                "metadata": node.metadata
            }
            documents_to_save.append(doc)
        if documents_to_save:
            collection.insert_many(documents_to_save)
            print(f"Đã lưu {len(documents_to_save)} chunks vào MongoDB.")
    else:
        print("Đã có dữ liệu trong MongoDB.")
        count = collection.count_documents({})
        print(f"Số lượng chunks hiện có: {count}")