from flask import Flask, request, Response, jsonify
from flask_cors import CORS
import requests
import json
import time

app = Flask(__name__)
CORS(app)

OLLAMA_API_URL = "http://192.168.86.30:11434/api/chat"
OLLAMA_MODEL = "qwen3:8b"

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({"error": "Message not provided"}), 400

    message = data['message']

    def generate():
        try:
            # Step 1: Yield simulated thoughts
            yield json.dumps({"type": "thought", "content": "The user sent a message. I need to understand their request and formulate a response."}) + '\n'
            time.sleep(0.5)
            yield json.dumps({"type": "thought", "content": "Analyzing the user's input for key topics and intent..."}) + '\n'
            time.sleep(0.5)
            yield json.dumps({"type": "thought", "content": "Okay, I have a plan. I will now generate the main response."}) + '\n'
            time.sleep(0.2)

            # Step 2: Call Ollama and stream answer chunks
            payload = {
                "model": OLLAMA_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": message
                    }
                ],
                "stream": True
            }

            response = requests.post(OLLAMA_API_URL, json=payload, stream=True)
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    try:
                        ollama_chunk = json.loads(line)
                        answer_content = ollama_chunk.get('message', {}).get('content')
                        if answer_content:
                            yield json.dumps({"type": "answer_chunk", "content": answer_content}) + '\n'
                    except json.JSONDecodeError:
                        continue

        except requests.exceptions.RequestException as e:
            error_message = f"Error connecting to Ollama: {e}"
            print(error_message)
            yield json.dumps({"type": "error", "content": error_message}) + '\n'

    return Response(generate(), mimetype='application/x-ndjson')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
