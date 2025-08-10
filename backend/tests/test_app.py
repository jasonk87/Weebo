import pytest
import json
import shelve
from backend.app import app as flask_app

@pytest.fixture
def app(mocker, tmp_path):
    """
    App fixture that patches the database file paths to use a temporary directory.
    This ensures that tests are isolated and don't leave behind database files.
    """
    history_db_path = tmp_path / "chat_histories.db"
    knowledge_db_path = tmp_path / "knowledge.db"
    mocker.patch('backend.app.CHAT_HISTORY_DB', str(history_db_path))
    mocker.patch('backend.knowledge_base.DB_FILE', str(knowledge_db_path))
    yield flask_app

@pytest.fixture
def client(app):
    return app.test_client()

def test_chat_no_message(client):
    """
    Test that the /chat endpoint returns a 400 error
    if no message is provided.
    """
    response = client.post('/chat', json={'session_id': 'test-session'})
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['error'] == "Message or session_id not provided"

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

def test_chat_success_mocked(client, mocker):
    """
    Test a successful call to the /chat endpoint with a mocked Ollama API.
    """
    # Mock the requests.post call
    mock_post = mocker.patch('requests.post')

    mock_ollama_chunks = [
        {"type": "thought", "content": "Thinking..."},
        {"type": "answer_chunk", "content": "Hello! How can I help?"},
    ]
    mock_post.return_value = MockResponse(mock_ollama_chunks, 200)

    response = client.post('/chat', json={'message': 'Hello', 'session_id': 'test-session'})
    assert response.status_code == 200

    # The response is a stream, so we need to read it
    response_data = b"".join(response.response).decode('utf-8')
    lines = [line for line in response_data.strip().split('\n') if line]

    # Check for thoughts and answer chunks
    lines = [json.loads(line) for line in lines]
    assert len(lines) == 2
    assert lines[0]['type'] == 'thought'
    assert lines[1]['type'] == 'answer_chunk'
    assert lines[1]['content'] == "Hello! How can I help?"

    mock_post.assert_called_once()


def test_chat_with_tool_call(client, mocker):
    """
    Test a chat interaction that involves a tool call.
    """
    # Mock the save_fact tool
    mock_save_fact = mocker.MagicMock()
    mocker.patch.dict('backend.app.tools', {'save_fact': mock_save_fact})

    # Mock the response from Ollama
    # First response: AI decides to call a tool
    ollama_response_1 = [
        {"type": "thought", "content": "The user mentioned their name is Jules. I should save this fact."},
        {"type": "tool_call", "tool_name": "save_fact", "arguments": {"fact_name": "user_name", "fact_content": "Jules"}}
    ]
    # Second response: After the tool call, AI gives a final answer
    ollama_response_2 = [
        {"type": "thought", "content": "I have saved the user's name. Now I will respond to them."},
        {"type": "answer_chunk", "content": "Thanks for telling me your name, Jules!"}
    ]

    # Mock the requests.post call to return these responses in sequence
    mock_post = mocker.patch('requests.post')
    mock_post.side_effect = [
        MockResponse(ollama_response_1, 200),
        MockResponse(ollama_response_2, 200)
    ]

    response = client.post('/chat', json={'message': 'Hi, my name is Jules', 'session_id': 'test-tool-session'})
    assert response.status_code == 200

    # We need to consume the response generator for the tool call to happen
    response_data = b"".join(response.response).decode('utf-8')

    # Verify that the save_fact tool was called correctly
    mock_save_fact.assert_called_once_with(fact_name='user_name', fact_content='Jules')

    # Verify the streamed output to the frontend
    lines = [json.loads(line) for line in response_data.strip().split('\n') if line]

    assert len(lines) == 5

    assert lines[0]['type'] == 'thought'
    assert lines[0]['content'] == "The user mentioned their name is Jules. I should save this fact."

    assert lines[1]['type'] == 'thought'
    assert "Executing tool: save_fact" in lines[1]['content']

    assert lines[2]['type'] == 'thought'
    assert "Tool save_fact executed successfully" in lines[2]['content']

    assert lines[3]['type'] == 'thought'
    assert lines[3]['content'] == "I have saved the user's name. Now I will respond to them."

    assert lines[4]['type'] == 'answer_chunk'
    assert lines[4]['content'] == "Thanks for telling me your name, Jules!"


def test_get_sessions_empty(client):
    """Test the /sessions endpoint when no sessions exist."""
    response = client.get('/sessions')
    assert response.status_code == 200
    assert response.get_json() == []

def test_get_sessions_with_data(client, tmp_path):
    """Test the /sessions endpoint with some data."""
    # Manually create some session data
    history_db_path = str(tmp_path / "chat_histories.db")
    with shelve.open(history_db_path) as db:
        db['session1'] = [
            {'role': 'user', 'content': 'This is the first message.'}
        ]
        db['session2'] = [
            {'role': 'user', 'content': 'This is another conversation that is much longer than fifty characters to test truncation.'}
        ]
        db['session3'] = [
            # No user message
            {'role': 'system', 'content': '...'}
        ]

    response = client.get('/sessions')
    assert response.status_code == 200
    sessions = response.get_json()
    assert len(sessions) == 3

    # The sessions should be sorted by id
    assert sessions[0]['id'] == 'session1'
    assert sessions[0]['title'] == 'This is the first message.'

    assert sessions[1]['id'] == 'session2'
    assert sessions[1]['title'] == 'This is another conversation that is much longer t...'

    assert sessions[2]['id'] == 'session3'
    assert sessions[2]['title'] == 'New Conversation'


def test_get_session_history_not_found(client):
    """Test getting history for a session that does not exist."""
    response = client.get('/sessions/non-existent-session')
    assert response.status_code == 404
    assert response.get_json()['error'] == 'Session not found'

def test_get_session_history_success(client, tmp_path):
    """Test getting history for a session that exists."""
    history_db_path = str(tmp_path / "chat_histories.db")
    mock_history = [{'role': 'user', 'content': 'Hello'}]
    with shelve.open(history_db_path) as db:
        db['session1'] = mock_history

    response = client.get('/sessions/session1')
    assert response.status_code == 200
    assert response.get_json() == mock_history
