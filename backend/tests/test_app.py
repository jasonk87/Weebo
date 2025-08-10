import pytest
import json
from backend.app import app as flask_app

@pytest.fixture
def app():
    yield flask_app

@pytest.fixture
def client(app):
    return app.test_client()

def test_chat_no_message(client):
    """
    Test that the /chat endpoint returns a 400 error
    if no message is provided.
    """
    response = client.post('/chat', json={})
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['error'] == "Message not provided"

def test_chat_success_mocked(client, mocker):
    """
    Test a successful call to the /chat endpoint with a mocked Ollama API.
    """
    # Mock the requests.post call
    mock_post = mocker.patch('requests.post')

    # Create a mock response object
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

    mock_ollama_chunks = [
        {"message": {"content": "Hello!"}},
        {"message": {"content": " How can"}},
        {"message": {"content": " I help?"}},
    ]
    mock_post.return_value = MockResponse(mock_ollama_chunks, 200)

    response = client.post('/chat', json={'message': 'Hello'})
    assert response.status_code == 200

    # The response is a stream, so we need to read it
    response_data = b"".join(response.response).decode('utf-8')
    lines = [line for line in response_data.strip().split('\n') if line]

    # Check for thoughts
    assert len(lines) > 3
    assert json.loads(lines[0])['type'] == 'thought'
    assert json.loads(lines[1])['type'] == 'thought'
    assert json.loads(lines[2])['type'] == 'thought'

    # Check for answer chunks
    answer_chunks = [json.loads(line) for line in lines[3:]]
    assert all(chunk['type'] == 'answer_chunk' for chunk in answer_chunks)

    full_answer = "".join(chunk['content'] for chunk in answer_chunks)
    assert full_answer == "Hello! How can I help?"

    mock_post.assert_called_once()
