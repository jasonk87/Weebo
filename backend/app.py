from flask import Flask, request, Response, jsonify
from flask_cors import CORS
import requests
import json

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
                        # Pass through the JSON object from Ollama
                        json.loads(line) # a simple check for valid json
                        yield line.decode('utf-8') + '\n'
                    except json.JSONDecodeError:
                        # Handle cases where a line is not valid JSON
                        continue

        except requests.exceptions.RequestException as e:
            error_message = f"Error connecting to Ollama: {e}"
            print(error_message)
            # Yield a JSON object with error info to the client
            yield json.dumps({"error": error_message}) + '\\n'

    return Response(generate(), mimetype='application/x-ndjson')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
