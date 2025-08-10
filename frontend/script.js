document.addEventListener('DOMContentLoaded', () => {
    const chatBox = document.getElementById('chat-box');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');

    const BACKEND_URL = 'http://localhost:5000/chat';

    const sendMessage = async () => {
        const messageText = userInput.value.trim();
        if (messageText === '') return;

        appendMessage(messageText, 'user');
        userInput.value = '';

        try {
            const response = await fetch(BACKEND_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: messageText }),
            });

            if (!response.body) {
                throw new Error('No response body');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let botMessageElement = appendMessage('', 'bot');
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');

                buffer = lines.pop(); // Keep the last, possibly incomplete, line

                for (const line of lines) {
                    if (line.trim() === '') continue;
                    try {
                        const jsonChunk = JSON.parse(line);
                        if (jsonChunk.error) {
                            botMessageElement.textContent = `Error: ${jsonChunk.error}`;
                            return;
                        }

                        // Assuming the streaming chunk has a 'message' object with 'content'
                        if (jsonChunk.message && jsonChunk.message.content) {
                            botMessageElement.textContent += jsonChunk.message.content;
                            chatBox.scrollTop = chatBox.scrollHeight;
                        }
                    } catch (error) {
                        console.error('Error parsing JSON chunk:', error, 'Chunk:', line);
                    }
                }
            }
        } catch (error) {
            console.error('Error sending message:', error);
            appendMessage(`Error: ${error.message}`, 'bot');
        }
    };

    const appendMessage = (text, sender) => {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', `${sender}-message`);
        messageElement.textContent = text;
        chatBox.appendChild(messageElement);
        chatBox.scrollTop = chatBox.scrollHeight;
        return messageElement;
    };

    sendButton.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
});
