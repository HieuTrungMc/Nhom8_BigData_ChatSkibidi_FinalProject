from llama_index.core import SimpleDirectoryReader
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core import Settings
# Import Gemini
from llama_index.llms.gemini import Gemini
from llama_index.embeddings.gemini import GeminiEmbedding
# Import các thành phần RAG
from llama_index.core import SummaryIndex, VectorStoreIndex, KeywordTableIndex
from llama_index.core.tools import QueryEngineTool
from llama_index.core.query_engine.router_query_engine import RouterQueryEngine
from llama_index.core.selectors import LLMSingleSelector
from llama_index.core.schema import TextNode
from llama_index.readers.file import PDFReader, UnstructuredReader
from mongodb import get_mongo_collection, save_to_mongodb, startMongo
from dotenv import load_dotenv
import os
import re
import time
from flask import Flask, request, jsonify
from flask_cors import CORS

# Initialize Flask application
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Global variables for engines
query_engine = None
vector_query_engine = None
hybrid_query_engine = None

class SimpleHybridQueryEngine:
    def __init__(self, vector_query_engine, bm25_query_engine, alpha=0.5):
        self.vector_query_engine = vector_query_engine
        self.bm25_query_engine = bm25_query_engine
        self.alpha = alpha  # trọng số giữa vector và bm25

    def query(self, question):
        # Lấy kết quả từ hai engine
        vector_result = self.vector_query_engine.query(question)
        bm25_result = self.bm25_query_engine.query(question)

        # Lấy các node và điểm số (nếu có)
        vector_nodes = getattr(vector_result, "source_nodes", [])
        bm25_nodes = getattr(bm25_result, "source_nodes", [])

        # Gộp node theo node_id, tính điểm tổng hợp
        node_scores = {}
        for node in vector_nodes:
            node_scores[node.node.node_id] = self.alpha * (node.score if hasattr(node, "score") and node.score else 1.0)
        for node in bm25_nodes:
            if node.node.node_id in node_scores:
                node_scores[node.node.node_id] += (1 - self.alpha) * (node.score if hasattr(node, "score") and node.score else 1.0)
            else:
                node_scores[node.node.node_id] = (1 - self.alpha) * (node.score if hasattr(node, "score") and node.score else 1.0)

        # Sắp xếp node theo điểm số tổng hợp
        sorted_node_ids = sorted(node_scores, key=node_scores.get, reverse=True)
        # Lấy node gốc từ vector_nodes hoặc bm25_nodes
        all_nodes = {n.node.node_id: n for n in vector_nodes + bm25_nodes}
        merged_nodes = [all_nodes[nid] for nid in sorted_node_ids]

        # Tạo một response giả lập (giống như response của query_engine gốc)
        class HybridResponse:
            def __init__(self, merged_nodes):
                self.response = "\n\n".join([n.node.text for n in merged_nodes[:3]])  # lấy top 3 node
                self.source_nodes = merged_nodes[:3]
                self.metadata = {"hybrid": True}

        return HybridResponse(merged_nodes)

def initialize_rag_system():
    global query_engine, vector_query_engine, hybrid_query_engine

    load_dotenv()
    gemini_keys = [
        os.getenv("GEMINI_API_KEY_1"),
        os.getenv("GEMINI_API_KEY_2"),
        os.getenv("GEMINI_API_KEY_3"),
    ]
    # Remove None values
    gemini_keys = [k for k in gemini_keys if k]

    collection = get_mongo_collection()

    # Nếu đã có index, load lại thay vì build mới
    if os.path.exists("vector_index.json") and os.path.exists("summary_index.json"):
        print("Loading indexes from disk...")
        vector_index = VectorStoreIndex.load_from_disk("vector_index.json")
        summary_index = SummaryIndex.load_from_disk("summary_index.json")
    else:
        print("Building indexes from scratch...")

        nodes = startMongo()
        save_to_mongodb(collection, nodes)
        mongo_nodes = []
        for doc in collection.find():
            print(len(doc["text"]))
            if(len(doc["text"]) < 10000):
                mongo_nodes.append(TextNode(
                    node_id=doc["node_id"],
                    text=doc["text"],
                    metadata=doc["metadata"]
                ))
        nodes = mongo_nodes


    print("Initializing RAG system...")
    start_time = time.time()

    # Thiết lập mô hình ngôn ngữ và embedding
    Settings.llm = Gemini(api_key=gemini_keys[0], model="models/gemini-1.5-flash")
    Settings.embed_model = GeminiEmbedding(api_key=gemini_keys[0], model="models/gemini-embedding-exp")
    vector_index = VectorStoreIndex(nodes)
    print("done vector.")

    Settings.llm = Gemini(api_key=gemini_keys[1], model="models/gemini-1.5-flash")
    Settings.embed_model = GeminiEmbedding(api_key=gemini_keys[1], model="models/gemini-embedding-exp")
    summary_index = SummaryIndex(nodes)
    print("done summary.")

    # Settings.llm = Gemini(api_key=gemini_keys[2], model="models/gemini-2.0-flash")
    # Settings.embed_model = GeminiEmbedding(api_key=gemini_keys[2], model="models/text-embedding-004")
    # keyword_index = KeywordTableIndex(nodes)
    print("Đã thiết lập mô hình LLM và embedding.")

    # Tạo vector query engine
    vector_query_engine = vector_index.as_query_engine(similarity_top_k=5)

    #vietnamese_query_engine = vector_index.as_query_engine()

    #keyword_query_engine = vector_index.as_query_engine()
    print("Đã tạo các query engine.")

    bm25_query_engine = summary_index.as_query_engine()
    hybrid_query_engine = SimpleHybridQueryEngine(
        vector_query_engine=vector_query_engine,
        bm25_query_engine=bm25_query_engine,
        alpha=0.5  # trọng số giữa vector và keyword, có thể điều chỉnh
    )

    # Lưu lại index để lần sau load nhanh
    # Tạo summary query engine
    summary_query_engine = summary_index.as_query_engine(
    response_mode="tree_summarize",
    use_async=True,
    )
    # Tạo công cụ tóm tắt
    summary_tool = QueryEngineTool.from_defaults(
        query_engine=summary_query_engine,
        description=(
            "Dùng cho các câu hỏi yêu cầu tóm tắt toàn bộ hoặc một phần tài liệu. "
            "Ví dụ: 'Tóm tắt nội dung chính của tài liệu này', 'Tóm tắt chương 2', 'Tóm tắt các điểm quan trọng'. "
            "Các từ khóa: tóm tắt, tổng hợp, overview, summary, main points."
        ),
    )
    # Tạo công cụ tìm kiếm vector
    vector_tool = QueryEngineTool.from_defaults(
        query_engine=vector_query_engine,
        description=(
            "Dùng cho các câu hỏi cần truy xuất thông tin chi tiết, tìm kiếm nội dung cụ thể trong tài liệu. "
            "Ví dụ: 'Điều 5 quy định gì?', 'Ai là tác giả?', 'Ngày ban hành là khi nào?', 'Nội dung của Điều 10'. "
            "Các từ khóa: tìm kiếm, tra cứu, chi tiết, thông tin, search, find, locate."
        ),
    )

    # Tạo công cụ định nghĩa
    definition_tool = QueryEngineTool.from_defaults(
        query_engine=vector_query_engine,
        description=(
            "Dùng cho các câu hỏi về định nghĩa, giải thích thuật ngữ, khái niệm trong tài liệu. "
            "Ví dụ: 'Định nghĩa dữ liệu cá nhân là gì?', 'Giải thích khái niệm an toàn thông tin', 'Thuật ngữ này nghĩa là gì?'. "
            "Các từ khóa: định nghĩa, khái niệm, thuật ngữ, definition, explain, meaning."
        ),
    )

    # Tạo công cụ dành riêng cho tiếng việt
    vietnamese_tool = QueryEngineTool.from_defaults(
        query_engine=vector_query_engine,
        description=(
            "Dùng cho các câu hỏi bằng tiếng Việt hoặc yêu cầu trả lời bằng tiếng Việt. "
            "Ví dụ: 'Giải thích bằng tiếng Việt', 'Trả lời bằng tiếng Việt', 'Nội dung này là gì?'. "
            "Các từ khóa: tiếng Việt, Vietnamese, trả lời bằng tiếng Việt."
        ),
    )

    # Tạo công cụ dành riêng cho các khái niệm
    compare_tool = QueryEngineTool.from_defaults(
        query_engine=vector_query_engine,
        description=(
            "Dùng cho các câu hỏi so sánh giữa các điều khoản, khái niệm, hoặc nội dung khác nhau trong tài liệu. "
            "Ví dụ: 'So sánh Điều 5 và Điều 6', 'Khác biệt giữa bảo mật và an toàn thông tin', 'Điểm giống và khác nhau giữa hai khái niệm'. "
            "Các từ khóa: so sánh, khác biệt, giống nhau, comparison, difference, similarity."
        ),
    )

    # Tạo công cụ dành riêng theo thời gian
    time_tool = QueryEngineTool.from_defaults(
        query_engine=vector_query_engine,
        description=(
            "Dùng cho các câu hỏi liên quan đến thời gian, mốc thời gian, hiệu lực, hoặc các sự kiện theo trình tự thời gian. "
            "Ví dụ: 'Khi nào luật có hiệu lực?', 'Các mốc thời gian quan trọng', 'Thời gian ban hành là khi nào?'. "
            "Các từ khóa: thời gian, mốc thời gian, hiệu lực, date, timeline, when."
        ),
    )

    # Tạo công cụ dành riêng cho tình huống
    situation_tool = QueryEngineTool.from_defaults(
        query_engine=vector_query_engine,
        description=(
            "Dùng cho các câu hỏi về tình huống thực tế, áp dụng luật vào trường hợp cụ thể, phân tích case study, ví dụ thực tiễn. "
            "Ví dụ: 'Nếu tôi làm mất giấy tờ thì bị xử lý thế nào?', 'Trong trường hợp này thì Điều 5 có áp dụng không?', "
            "'Một người dưới 18 tuổi vi phạm thì xử lý ra sao?', 'Tình huống: ... hãy tư vấn pháp lý'. "
            "Các từ khóa: tình huống, trường hợp, case, scenario, áp dụng, xử lý, ví dụ thực tế, pháp lý thực tiễn."
        ),
    )

    # Tạo công cụ dành riêng cho quy trình
    procedure_tool = QueryEngineTool.from_defaults(
        query_engine=vector_query_engine,
        description=(
            "Dùng cho các câu hỏi về quy trình, thủ tục pháp lý, các bước thực hiện theo luật. "
            "Ví dụ: 'Thủ tục đăng ký kết hôn như thế nào?', 'Các bước xin cấp lại giấy tờ', 'Quy trình xử lý vi phạm'. "
            "Các từ khóa: thủ tục, quy trình, procedure, process, các bước, hướng dẫn."
        ),
    )

    # Tạo công cụ dành riêng cho mức phạt
    penalty_tool = QueryEngineTool.from_defaults(
        query_engine=vector_query_engine,
        description=(
            "Dùng cho các câu hỏi về mức phạt, hình thức xử lý, chế tài theo luật. "
            "Ví dụ: 'Mức phạt cho hành vi này là bao nhiêu?', 'Bị xử lý như thế nào?', 'Chế tài áp dụng ra sao?'. "
            "Các từ khóa: mức phạt, xử lý, chế tài, penalty, sanction, xử phạt."
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
            vietnamese_tool,
            situation_tool,  # Thêm tool tình huống vào đây
            procedure_tool,  # Thêm tool quy trình vào đây
            penalty_tool,  # Thêm tool mức phạt vào đây
        ],
        verbose=True)
    
    end_time = time.time()
    print(f"Đã tạo router query engine, initialization time: {end_time - start_time:.2f} seconds")
    return query_engine

 #API endpoint for asking questions
@app.route('/chatskibidi/ask', methods=['GET'])
def ask_question():
    global query_engine
   
     #Get question from query parameter
    question = request.args.get('question', '')
   
    if not question:
        return jsonify({
            "status": "error",
            "message": "No question provided",
            "error": "Missing 'question' parameter"
        }), 400
   
    try:
         #Time the query
        start_time = time.time()
        response = query_engine.query(question)
        end_time = time.time()
       
         #Prepare response data
        response_data = {
            "status": "success",
            "question": question,
            "answer": response.response,
            "debug": {
                "response_time": f"{end_time - start_time:.2f} seconds",
                "source_nodes": [],
                "tool_used": response.metadata.get("tool_name", "Unknown") if hasattr(response, "metadata") else "Unknown"
            }
        }
       
        # Include source nodes if available
        if hasattr(response, "source_nodes"):
            for i, node in enumerate(response.source_nodes):
                response_data["debug"]["source_nodes"].append({
                    "index": i,
                    "text": node.node.text[:200] + "..." if len(node.node.text) > 200 else node.node.text,
                    "score": node.score if hasattr(node, "score") else None,
                    "source": node.node.metadata.get("source", "Unknown")
                })
       
        return jsonify(response_data)
       
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Error processing question",
            "error": str(e)
        }), 500

@app.route('/chatskibidi/ask-vector', methods=['GET'])
def ask_vector():
    global vector_query_engine
    question = request.args.get('question', '')
    if not question:
        return jsonify({"status": "error", "message": "No question provided"}), 400
    try:
        start_time = time.time()
        response = vector_query_engine.query(question)
        end_time = time.time()
        response_data = {
            "status": "success",
            "question": question,
            "answer": response.response,
            "debug": {
                "response_time": f"{end_time - start_time:.2f} seconds",
                "source_nodes": [
                    {
                        "index": i,
                        "text": node.node.text[:200] + "..." if len(node.node.text) > 200 else node.node.text,
                        "score": node.score if hasattr(node, "score") else None,
                        "source": node.node.metadata.get("source", "Unknown")
                    }
                    for i, node in enumerate(getattr(response, "source_nodes", []))
                ]
            }
        }
        return jsonify(response_data)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/chatskibidi/ask-hybrid', methods=['GET'])
def ask_hybrid():
    global hybrid_query_engine
    question = request.args.get('question', '')
    if not question:
        return jsonify({"status": "error", "message": "No question provided"}), 400
    try:
        start_time = time.time()
        response = hybrid_query_engine.query(question)
        end_time = time.time()
        response_data = {
            "status": "success",
            "question": question,
            "answer": response.response,
            "debug": {
                "response_time": f"{end_time - start_time:.2f} seconds",
                "source_nodes": [
                    {
                        "index": i,
                        "text": node.node.text + "..." if len(node.node.text) > 200 else node.node.text,
                        "score": node.score if hasattr(node, "score") else None,
                        "source": node.node.metadata.get("source", "Unknown")
                    }
                    for i, node in enumerate(getattr(response, "source_nodes", []))
                ]
            }
        }
        return jsonify(response_data)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500 

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "ok",
        "message": "Server is running",
        "timestamp": time.time()
    })

if __name__ == "__main__":
    # Initialize the RAG system before starting the server
    query_engine = initialize_rag_system()
    # Start Flask server
    app.run(host='0.0.0.0', port=3000, debug=False)
