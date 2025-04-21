from pymongo import MongoClient
import re
import os
import json
from llama_index.core.schema import Document
from llama_index.core import SimpleDirectoryReader
# Thiết lập MongoDB
def get_mongo_collection():
    mongo_url = os.getenv("mongo_url", "mongodb://localhost:27017/")
    client = MongoClient(mongo_url)
    db = client["final"]
    return db["chunks"]

def parse_articles_as_chunks(json_data, source="unknown.json", max_chunk_size=2048):
    documents = []

    def parse_point(point):
        return f"{point.get('letter', '')}. {point.get('content', '')}"

    def create_document(text, article_title, chapter_title=None, clause_number=None):
        metadata = {
            "title": article_title,
            "source": source,
            "chapter": chapter_title,
            "clause": clause_number
        }
        return Document(text=text, metadata=metadata)

    def split_text(text, max_size=max_chunk_size):
        """Split text into smaller chunks based on sentences while respecting max_size"""
        if len(text) <= max_size:
            return [text]
        
        # Split by sentences (assuming Vietnamese text)
        sentences = text.split('. ')
        chunks = []
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # Add period back if it was removed during split
            if not sentence.endswith('.'):
                sentence += '.'
                
            sentence_length = len(sentence)
            
            if current_length + sentence_length > max_size and current_chunk:
                # Join current chunk and add to chunks
                chunks.append(' '.join(current_chunk))
                current_chunk = [sentence]
                current_length = sentence_length
            else:
                current_chunk.append(sentence)
                current_length += sentence_length
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
            
        return chunks

    def parse_clause(clause, article_title, chapter_title=None):
        # Start with clause header
        base_text = f"Khoản {clause.get('number')}: {clause.get('content_full')}"
        
        # Add points if they exist
        points_text = ""
        for point in clause.get("points", []):
            points_text += f"\n   {parse_point(point)}"
            
        # Combine and create context header
        context_header = f"{chapter_title + ' - ' if chapter_title else ''}{article_title}\n"
        full_text = base_text + points_text
        
        # Split into smaller chunks if needed
        chunks = split_text(full_text)
        
        # Create documents for each chunk
        for i, chunk in enumerate(chunks):
            # Add context header to each chunk
            chunk_text = f"{context_header}{chunk}"
            documents.append(create_document(
                text=chunk_text,
                article_title=article_title,
                chapter_title=chapter_title,
                clause_number=f"{clause.get('number')} (part {i+1}/{len(chunks)})"
            ))

    def process_article(article, chapter_title=None):
        article_title = article.get('title', '')
        for clause in article.get("clauses", []):
            parse_clause(clause, article_title, chapter_title)

    # Process based on input type
    if isinstance(json_data, list):  # multiple chapters
        for chapter in json_data:
            chapter_title = chapter.get("title", "")
            for article in chapter.get("articles", []):
                process_article(article, chapter_title)
    elif isinstance(json_data, dict):
        if json_data.get("type") == "chapter":
            chapter_title = json_data.get("title", "")
            for article in json_data.get("articles", []):
                process_article(article, chapter_title)
        elif json_data.get("type") == "article":
            process_article(json_data)

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
def load_documents_from_data_folder(folder_path="../data"):
    docs = []
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if filename.endswith(".pdf"):
            docs.extend(SimpleDirectoryReader(input_files=[file_path]).load_data(num_workers=4))

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

# Lưu dữ liệu vào MongoDB
def save_to_mongodb(collection, nodes):
    if collection.count_documents({}) == 0:
        print("Chưa có dữ liệu trong MongoDB, tiến hành lưu...")
        documents_to_save = []
        for node in nodes:
            #print("===================================")
            #print(node.id_)
            #node.text_resource.text = clean_text(node.text_resource.text)
            doc = {
                "node_id": node.id_,
                "text": node.text_resource.text,
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
def startMongo():
    documents = load_documents_from_data_folder("../data")
    return documents