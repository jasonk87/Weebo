document.addEventListener('DOMContentLoaded', () => {
    const chatBox = document.getElementById('chat-box');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const typingIndicator = document.getElementById('typing-indicator');

    const BACKEND_URL = 'http://localhost:5000/chat';

    const sendMessage = async () => {
        const messageText = userInput.value.trim();
        if (messageText === '') return;

        appendMessage(messageText, 'user');
        userInput.value = '';

        // Show typing indicator and disable input
        typingIndicator.style.display = 'flex';
        sendButton.disabled = true;
        userInput.disabled = true;

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
            let botMessageElement = null;
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                // Hide typing indicator once the first chunk arrives
                if (typingIndicator.style.display !== 'none') {
                    typingIndicator.style.display = 'none';
                }

                if (!botMessageElement) {
                    botMessageElement = appendMessage('', 'bot');
                }

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
                            botMessageElement.fullContent += jsonChunk.message.content;
                            // Use marked to parse markdown content
                            botMessageElement.innerHTML = marked.parse(botMessageElement.fullContent);
                            // Apply highlighting to code blocks
                            botMessageElement.querySelectorAll('pre code').forEach((block) => {
                                hljs.highlightElement(block);
                            });
                            addCopyButtons(botMessageElement);
                            chatBox.scrollTop = chatBox.scrollHeight;
                        }
                    } catch (error) {
                        console.error('Error parsing JSON chunk:', error, 'Chunk:', line);
                    }
                }
            }
        } catch (error) {
            console.error('Error sending message:', error);
            const botMessageElement = appendMessage('', 'bot');
            botMessageElement.innerHTML = `<p class="error">Error: ${error.message}</p>`;
        } finally {
            // Re-enable input and hide indicator
            typingIndicator.style.display = 'none';
            sendButton.disabled = false;
            userInput.disabled = false;
            userInput.focus();
        }
    };

    const addCopyButtons = (element) => {
        const codeBlocks = element.querySelectorAll('pre');
        codeBlocks.forEach(block => {
            if (block.querySelector('.copy-button')) return; // Don't add a button if it already has one

            const button = document.createElement('button');
            button.className = 'copy-button';
            button.textContent = 'Copy';

            button.addEventListener('click', () => {
                const code = block.querySelector('code').textContent;
                navigator.clipboard.writeText(code).then(() => {
                    button.textContent = 'Copied!';
                    setTimeout(() => {
                        button.textContent = 'Copy';
                    }, 2000);
                });
            });

            block.style.position = 'relative';
            block.appendChild(button);
        });
    }

    const appendMessage = (text, sender) => {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', `${sender}-message`);

        if (sender === 'user') {
            messageElement.textContent = text;
        } else {
            messageElement.fullContent = text; // Custom property to store raw content
            messageElement.innerHTML = text;
        }

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
