import pytest
import pytest_asyncio
import json
import sys
import os
import asyncio
import httpx

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.app import app
from backend import database as db_ops
from backend.models import User, UserFact

@pytest_asyncio.fixture
async def setup_database(tmp_path):
    """Fixture to set up a temporary file-based SQLite database for tests."""
    db_path = tmp_path / "test_app.db"
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite+aiosqlite:///{db_path}"
    })

    from backend.extensions import async_engine, Base

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    user = await db_ops.get_or_create_user("test_user")
    app.config['DEFAULT_USER_ID'] = user.id

    yield

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture
async def client(setup_database):
    """An async test client for the Quart app."""
    return app.test_client()

class MockAsyncResponse:
    def __init__(self, chunks, status_code):
        self._chunks = chunks
        self.status_code = status_code

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def aiter_lines(self):
        for chunk in self._chunks:
            yield json.dumps(chunk)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("Error", request=None, response=self)

@pytest.mark.asyncio
async def test_chat_no_message(client):
    response = await client.post('/chat', json={'session_id': 'test-session'})
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_chat_success_mocked(client, mocker):
    mock_ollama_chunks = [{"type": "answer_chunk", "content": "Hello there!"}]
    mocker.patch('httpx.AsyncClient.stream', return_value=MockAsyncResponse(mock_ollama_chunks, 200))
    response = await client.post('/chat', json={'message': 'Hello', 'session_id': 'test-session'})
    assert response.status_code == 200
    await response.data
    history = await db_ops.get_session_history('test-session')
    assert len(history) == 2
    assert history[1]['content'] == 'Hello there!'

@pytest.mark.asyncio
async def test_get_sessions_with_data(client):
    user_id = app.config['DEFAULT_USER_ID']
    await db_ops.create_chat_session('session1', user_id, title="First Chat")
    await asyncio.sleep(0.01)
    await db_ops.create_chat_session('session2', user_id, title="Second Chat")
    response = await client.get('/sessions')
    assert response.status_code == 200
    sessions = await response.get_json()
    assert len(sessions) == 2
    titles = {s['title'] for s in sessions}
    assert titles == {"First Chat", "Second Chat"}

@pytest.mark.asyncio
async def test_delete_session(client):
    user_id = app.config['DEFAULT_USER_ID']
    session_id = 'delete-me'
    await db_ops.create_chat_session(session_id, user_id, "Delete Test")
    response = await client.delete(f'/sessions/{session_id}')
    assert response.status_code == 200
    sessions = await db_ops.get_all_sessions(user_id)
    assert not any(s['id'] == session_id for s in sessions)

@pytest.mark.asyncio
async def test_update_session_title(client):
    user_id = app.config['DEFAULT_USER_ID']
    session_id = 'rename-me'
    await db_ops.create_chat_session(session_id, user_id, "Old Title")
    response = await client.put(f'/sessions/{session_id}', json={'title': 'New Title'})
    assert response.status_code == 200
    sessions = await db_ops.get_all_sessions(user_id)
    updated_session = next((s for s in sessions if s['id'] == session_id), None)
    assert updated_session is not None
    assert updated_session['title'] == 'New Title'

@pytest.mark.asyncio
async def test_get_session_history_success(client):
    user_id = app.config['DEFAULT_USER_ID']
    await db_ops.create_chat_session('history-session', user_id)
    await db_ops.add_chat_message('history-session', 'user', 'Message 1')
    await db_ops.add_chat_message('history-session', 'assistant', 'Response 1')
    response = await client.get('/sessions/history-session')
    assert response.status_code == 200
    history = await response.get_json()
    assert len(history) == 2

@pytest.mark.asyncio
async def test_get_latest_session_greeting(client):
    user_id = app.config['DEFAULT_USER_ID']
    await db_ops.create_chat_session('session-old', user_id, title="Older Project")
    await asyncio.sleep(0.01)
    await db_ops.create_chat_session('session-new', user_id, title="Newer Project")
    response = await client.get('/sessions/latest/greeting')
    assert response.status_code == 200
    json_data = await response.get_json()
    assert "Newer Project" in json_data['greeting']

@pytest.mark.asyncio
async def test_save_fact_tool(client, mocker):
    user_id = app.config['DEFAULT_USER_ID']
    tool_call_response = [{"type": "tool_call", "tool_name": "save_fact", "arguments": {"fact_key": "user_city", "fact_value": "London"}}]
    final_response = [{"type": "answer_chunk", "content": "I've noted that you live in London."}]

    mock_stream = mocker.patch('httpx.AsyncClient.stream')
    mock_stream.side_effect = [
        MockAsyncResponse(tool_call_response, 200),
        MockAsyncResponse(final_response, 200)
    ]

    response = await client.post('/chat', json={'message': 'I live in London', 'session_id': 'fact-session'})
    await response.data

    facts = await db_ops.get_user_facts(user_id)
    assert any(fact['fact_key'] == 'user_city' and fact['fact_value'] == 'London' for fact in facts)

@pytest.mark.asyncio
async def test_chat_with_fact_recall(client, mocker):
    user_id = app.config['DEFAULT_USER_ID']
    await db_ops.save_fact(user_id, 'name', 'John')
    mock_ollama_chunks = [{"type": "answer_chunk", "content": "Hello John!"}]

    mock_stream = mocker.patch('httpx.AsyncClient.stream', return_value=MockAsyncResponse(mock_ollama_chunks, 200))

    await client.post('/chat', json={'message': 'Hi, do you know my name?', 'session_id': 'recall-test'})

    sent_payload = mock_stream.call_args.kwargs['json']
    system_prompt = sent_payload['messages'][0]['content']
    assert "## Known Facts About The User" in system_prompt
    assert "- name: John" in system_prompt
