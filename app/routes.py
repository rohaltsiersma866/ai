from app import app
from flask import request, jsonify
import os
from app.utils import call_agentrouter_api

@app.route('/')
def home():
    return "Welcome to the Chatbot!"

@app.route('/send_message', methods=['POST'])
def send_message():
    data = request.get_json()
    prompt = data['input']
    response = call_agentrouter_api(prompt)
    return jsonify({'response': response['output']})

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"})
    file = request.files['file']
    filename = os.path.join('uploads', file.filename)
    file.save(filename)
    # Xử lý file nếu cần
    return jsonify({"message": "File uploaded successfully!"})
