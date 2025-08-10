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

        const botMessageElement = appendMessage('', 'bot');

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
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const wasScrolledToBottom = isScrolledToBottom(chatBox);

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');

                buffer = lines.pop(); // Keep the last, possibly incomplete, line

                for (const line of lines) {
                    if (line.trim() === '') continue;
                    try {
                        const jsonChunk = JSON.parse(line);

                        // Hide typing indicator on first chunk
                        if (typingIndicator.style.display !== 'none') {
                            typingIndicator.style.display = 'none';
                        }

                        if (jsonChunk.type === 'thought') {
                            const thoughtsContent = botMessageElement.thoughtsContent;
                            const thoughtScrolledToBottom = isScrolledToBottom(thoughtsContent);

                            botMessageElement.thoughtsContainer.style.display = 'block';
                            const thoughtElement = document.createElement('p');
                            thoughtElement.textContent = jsonChunk.content;
                            thoughtsContent.appendChild(thoughtElement);

                            if (thoughtScrolledToBottom) {
                                thoughtsContent.scrollTop = thoughtsContent.scrollHeight;
                            }
                        } else if (jsonChunk.type === 'answer_chunk') {
                            botMessageElement.fullContent += jsonChunk.content;
                            botMessageElement.answerContainer.innerHTML = marked.parse(botMessageElement.fullContent);
                            botMessageElement.answerContainer.querySelectorAll('pre code').forEach((block) => {
                                hljs.highlightElement(block);
                            });
                            addCopyButtons(botMessageElement.answerContainer);
                        } else if (jsonChunk.type === 'error') {
                            botMessageElement.answerContainer.innerHTML = `<p class="error">Error: ${jsonChunk.content}</p>`;
                            return;
                        }

                    } catch (error) {
                        console.error('Error parsing JSON chunk:', error, 'Chunk:', line);
                    }
                }

                if (wasScrolledToBottom) {
                    chatBox.scrollTop = chatBox.scrollHeight;
                }
            }
        } catch (error) {
            console.error('Error sending message:', error);
            botMessageElement.answerContainer.innerHTML = `<p class="error">Error: ${error.message}</p>`;
        } finally {
            // Re-enable input and hide indicator
            typingIndicator.style.display = 'none';
            sendButton.disabled = false;
            userInput.disabled = false;
            userInput.focus();
        }
    };

    const isScrolledToBottom = (element) => {
        // A little buffer for pixel-perfect scrolling issues
        const buffer = 10;
        return element.scrollHeight - element.scrollTop <= element.clientHeight + buffer;
    }

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
            // Create the new structure for bot messages
            messageElement.innerHTML = `
                <div class="thoughts-container" style="display: none;">
                    <div class="thoughts-header">Thinking...</div>
                    <div class="thoughts-content"></div>
                </div>
                <div class="answer-container"></div>
            `;
            messageElement.answerContainer = messageElement.querySelector('.answer-container');
            messageElement.thoughtsContainer = messageElement.querySelector('.thoughts-container');
            messageElement.thoughtsContent = messageElement.querySelector('.thoughts-content');
            messageElement.fullContent = ''; // To store the raw answer markdown
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
