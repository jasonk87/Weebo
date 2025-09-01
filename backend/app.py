from flask import Flask, request, Response, jsonify, g
from flask_cors import CORS
import requests
import json
import sqlite3
import os
import backend.database as db

app = Flask(__name__)
CORS(app)

# --- Database Connection Management ---
def get_db():
    """Opens a new database connection if there is none yet for the current application context."""
    if 'db' not in g:
        db_path = app.config.get('DATABASE_PATH', db.DB_FILE)
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    """Closes the database again at the end of the request."""
    database = g.pop('db', None)
    if database is not None:
        database.close()

# This will be initialized in the main block or test fixture
DEFAULT_USER_ID = 1

# --- AI Configuration ---
OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "http://127.0.0.1:11434/api/chat")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:8b")
SYSTEM_PROMPT = """You are a helpful and friendly AI assistant. Your goal is to have a conversation with the user and assist them with their tasks.

You have access to the following tools. To use a tool, you must respond with a single JSON object with 'type': 'tool_call' and no other text.
Example:
{"type": "tool_call", "tool_name": "save_fact", "arguments": {"fact_key": "user_hometown", "fact_value": "New York"}}

Here are the available tools:
- `save_fact(fact_key: str, fact_value: str)`: Use this tool to remember a specific fact about the user or the conversation. For example, if the user mentions their name or hometown, you should save it.

Your thought process should be:
1.  **Think:** Analyze the user's message and the conversation history. Formulate a plan. You must output your thoughts in JSON format: {"type": "thought", "content": "your thought here"}.
2.  **Act:** Decide if you need to use a tool. If so, call the tool using the specified JSON format. If not, provide your final answer to the user directly, streaming it chunk by chunk in the format: {"type": "answer_chunk", "content": "your response here"}.

Always start by thinking.
"""

def get_tools(db_conn):
    return {
        "save_fact": lambda **kwargs: db.save_fact(db_conn, **kwargs),
    }

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    if not data or 'message' not in data or 'session_id' not in data:
        return jsonify({"error": "Message or session_id not provided"}), 400

    message = data['message']
    session_id = data['session_id']
    user_id = app.config.get('DEFAULT_USER_ID', 1)

    db_conn = get_db()

    def generate_and_save():
        db.create_chat_session(db_conn, session_id, user_id)
        db.add_chat_message(db_conn, session_id, "user", message)

        facts = db.get_user_facts(db_conn, user_id)
        facts_prompt_section = ""
        if facts:
            facts_list = "\n".join([f"- {fact['fact_key']}: {fact['fact_value']}" for fact in facts])
            facts_prompt_section = f"\n\n## Known Facts About The User\nHere is a list of facts you know about the user. Use them to provide a more personalized experience.\n{facts_list}"

        system_prompt_with_facts = SYSTEM_PROMPT + facts_prompt_section

        history = db.get_session_history(db_conn, session_id)
        history.insert(0, {"role": "system", "content": system_prompt_with_facts})

        full_assistant_response = ""
        tools = get_tools(db_conn)

        try:
            while True:
                payload = {"model": OLLAMA_MODEL, "messages": history, "stream": True}
                response = requests.post(OLLAMA_API_URL, json=payload, stream=True)
                response.raise_for_status()
                tool_call_json = None

                for line in response.iter_lines():
                    if line:
                        try:
                            chunk_str = line.decode('utf-8')
                            chunk = json.loads(chunk_str)
                            if chunk.get("type") == "tool_call":
                                tool_call_json = chunk
                                break
                            yield chunk_str + '\n'
                            if chunk.get("type") == "answer_chunk":
                                full_assistant_response += chunk.get("content", "")
                        except json.JSONDecodeError:
                            print(f"JSON decode error for line: {line}")
                            continue

                if tool_call_json:
                    tool_name = tool_call_json.get("tool_name")
                    arguments = tool_call_json.get("arguments", {})
                    if tool_name in tools:
                        yield json.dumps({"type": "thought", "content": f"Executing tool: {tool_name}({arguments})"}) + '\n'
                        try:
                            tool_result = tools[tool_name](user_id=user_id, **arguments)
                            result_message = f"Tool {tool_name} executed successfully. Result: {tool_result}"
                        except Exception as e:
                            result_message = f"Error executing tool {tool_name}: {e}"
                        yield json.dumps({"type": "thought", "content": result_message}) + '\n'
                        db.add_chat_message(db_conn, session_id, "assistant", json.dumps(tool_call_json))
                        db.add_chat_message(db_conn, session_id, "tool", result_message)
                        history.append({"role": "assistant", "content": json.dumps(tool_call_json)})
                        history.append({"role": "tool", "content": result_message})
                        continue
                    else:
                        yield json.dumps({"type": "error", "content": f"Unknown tool: {tool_name}"}) + '\n'
                        break
                else:
                    break

            if full_assistant_response:
                db.add_chat_message(db_conn, session_id, "assistant", full_assistant_response)

        except requests.exceptions.RequestException as e:
            error_message = f"Error connecting to Ollama: {e}"
            print(error_message)
            yield json.dumps({"type": "error", "content": error_message}) + '\n'

    return Response(generate_and_save(), mimetype='application/x-ndjson')

@app.route('/sessions', methods=['GET'])
def get_sessions():
    user_id = app.config.get('DEFAULT_USER_ID', 1)
    try:
        sessions = db.get_all_sessions(get_db(), user_id)
        return jsonify(sessions)
    except Exception as e:
        print(f"Error reading sessions: {e}")
        return jsonify({"error": "Could not retrieve sessions"}), 500

@app.route('/sessions/<session_id>', methods=['GET'])
def get_session_history_route(session_id):
    try:
        history = db.get_session_history(get_db(), session_id)
        return jsonify(history)
    except Exception as e:
        print(f"Error reading session {session_id}: {e}")
        return jsonify({"error": "Could not retrieve session history"}), 500

@app.route('/sessions/latest/greeting', methods=['GET'])
def get_latest_session_greeting():
    user_id = app.config.get('DEFAULT_USER_ID', 1)
    try:
        session = db.get_latest_session(get_db(), user_id)
        if not session:
            return jsonify({"greeting": "Welcome! What can I help you with today?", "session_id": None})

        title = session['title']
        if title == 'New Conversation':
             return jsonify({"greeting": "Welcome back! Ready to start a new conversation?", "session_id": None})

        greeting = f"Welcome back! Would you like to continue our conversation about '{title}'?"
        return jsonify({"greeting": greeting, "session_id": session['id']})
    except Exception as e:
        print(f"Error getting latest session greeting: {e}")
        return jsonify({"greeting": "Welcome back! It's great to see you.", "session_id": None})

if __name__ == '__main__':
    with app.app_context():
        db.init_db()
        app.config['DEFAULT_USER_ID'] = db.get_or_create_user(get_db(), "default_user")
    app.run(host='0.0.0.0', port=5000, debug=True)
