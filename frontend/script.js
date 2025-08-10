document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Element References ---
    const chatBox = document.getElementById('chat-box');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const typingIndicator = document.getElementById('typing-indicator');
    const chatList = document.getElementById('chat-list');
    const newChatBtn = document.getElementById('new-chat-btn');
    const welcomeMessage = document.getElementById('welcome-message');

    // --- State ---
    let activeSessionId = null;
    const BACKEND_BASE_URL = 'http://localhost:5000';

    // --- Main Initialization ---
    function init() {
        sendButton.addEventListener('click', sendMessage);
        userInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !userInput.disabled) sendMessage();
        });
        newChatBtn.addEventListener('click', startNewChat);

        loadSessions();
        renderInitialUI();
    }

    // --- Session Management ---
    async function loadSessions() {
        try {
            const response = await fetch(`${BACKEND_BASE_URL}/sessions`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const sessions = await response.json();

            chatList.innerHTML = ''; // Clear existing list
            sessions.forEach((session, index) => {
                const listItem = document.createElement('div');
                listItem.className = 'chat-list-item';
                listItem.textContent = session.title;
                listItem.dataset.sessionId = session.id;
                listItem.style.animationDelay = `${index * 0.05}s`;
                listItem.addEventListener('click', () => switchSession(session.id));
                chatList.appendChild(listItem);
            });
            updateActiveSessionInUI();
        } catch (error) {
            console.error('Error loading sessions:', error);
            // Optionally, display an error in the sidebar
        }
    }

    async function switchSession(sessionId) {
        if (activeSessionId === sessionId) return;

        activeSessionId = sessionId;
        chatBox.innerHTML = '';
        welcomeMessage.style.display = 'none';
        updateActiveSessionInUI();
        userInput.focus();

        try {
            const response = await fetch(`${BACKEND_BASE_URL}/sessions/${sessionId}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const history = await response.json();

            // Filter out system messages from history rendering
            history.filter(msg => msg.role !== 'system' && msg.role !== 'tool').forEach(message => {
                if (message.role === 'user') {
                    appendMessage(message.content, 'user');
                } else if (message.role === 'assistant') {
                    const botMessageElement = appendMessage('', 'bot');
                    const parsedContent = marked.parse(message.content);
                    botMessageElement.answerContainer.innerHTML = parsedContent;
                    addCopyButtons(botMessageElement.answerContainer);
                }
            });
            chatBox.scrollTop = chatBox.scrollHeight;
        } catch (error) {
            console.error('Error loading session history:', error);
            chatBox.innerHTML = `<p class="error">Could not load session history.</p>`;
        }
    }

    function startNewChat() {
        activeSessionId = crypto.randomUUID();
        chatBox.innerHTML = '';
        welcomeMessage.style.display = 'none';
        updateActiveSessionInUI();
        userInput.focus();
    }

    // --- Chat Logic ---
    const sendMessage = async () => {
        const messageText = userInput.value.trim();
        if (messageText === '' || !activeSessionId) return;

        welcomeMessage.style.display = 'none';
        appendMessage(messageText, 'user');
        userInput.value = '';

        typingIndicator.style.display = 'flex';
        sendButton.disabled = true;
        userInput.disabled = true;

        const botMessageElement = appendMessage('', 'bot');
        let isFirstChunk = true;

        try {
            const response = await fetch(`${BACKEND_BASE_URL}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: messageText, session_id: activeSessionId }),
            });

            if (!response.body) throw new Error('No response body');

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const wasScrolledToBottom = isScrolledToBottom(chatBox);
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop();

                for (const line of lines) {
                    if (line.trim() === '') continue;
                    try {
                        const jsonChunk = JSON.parse(line);

                        if (isFirstChunk) {
                            typingIndicator.style.display = 'none';
                            await loadSessions(); // Use await to ensure list is updated before UI state
                            isFirstChunk = false;
                        }

                        if (jsonChunk.type === 'thought') {
                            botMessageElement.thoughtsContainer.style.display = 'block';
                            const thoughtElement = document.createElement('p');
                            thoughtElement.textContent = jsonChunk.content;
                            botMessageElement.thoughtsContent.appendChild(thoughtElement);
                            botMessageElement.thoughtsContent.scrollTop = botMessageElement.thoughtsContent.scrollHeight;
                        } else if (jsonChunk.type === 'answer_chunk') {
                            botMessageElement.fullContent += jsonChunk.content;
                            botMessageElement.answerContainer.innerHTML = marked.parse(botMessageElement.fullContent);
                            botMessageElement.answerContainer.querySelectorAll('pre code').forEach(hljs.highlightElement);
                            addCopyButtons(botMessageElement.answerContainer);
                        } else if (jsonChunk.type === 'error') {
                            botMessageElement.answerContainer.innerHTML = `<p class="error">Error: ${jsonChunk.content}</p>`;
                            return;
                        }
                    } catch (error) {
                        console.error('Error parsing JSON chunk:', error, 'Chunk:', line);
                    }
                }
                if (wasScrolledToBottom) chatBox.scrollTop = chatBox.scrollHeight;
            }
        } catch (error) {
            console.error('Error sending message:', error);
            botMessageElement.answerContainer.innerHTML = `<p class="error">Error: ${error.message}</p>`;
        } finally {
            typingIndicator.style.display = 'none';
            sendButton.disabled = false;
            userInput.disabled = false;
            userInput.focus();
            updateActiveSessionInUI();
        }
    };

    const appendMessage = (text, sender) => {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', `${sender}-message`);

        if (sender === 'user') {
            messageElement.textContent = text;
        } else {
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
            messageElement.fullContent = '';
        }
        chatBox.appendChild(messageElement);
        chatBox.scrollTop = chatBox.scrollHeight;
        return messageElement;
    };

    // --- UI Helpers ---
    function renderInitialUI() {
        activeSessionId = null;
        chatBox.innerHTML = '';
        welcomeMessage.style.display = 'flex';
        userInput.disabled = true;
        sendButton.disabled = true;
        updateActiveSessionInUI();
    }

    function updateActiveSessionInUI() {
        const listItems = chatList.querySelectorAll('.chat-list-item');
        listItems.forEach(item => {
            item.classList.toggle('active', item.dataset.sessionId === activeSessionId);
        });

        const isInputDisabled = !activeSessionId;
        userInput.disabled = isInputDisabled;
        sendButton.disabled = isInputDisabled;
    }

    // --- Utility Functions ---
    const isScrolledToBottom = (element) => {
        const buffer = 10;
        return element.scrollHeight - element.scrollTop <= element.clientHeight + buffer;
    };

    const addCopyButtons = (element) => {
        const codeBlocks = element.querySelectorAll('pre');
        codeBlocks.forEach(block => {
            if (block.querySelector('.copy-button')) return;
            const button = document.createElement('button');
            button.className = 'copy-button';
            button.textContent = 'Copy';
            button.addEventListener('click', () => {
                const code = block.querySelector('code').textContent;
                navigator.clipboard.writeText(code).then(() => {
                    button.textContent = 'Copied!';
                    setTimeout(() => { button.textContent = 'Copy'; }, 2000);
                });
            });
            block.style.position = 'relative';
            block.appendChild(button);
        });
    };

    init();
});
