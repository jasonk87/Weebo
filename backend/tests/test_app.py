import pytest
import json
import os
import time
from backend.app import app as flask_app, get_db
from backend import database as db

@pytest.fixture
def app(tmp_path):
    """App fixture that sets up a temporary, isolated database for each test."""
    db_path = tmp_path / "test_app.db"

    flask_app.config.update({
        "TESTING": True,
        "DATABASE_PATH": str(db_path),
    })

    with flask_app.app_context():
        db.init_db(db_path=str(db_path))
        conn = get_db()
        # Set a known user for testing
        flask_app.config['DEFAULT_USER_ID'] = db.get_or_create_user(conn, "test_user")

        yield flask_app

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

# Helper class for mocking requests.post responses
class MockResponse:
    def __init__(self, chunks, status_code):
        self.chunks = chunks
        self.status_code = status_code
    def iter_lines(self):
        for chunk in self.chunks:
            yield json.dumps(chunk).encode('utf-8')
    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception("HTTP Error")

def test_chat_no_message(client):
    response = client.post('/chat', json={'session_id': 'test-session'})
    assert response.status_code == 400

def test_chat_success_mocked(client, mocker):
    client.application.config['DEFAULT_USER_ID'] = 1
    mock_post = mocker.patch('requests.post')
    mock_ollama_chunks = [{"type": "answer_chunk", "content": "Hello there!"}]
    mock_post.return_value = MockResponse(mock_ollama_chunks, 200)

    response = client.post('/chat', json={'message': 'Hello', 'session_id': 'test-session'})
    assert response.status_code == 200
    _ = response.data

    with flask_app.app_context():
        history = db.get_session_history(get_db(), 'test-session')
        assert len(history) == 2
        assert history[1]['content'] == 'Hello there!'

def test_get_sessions_with_data(client):
    with flask_app.app_context():
        conn = get_db()
        user_id = flask_app.config['DEFAULT_USER_ID']
        db.create_chat_session(conn, 'session1', user_id, title="First Chat")
        time.sleep(1.1)
        db.create_chat_session(conn, 'session2', user_id, title="Second Chat")

    response = client.get('/sessions')
    assert response.status_code == 200
    sessions = response.get_json()
    assert len(sessions) == 2
    titles = {s['title'] for s in sessions}
    assert titles == {"First Chat", "Second Chat"}

def test_get_session_history_success(client):
    with flask_app.app_context():
        conn = get_db()
        user_id = flask_app.config['DEFAULT_USER_ID']
        db.create_chat_session(conn, 'history-session', user_id)
        db.add_chat_message(conn, 'history-session', 'user', 'Message 1')
        db.add_chat_message(conn, 'history-session', 'assistant', 'Response 1')

    response = client.get('/sessions/history-session')
    assert response.status_code == 200
    history = response.get_json()
    assert len(history) == 2

def test_get_latest_session_greeting(client):
    with flask_app.app_context():
        conn = get_db()
        user_id = flask_app.config['DEFAULT_USER_ID']
        db.create_chat_session(conn, 'session-old', user_id, title="Older Project")
        time.sleep(1.1)
        db.create_chat_session(conn, 'session-new', user_id, title="Newer Project")

    response = client.get('/sessions/latest/greeting')
    assert response.status_code == 200
    json_data = response.get_json()
    assert "Newer Project" in json_data['greeting']

def test_save_fact_tool(client, mocker):
    client.application.config['DEFAULT_USER_ID'] = 1
    mock_post = mocker.patch('requests.post')
    tool_call_response = [{"type": "tool_call", "tool_name": "save_fact", "arguments": {"fact_key": "user_city", "fact_value": "London"}}]
    final_response = [{"type": "answer_chunk", "content": "I've noted that you live in London."}]
    mock_post.side_effect = [
        MockResponse(tool_call_response, 200),
        MockResponse(final_response, 200),
    ]

    response = client.post('/chat', json={'message': 'I live in London', 'session_id': 'fact-session'})
    _ = response.data

    with flask_app.app_context():
        conn = get_db()
        user_id = flask_app.config['DEFAULT_USER_ID']
        cursor = conn.cursor()
        cursor.execute("SELECT fact_value FROM user_facts WHERE user_id = ? AND fact_key = ?", (user_id, 'user_city'))
        fact = cursor.fetchone()
        assert fact is not None
        assert fact['fact_value'] == 'London'

def test_chat_with_fact_recall(client, mocker):
    # 1. Setup: Save a fact directly to the database for the user
    user_id = client.application.config['DEFAULT_USER_ID']
    with flask_app.app_context():
        db.save_fact(get_db(), user_id, 'name', 'John')

    # 2. Mock the API call
    mock_post = mocker.patch('requests.post')
    mock_ollama_chunks = [{"type": "answer_chunk", "content": "Hello John!"}]
    mock_post.return_value = MockResponse(mock_ollama_chunks, 200)

    # 3. Act: Send a message that should trigger the recall
    client.post('/chat', json={'message': 'Hi, do you know my name?', 'session_id': 'recall-test'})

    # 4. Assert: Check that the prompt sent to Ollama contained the fact
    mock_post.assert_called_once()
    call_args, call_kwargs = mock_post.call_args
    sent_payload = call_kwargs['json']
    system_prompt = sent_payload['messages'][0]['content']

    assert "## Known Facts About The User" in system_prompt
    assert "- name: John" in system_prompt

def test_delete_session(client):
    # 1. Setup: Create a session to delete
    user_id = client.application.config['DEFAULT_USER_ID']
    session_id_to_delete = 'delete-me'
    with flask_app.app_context():
        conn = get_db()
        db.create_chat_session(conn, session_id_to_delete, user_id, title="To Be Deleted")
        db.add_chat_message(conn, session_id_to_delete, 'user', 'A message')
        # Verify it exists
        sessions = db.get_all_sessions(conn, user_id)
        assert any(s['id'] == session_id_to_delete for s in sessions)

    # 2. Act: Call the DELETE endpoint
    response = client.delete(f'/sessions/{session_id_to_delete}')
    assert response.status_code == 200

    # 3. Assert: Verify the session and its messages are gone
    with flask_app.app_context():
        conn = get_db()
        sessions = db.get_all_sessions(conn, user_id)
        assert not any(s['id'] == session_id_to_delete for s in sessions)
        history = db.get_session_history(conn, session_id_to_delete)
        assert len(history) == 0

def test_update_session_title(client):
    # 1. Setup: Create a session to rename
    user_id = client.application.config['DEFAULT_USER_ID']
    session_id_to_rename = 'rename-me'
    with flask_app.app_context():
        conn = get_db()
        db.create_chat_session(conn, session_id_to_rename, user_id, title="Old Title")

    # 2. Act: Call the PUT endpoint with the new title
    new_title = "A Better Title"
    response = client.put(f'/sessions/{session_id_to_rename}', json={'title': new_title})
    assert response.status_code == 200

    # 3. Assert: Verify the title was updated
    with flask_app.app_context():
        conn = get_db()
        sessions = db.get_all_sessions(conn, user_id)
        renamed_session = next((s for s in sessions if s['id'] == session_id_to_rename), None)
        assert renamed_session is not None
        assert renamed_session['title'] == new_title
