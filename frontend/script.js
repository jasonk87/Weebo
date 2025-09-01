document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Element References ---
    const chatBox = document.getElementById('chat-box');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const typingIndicator = document.getElementById('typing-indicator');
    const welcomeMessage = document.getElementById('welcome-message');
    const proactiveGreeting = document.getElementById('proactive-greeting');
    const proactiveMessage = document.getElementById('proactive-message');
    const proactiveYesBtn = document.getElementById('proactive-yes');
    const proactiveNoBtn = document.getElementById('proactive-no');
    const sessionList = document.getElementById('session-list');
    const newChatButton = document.getElementById('new-chat-button');


    // --- Configuration ---
    // Change this to the URL of your backend server
    const BACKEND_BASE_URL = 'http://localhost:5000';

    // --- State ---
    let activeSessionId = null;

    // --- Main Initialization ---
    function init() {
        sendButton.addEventListener('click', sendMessage);
        userInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !userInput.disabled) sendMessage();
        });

        newChatButton.addEventListener('click', () => {
            startNewChat();
        });

        proactiveYesBtn.addEventListener('click', () => {
            const sessionId = proactiveYesBtn.dataset.sessionId;
            if (sessionId) {
                switchSession(sessionId);
            }
            proactiveGreeting.classList.add('hidden');
        });

        proactiveNoBtn.addEventListener('click', () => {
            startNewChat();
            proactiveGreeting.classList.add('hidden');
        });

        loadSessions();
        showProactiveGreeting();
    }

    // --- Proactive Greeting ---
    async function showProactiveGreeting() {
        try {
            const response = await fetch(`${BACKEND_BASE_URL}/sessions/latest/greeting`);
            if (!response.ok) {
                startNewChat();
                return;
            }
            const data = await response.json();
            if (data.session_id) {
                proactiveMessage.textContent = data.greeting;
                proactiveYesBtn.dataset.sessionId = data.session_id;
                proactiveGreeting.classList.remove('hidden');
                welcomeMessage.classList.add('hidden');
            } else {
                startNewChat();
            }
        } catch (error) {
            console.error('Error fetching greeting:', error);
            startNewChat();
        }
    }


    // --- Session Management ---
    function handleRename(sessionId, li) {
        const titleSpan = li.querySelector('.session-title');
        const currentTitle = titleSpan.textContent;

        const input = document.createElement('input');
        input.type = 'text';
        input.value = currentTitle;
        input.className = 'rename-input';

        titleSpan.style.display = 'none';
        li.prepend(input);
        input.focus();
        input.select();

        const finishEditing = async () => {
            const newTitle = input.value.trim();

            // Revert UI
            li.removeChild(input);
            titleSpan.style.display = 'inline';

            if (newTitle && newTitle !== currentTitle) {
                try {
                    const response = await fetch(`${BACKEND_BASE_URL}/sessions/${sessionId}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ title: newTitle }),
                    });
                    if (!response.ok) throw new Error('Failed to rename session');
                    titleSpan.textContent = newTitle; // Optimistic update
                } catch (error) {
                    console.error('Error renaming session:', error);
                    alert('Error: Could not rename session.');
                    titleSpan.textContent = currentTitle; // Revert on failure
                }
            }
        };

        input.addEventListener('blur', finishEditing);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                input.blur();
            } else if (e.key === 'Escape') {
                input.value = currentTitle;
                input.blur();
            }
        });
    }

    async function handleDelete(sessionId) {
        const confirmed = confirm("Are you sure you want to delete this conversation?");
        if (!confirmed) return;

        try {
            const response = await fetch(`${BACKEND_BASE_URL}/sessions/${sessionId}`, {
                method: 'DELETE',
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to delete session');
            }

            if (activeSessionId === sessionId) {
                activeSessionId = null;
                chatBox.innerHTML = '';
                welcomeMessage.classList.remove('hidden');
                updateActiveSessionInUI();
            }

            await loadSessions(); // Refresh the list
        } catch (error) {
            console.error('Error deleting session:', error);
            alert(`Error: ${error.message}`);
        }
    }

    async function loadSessions() {
        try {
            const response = await fetch(`${BACKEND_BASE_URL}/sessions`);
            if (!response.ok) throw new Error('Failed to load sessions');
            const sessions = await response.json();

            sessionList.innerHTML = '';
            sessions.forEach(session => {
                const li = document.createElement('li');
                li.dataset.sessionId = session.id;
                li.classList.add('session-list-item');

                const titleSpan = document.createElement('span');
                titleSpan.className = 'session-title';
                titleSpan.textContent = session.title || 'New Conversation';
                li.appendChild(titleSpan);

                const actionsDiv = document.createElement('div');
                actionsDiv.className = 'session-actions';

                const renameBtn = document.createElement('button');
                renameBtn.className = 'rename-btn';
                renameBtn.title = 'Rename';
                renameBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather feather-edit-2"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path></svg>`;
                renameBtn.addEventListener('click', (e) => { e.stopPropagation(); handleRename(session.id, li); });
                actionsDiv.appendChild(renameBtn);

                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'delete-btn';
                deleteBtn.title = 'Delete';
                deleteBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather feather-trash-2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>`;
                deleteBtn.addEventListener('click', (e) => { e.stopPropagation(); handleDelete(session.id); });
                actionsDiv.appendChild(deleteBtn);

                li.appendChild(actionsDiv);

                li.addEventListener('click', (e) => {
                    // Don't switch session if an action button was clicked
                    if (e.target.tagName !== 'BUTTON') {
                        switchSession(session.id);
                    }
                });
                sessionList.appendChild(li);
            });
            updateActiveSessionInUI();
        } catch (error) {
            console.error('Error loading sessions:', error);
            sessionList.innerHTML = `<li class="error">Could not load sessions.</li>`;
        }
    }

    async function switchSession(sessionId) {
        if (activeSessionId === sessionId) return;

        activeSessionId = sessionId;
        chatBox.innerHTML = '';
        welcomeMessage.classList.add('hidden');
        proactiveGreeting.classList.add('hidden');
        userInput.disabled = false;
        sendButton.disabled = false;
        userInput.focus();
        updateActiveSessionInUI();

        try {
            const response = await fetch(`${BACKEND_BASE_URL}/sessions/${sessionId}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const history = await response.json();

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
        welcomeMessage.classList.remove('hidden');
        proactiveGreeting.classList.add('hidden');
        userInput.disabled = false;
        sendButton.disabled = false;
        userInput.focus();
        updateActiveSessionInUI();
    }

    // --- Chat Logic ---
    const sendMessage = async () => {
        const messageText = userInput.value.trim();
        if (messageText === '' || !activeSessionId) return;

        welcomeMessage.classList.add('hidden');
        proactiveGreeting.classList.add('hidden');
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
                            botMessageElement.thoughtsContainer.classList.add('visible');
                            botMessageElement.thoughtsContent.textContent += jsonChunk.content + '\n';
                            // Auto-scroll the thoughts container
                            const thoughtsContainer = botMessageElement.querySelector('.thoughts-content');
                            thoughtsContainer.scrollTop = thoughtsContainer.scrollHeight;
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
                <div class="thoughts-container">
                    <div class="thoughts-header">Thinking...</div>
                    <div class="thoughts-content">
                        <pre><code></code></pre>
                    </div>
                </div>
                <div class="answer-container"></div>
            `;
            messageElement.answerContainer = messageElement.querySelector('.answer-container');
            messageElement.thoughtsContainer = messageElement.querySelector('.thoughts-container');
            messageElement.thoughtsContent = messageElement.querySelector('.thoughts-content pre code');
            messageElement.fullContent = '';
        }
        chatBox.appendChild(messageElement);
        chatBox.scrollTop = chatBox.scrollHeight;
        return messageElement;
    };

    // --- UI Helpers ---
    function updateActiveSessionInUI() {
        const listItems = sessionList.querySelectorAll('.session-list-item');
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
