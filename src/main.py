from llama_index.core import SimpleDirectoryReader
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core import Settings
# Import Gemini
from llama_index.llms.gemini import Gemini
from llama_index.embeddings.gemini import GeminiEmbedding
# Import các thành phần RAG
from llama_index.core import SummaryIndex, VectorStoreIndex 
from llama_index.core.tools import QueryEngineTool
from llama_index.core.query_engine.router_query_engine import RouterQueryEngine
from llama_index.core.selectors import LLMSingleSelector
from llama_index.core.schema import TextNode
from mongodb import get_mongo_collection, save_to_mongodb
import re
gemini_api_key = "AIzaSyCP6Xp7zTh9RvP-NSEGPFqvqik_Yy6ni2w"

# Thiết lập MongoDB
collection = get_mongo_collection()

#Đọc tài liệu
documents = SimpleDirectoryReader(input_files=["BigData.pdf"]).load_data()
print(f"Đã tải {len(documents)} tài liệu.")
# Chia tài liệu thành các đoạn nhỏ (node)
splitter = SentenceSplitter(chunk_size=1024)
nodes = splitter.get_nodes_from_documents(documents)
print(f"Đã tạo {len(nodes)} node.")

# Lưu dữ liệu vào MongoDB
save_to_mongodb(collection, nodes)


# Thiết lập mô hình ngôn ngữ và embedding
Settings.llm = Gemini(api_key=gemini_api_key,
model="models/gemini-1.5-pro")
Settings.embed_model = GeminiEmbedding(api_key=gemini_api_key,
model="models/embedding-001")
print("Đã thiết lập mô hình LLM và embedding.")

#Dùng dữ liệu từ mongodb
mongo_nodes = []
for doc in collection.find():
    node = {
        "node_id": doc["node_id"],
        "text": doc["text"],
        "metadata": doc["metadata"]
    }
    mongo_nodes.append(TextNode(node))
    
nodes = mongo_nodes

# Tạo vector index
vector_index = VectorStoreIndex(nodes)
# Tạo summary index
summary_index = SummaryIndex(nodes)
print("Đã tạo các chỉ mục vector và summary")

# Tạo summary query engine
summary_query_engine = summary_index.as_query_engine(
response_mode="tree_summarize",
use_async=True,
)
# Tạo vector query engine
vector_query_engine = vector_index.as_query_engine()

vietnamese_query_engine = vector_index.as_query_engine()

keyword_query_engine = vector_index.as_query_engine( )
print("Đã tạo các query engine.")

# Tạo công cụ tóm tắt
summary_tool = QueryEngineTool.from_defaults(
query_engine=summary_query_engine,
description=("Hữu ích cho các câu hỏi tóm tắt liên quan đến tài liệu."
),
)
# Tạo công cụ tìm kiếm vector
vector_tool = QueryEngineTool.from_defaults(
query_engine=vector_query_engine,
description=(
"Hữu ích để truy xuất thông tin cụ thể từ tài liệu."
),
)

# Tạo công cụ định nghĩa
definition_tool = QueryEngineTool.from_defaults(
query_engine=keyword_query_engine,
description=(
"Hữu ích để truy xuất định nghĩa trong tài liệu."
),
)

# Tạo công cụ dành riêng cho tiếng việt
vietnamese_tool = QueryEngineTool.from_defaults(
query_engine=vietnamese_query_engine,
description=(
"Hữu ích để truy xuất bằng tiếng Việt bên trong tài liệu."
),
)

# Tạo công cụ dành riêng cho các khái niệm
compare_tool = QueryEngineTool.from_defaults(
query_engine=vector_query_engine,
description=(
"Hữu ích để so sánh các khái niệm bên trong tài liệu."
),
)

# Tạo công cụ dành riêng theo thời gian
time_tool = QueryEngineTool.from_defaults(
query_engine=vector_query_engine,
description=(
"Hữu ích để phân tích theo thời gian."
),
)



print("Đã tạo các công cụ.")


# Tạo router query engine
query_engine = RouterQueryEngine(
selector=LLMSingleSelector.from_defaults(),
query_engine_tools=[
summary_tool,
vector_tool,
definition_tool,
compare_tool,
time_tool,
vietnamese_tool
],
verbose=True)
print("Đã tạo router query engine summary tool.")
