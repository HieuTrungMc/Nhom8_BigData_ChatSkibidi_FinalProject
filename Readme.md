# Overview
This project is a simple chatbot called `ChatSkibidi` that will compete against `ChatGPT`. It is designed to be a fun and interactive way to engage with users. The chatbot is built using Python and utilizes the `tkinter` library for the GUI interface. The chatbot is capable of responding to user input and can be customized with different themes and styles.

Huong dan:
1. Build và chạy tất cả services: 
    docker-compose up --build
2. Chạy riêng services:
    docker-compose up crawler
    docker-compose up flask_server
    docker-compose up streamlit_app
3. Xem log services:
    docker-compose logs -f crawler
    docker-compose logs -f flask_server
    docker-compose logs -f streamlit_app
4. Dừng services:
    docker-compose down