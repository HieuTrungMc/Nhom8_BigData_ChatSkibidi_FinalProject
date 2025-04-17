from pymongo import MongoClient
import re

# Thiết lập MongoDB
def get_mongo_collection():
    mongo_url = "mongodb://hieutrungmc:verysafebozo@cluster0-shard-00-00.0bbrp.mongodb.net:27017,cluster0-shard-00-01.0bbrp.mongodb.net:27017,cluster0-shard-00-02.0bbrp.mongodb.net:27017/?ssl=true&replicaSet=atlas-4lkfbx-shard-0&authSource=admin&retryWrites=true&w=majority&appName=Cluster0"
    client = MongoClient(mongo_url)
    db = client["final"]
    return db["chunks"]

# Hàm tiền xử lý văn bản
def clean_text(text):
    unwanted_chars = r'[@#$%^&*()_+={}\[\]:;"\'<>/?|\\~`]'
    text = re.sub(unwanted_chars, '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

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