from flask import Flask, request, Response, jsonify
from flask_cors import CORS
import requests
import json
import time
import shelve
from backend.knowledge_base import save_fact

app = Flask(__name__)
CORS(app)

OLLAMA_API_URL = "http://192.168.86.30:11434/api/chat"
OLLAMA_MODEL = "qwen3:8b"
SYSTEM_PROMPT = """You are a helpful and friendly AI assistant. Your goal is to have a conversation with the user and assist them with their tasks.

You have access to the following tools. To use a tool, you must respond with a single JSON object with 'type': 'tool_call' and no other text.
Example:
{"type": "tool_call", "tool_name": "save_fact", "arguments": {"fact_name": "user_hometown", "fact_content": "New York"}}

Here are the available tools:
- `save_fact(fact_name: str, fact_content: str)`: Use this tool to remember a specific fact about the user or the conversation. For example, if the user mentions their name or hometown, you should save it.

Your thought process should be:
1.  **Think:** Analyze the user's message and the conversation history. Formulate a plan. You must output your thoughts in JSON format: {"type": "thought", "content": "your thought here"}.
2.  **Act:** Decide if you need to use a tool. If so, call the tool using the specified JSON format. If not, provide your final answer to the user directly, streaming it chunk by chunk in the format: {"type": "answer_chunk", "content": "your response here"}.

Always start by thinking.
"""

tools = {
    "save_fact": save_fact,
}

CHAT_HISTORY_DB = 'chat_histories.db'

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    if not data or 'message' not in data or 'session_id' not in data:
        return jsonify({"error": "Message or session_id not provided"}), 400

    message = data['message']
    session_id = data['session_id']

    def generate_and_save():
        # 1. Read initial history from shelve
        with shelve.open(CHAT_HISTORY_DB) as db:
            history = db.get(session_id, [
                {"role": "system", "content": SYSTEM_PROMPT}
            ])

        history.append({"role": "user", "content": message})
        full_assistant_response = ""

        try:
            # ReAct Loop
            while True:
                payload = {
                    "model": OLLAMA_MODEL,
                    "messages": history,
                    "stream": True
                }

                response = requests.post(OLLAMA_API_URL, json=payload, stream=True)
                response.raise_for_status()

                tool_call_json = None

                for line in response.iter_lines():
                    if line:
                        try:
                            chunk_str = line.decode('utf-8')
                            chunk = json.loads(chunk_str)

                            # Check if the chunk is a tool call
                            if chunk.get("type") == "tool_call":
                                tool_call_json = chunk
                                break

                            # Otherwise, it's a thought or an answer chunk
                            yield chunk_str + '\n'

                            # Accumulate final answer for history
                            if chunk.get("type") == "answer_chunk":
                                full_assistant_response += chunk.get("content", "")

                        except json.JSONDecodeError:
                            print(f"JSON decode error for line: {line}")
                            continue

                if tool_call_json:
                    tool_name = tool_call_json.get("tool_name")
                    arguments = tool_call_json.get("arguments")

                    if tool_name in tools:
                        yield json.dumps({"type": "thought", "content": f"Executing tool: {tool_name}({arguments})"}) + '\n'
                        try:
                            tool_result = tools[tool_name](**arguments)
                            result_message = f"Tool {tool_name} executed successfully. Result: {tool_result}"
                        except Exception as e:
                            result_message = f"Error executing tool {tool_name}: {e}"

                        yield json.dumps({"type": "thought", "content": result_message}) + '\n'
                        history.append({"role": "assistant", "content": json.dumps(tool_call_json)}) # Add tool call to history
                        history.append({"role": "tool", "content": result_message}) # Add tool result to history
                        continue # Continue the loop to get the next step from the AI
                    else:
                        yield json.dumps({"type": "error", "content": f"Unknown tool: {tool_name}"}) + '\n'
                        break # Exit loop if tool is unknown
                else:
                    # If no tool call, the stream is finished
                    break

            # Save the final assistant response to the history
            if full_assistant_response:
                history.append({"role": "assistant", "content": full_assistant_response})

        except requests.exceptions.RequestException as e:
            error_message = f"Error connecting to Ollama: {e}"
            print(error_message)
            yield json.dumps({"type": "error", "content": error_message}) + '\n'
        finally:
            # After generator is exhausted, save the final history
            with shelve.open(CHAT_HISTORY_DB) as db:
                db[session_id] = history

    return Response(generate_and_save(), mimetype='application/x-ndjson')

@app.route('/sessions', methods=['GET'])
def get_sessions():
    sessions = []
    try:
        with shelve.open(CHAT_HISTORY_DB) as db:
            # Sort keys to have a consistent order, maybe by creation time if possible
            # For now, sorting alphabetically is better than random
            sorted_keys = sorted(list(db.keys()))
            for session_id in sorted_keys:
                history = db[session_id]
                # Find the first user message to use as a title
                first_user_message = next((msg['content'] for msg in history if msg['role'] == 'user'), None)
                title = (first_user_message[:50] + '...') if first_user_message and len(first_user_message) > 50 else first_user_message
                if not title:
                    title = 'New Conversation'

                sessions.append({'id': session_id, 'title': title})
        return jsonify(sessions)
    except Exception as e:
        print(f"Error reading sessions: {e}")
        return jsonify({"error": "Could not retrieve sessions"}), 500

@app.route('/sessions/<session_id>', methods=['GET'])
def get_session_history(session_id):
    try:
        with shelve.open(CHAT_HISTORY_DB) as db:
            if session_id not in db:
                return jsonify({"error": "Session not found"}), 404
            return jsonify(db[session_id])
    except Exception as e:
        print(f"Error reading session {session_id}: {e}")
        return jsonify({"error": "Could not retrieve session history"}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
