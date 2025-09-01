import pytest
import json
import os
import time
from backend.app import app as flask_app, db_sql_alchemy as db
from backend import database as db_ops
from backend.models import User, ChatSession, ChatMessage, UserFact

@pytest.fixture
def app(tmp_path):
    """App fixture that sets up a temporary, isolated database for each test."""
    db_path = tmp_path / "test_app.db"
    flask_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}"
    })

    with flask_app.app_context():
        db.create_all()
        user = db_ops.get_or_create_user("test_user")
        flask_app.config['DEFAULT_USER_ID'] = user.id
        yield flask_app
        db.session.remove()
        db.drop_all()

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

def test_chat_success_mocked(client, mocker, app):
    app.config['DEFAULT_USER_ID'] = 1
    mock_post = mocker.patch('requests.post')
    mock_ollama_chunks = [{"type": "answer_chunk", "content": "Hello there!"}]
    mock_post.return_value = MockResponse(mock_ollama_chunks, 200)

    response = client.post('/chat', json={'message': 'Hello', 'session_id': 'test-session'})
    assert response.status_code == 200
    # Fully consume the generator
    for _ in response.iter_encoded():
        pass

    history = db_ops.get_session_history('test-session')
    assert len(history) == 2
    assert history[1]['content'] == 'Hello there!'

def test_get_sessions_with_data(client, app):
    user_id = app.config['DEFAULT_USER_ID']
    db_ops.create_chat_session('session1', user_id, title="First Chat")
    time.sleep(1.1) # To ensure different timestamps
    db_ops.create_chat_session('session2', user_id, title="Second Chat")

    response = client.get('/sessions')
    assert response.status_code == 200
    sessions = response.get_json()
    assert len(sessions) == 2
    titles = {s['title'] for s in sessions}
    assert titles == {"First Chat", "Second Chat"}

def test_get_session_history_success(client, app):
    user_id = app.config['DEFAULT_USER_ID']
    db_ops.create_chat_session('history-session', user_id)
    db_ops.add_chat_message('history-session', 'user', 'Message 1')
    db_ops.add_chat_message('history-session', 'assistant', 'Response 1')

    response = client.get('/sessions/history-session')
    assert response.status_code == 200
    history = response.get_json()
    assert len(history) == 2

def test_get_latest_session_greeting(client, app):
    user_id = app.config['DEFAULT_USER_ID']
    db_ops.create_chat_session('session-old', user_id, title="Older Project")
    time.sleep(1.1)
    db_ops.create_chat_session('session-new', user_id, title="Newer Project")

    response = client.get('/sessions/latest/greeting')
    assert response.status_code == 200
    json_data = response.get_json()
    assert "Newer Project" in json_data['greeting']

def test_save_fact_tool(client, mocker, app):
    app.config['DEFAULT_USER_ID'] = 1
    mock_post = mocker.patch('requests.post')
    tool_call_response = [{"type": "tool_call", "tool_name": "save_fact", "arguments": {"fact_key": "user_city", "fact_value": "London"}}]
    final_response = [{"type": "answer_chunk", "content": "I've noted that you live in London."}]
    mock_post.side_effect = [ MockResponse(tool_call_response, 200), MockResponse(final_response, 200) ]

    response = client.post('/chat', json={'message': 'I live in London', 'session_id': 'fact-session'})
    # Fully consume the generator
    for _ in response.iter_encoded():
        pass

    fact = UserFact.query.filter_by(user_id=1, fact_key='user_city').first()
    assert fact is not None
    assert fact.fact_value == 'London'

def test_chat_with_fact_recall(client, mocker, app):
    user_id = app.config['DEFAULT_USER_ID']
    db_ops.save_fact(user_id, 'name', 'John')

    mock_post = mocker.patch('requests.post')
    mock_ollama_chunks = [{"type": "answer_chunk", "content": "Hello John!"}]
    mock_post.return_value = MockResponse(mock_ollama_chunks, 200)

    response = client.post('/chat', json={'message': 'Hi, do you know my name?', 'session_id': 'recall-test'})
    # Fully consume the generator
    for _ in response.iter_encoded():
        pass

    mock_post.assert_called_once()
    sent_payload = mock_post.call_args.kwargs['json']
    system_prompt = sent_payload['messages'][0]['content']
    assert "## Known Facts About The User" in system_prompt
    assert "- name: John" in system_prompt

def test_delete_session(client, app):
    user_id = app.config['DEFAULT_USER_ID']
    session_id_to_delete = 'delete-me'
    db_ops.create_chat_session(session_id_to_delete, user_id, title="To Be Deleted")
    db_ops.add_chat_message(session_id_to_delete, 'user', 'A message')

    response = client.delete(f'/sessions/{session_id_to_delete}')
    assert response.status_code == 200

    sessions = db_ops.get_all_sessions(user_id)
    assert not any(s['id'] == session_id_to_delete for s in sessions)
    history = db_ops.get_session_history(session_id_to_delete)
    assert len(history) == 0

def test_update_session_title(client, app):
    user_id = app.config['DEFAULT_USER_ID']
    session_id_to_rename = 'rename-me'
    db_ops.create_chat_session(session_id_to_rename, user_id, title="Old Title")

    new_title = "A Better Title"
    response = client.put(f'/sessions/{session_id_to_rename}', json={'title': new_title})
    assert response.status_code == 200

    sessions = db_ops.get_all_sessions(user_id)
    renamed_session = next((s for s in sessions if s['id'] == session_id_to_rename), None)
    assert renamed_session is not None
    assert renamed_session['title'] == new_title
