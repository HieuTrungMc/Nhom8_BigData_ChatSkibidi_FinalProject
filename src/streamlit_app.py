import streamlit as st
import requests
import json
from pymongo import MongoClient
from datetime import datetime
import os
from dotenv import load_dotenv
import uuid
import base64

# Load environment variables
load_dotenv()
FLASK_URL = os.getenv("FLASK_URL", "http://localhost:3000")
MONGO_URL = os.getenv("mongo_url", "mongodb://localhost:27017/")

# Initialize MongoDB client
def get_mongo_chat_collection():
    client = MongoClient(MONGO_URL)
    db = client["final"]
    return db["chat_history"]

# Function to save chat to MongoDB
def save_chat_to_mongodb(session_id, user_message, bot_response, engine_used):
    collection = get_mongo_chat_collection()
    chat_doc = {
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat(),
        "user_message": user_message,
        "bot_response": bot_response,
        "engine_used": engine_used
    }
    collection.insert_one(chat_doc)

# Function to load chat history from MongoDB
def load_chat_history(session_id):
    collection = get_mongo_chat_collection()
    chats = collection.find({"session_id": session_id}).sort("timestamp", 1)
    return list(chats)

# Function to clear chat history
def clear_chat_history(session_id):
    collection = get_mongo_chat_collection()
    collection.delete_many({"session_id": session_id})

# Function to get context from recent messages
def get_context(session_id, max_messages=3):
    chats = load_chat_history(session_id)
    recent_chats = chats[-max_messages:]  # Get last max_messages
    context = ""
    for chat in recent_chats:
        context += f"User: {chat['user_message']}\nBot: {chat['bot_response']}\n"
    return context

# Function to query the Flask API
def query_api(question, engine, session_id):
    endpoint_map = {
        "Default": "/chatskibidi/ask",
        "Vector": "/chatskibidi/ask-vector",
        "Hybrid": "/chatskibidi/ask-hybrid"
    }
    endpoint = endpoint_map.get(engine, "/chatskibidi/ask")

    # Add context to the question
    context = get_context(session_id)
    full_query = f"{context}\nCurrent Question: {question}" if context else question

    try:
        response = requests.get(
            f"{FLASK_URL}{endpoint}",
            params={"question": full_query}
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"status": "error", "message": str(e)}

# Function to set background image
def set_background(image_file):
    with open(image_file, "rb") as f:
        img_data = f.read()
    b64_encoded = base64.b64encode(img_data).decode()
    return f"""
    <style>
    .stApp {{
        background-image: url(data:image/png;base64,{b64_encoded});
        background-size: cover;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }}
    </style>
    """

# Custom CSS for dark mode and styling
st.markdown("""
    <style>
    /* Dark mode styling */
    .stApp {
        color: #E0E0E0;
    }
    .stTextInput > div > div > input {
        background-color: rgba(45, 45, 45, 0.9);
        color: #E0E0E0;
        border: 1px solid #4A4A4A;
        border-radius: 8px;
        padding: 10px;
    }
    .stButton > button {
        background-color: rgba(58, 58, 58, 0.9);
        color: #E0E0E0;
        border: 1px solid #4A4A4A;
        border-radius: 8px;
        padding: 8px 16px;
        transition: background-color 0.3s;
    }
    .stButton > button:hover {
        background-color: rgba(74, 74, 74, 0.9);
    }
    .stSelectbox > div > div {
        background-color: rgba(45, 45, 45, 0.9);
        color: #E0E0E0;
        border: 1px solid #4A4A4A;
        border-radius: 8px;
    }
    .chat-message {
        padding: 10px;
        margin: 5px 0;
        border-radius: 8px;
        max-width: 80%;
    }
    .user-message {
        background-color: rgba(58, 58, 58, 0.9);
        margin-left: auto;
        text-align: right;
    }
    .bot-message {
        background-color: rgba(45, 45, 45, 0.9);
        margin-right: auto;
    }
    .sidebar .sidebar-content {
        background-color: rgba(37, 37, 37, 0.9);
    }
            
    .block-container{
        padding: 10px;
        margin-top: 10px;
        background-color: #FFFFFF;
    }

    .stMarkdown p{
        color: #000000;
    }

    </style>
""", unsafe_allow_html=True)

# Streamlit app
def main():
    # Set background image if exists
    bg_image = "background1.png"  # You can change this to your image path
    if os.path.exists(bg_image):
        st.markdown(set_background(bg_image), unsafe_allow_html=True)
        #unsafely allow html là để cho phép html vào trong streamlit
        
    st.title("📚 ChatSkibidi")
    st.markdown("Tôi là chatskibidi, hãy hỏi tôi bất cứ điều gì về luật pháp, tôi sẽ giúp bạn tìm đc câu trả lời.")

    # Initialize session state
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Sidebar for settings
    with st.sidebar:
        st.header("Settings")
        engine = st.selectbox(
            "Query Engine",
            ["Default", "Vector", "Hybrid"],
            help="Choose the query engine to use."
        )
        if st.button("Clear Chat History"):
            clear_chat_history(st.session_state.session_id)
            st.session_state.chat_history = []
            st.success("Chat history cleared!")

    # Load chat history from MongoDB
    st.session_state.chat_history = load_chat_history(st.session_state.session_id)

    # Display chat history
    chat_container = st.container()
    with chat_container:
        for chat in st.session_state.chat_history:
            # User message
            st.markdown(
                f'<div class="chat-message user-message">{chat["user_message"]}</div>',
                unsafe_allow_html=True
            )
            # Bot response
            st.markdown(
                f'<div class="chat-message bot-message">{chat["bot_response"]}<br><small>Engine: {chat["engine_used"]}</small></div>',
                unsafe_allow_html=True
            )

    # Input box for new question
    with st.form(key="chat_form", clear_on_submit=True):
        question = st.text_input("Hãy hỏi tôi ở đây:", placeholder="Nhập câu hỏi của bạn...")
        submit_button = st.form_submit_button("Gửi")

        if submit_button and question:
            # Query the API
            response = query_api(question, engine, st.session_state.session_id)

            if response.get("status") == "success":
                bot_response = response.get("answer", "No answer provided.")
                # Save to MongoDB
                save_chat_to_mongodb(
                    st.session_state.session_id,
                    question,
                    bot_response,
                    engine
                )
                # Update session state
                st.session_state.chat_history.append({
                    "user_message": question,
                    "bot_response": bot_response,
                    "engine_used": engine
                })
                # Rerun to update UI
                st.rerun()
            else:
                st.error(f"Error: {response.get('message', 'Unknown error')}")

if __name__ == "__main__":
    main()
