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
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code
            self.text = json.dumps(json_data)

        def iter_lines(self):
            yield self.text.encode('utf-8')

        def raise_for_status(self):
            if self.status_code >= 400:
                raise Exception("HTTP Error")

    mock_response_data = {
        "model": "qwen3:8b",
        "created_at": "2023-08-04T19:22:45.499127Z",
        "message": {
            "role": "assistant",
            "content": "Hello! How can I help you today?"
        },
        "done": True
    }
    mock_post.return_value = MockResponse(mock_response_data, 200)

    response = client.post('/chat', json={'message': 'Hello'})
    assert response.status_code == 200

    # The response is a stream, so we need to read it
    response_data = b"".join(response.response).decode('utf-8')

    # As the stream yields json strings with newline, we expect one such line
    lines = [line for line in response_data.strip().split('\n') if line]
    assert len(lines) == 1

    response_json = json.loads(lines[0])

    assert response_json['message']['content'] == "Hello! How can I help you today?"
    mock_post.assert_called_once()
