const chatMessages = document.getElementById('chatMessages');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
let chatHistory = [];

function addMessage(message, isUser) {
    // Remove welcome message if it exists
    const welcomeMsg = document.querySelector('.welcome-message');
    if (welcomeMsg) {
        welcomeMsg.remove();
    }

    const messageWrapper = document.createElement('div');
    messageWrapper.className = `message-wrapper ${isUser ? 'user' : 'assistant'}`;

    const avatar = document.createElement('div');
    avatar.className = `avatar ${isUser ? 'user' : 'assistant'}`;
    avatar.textContent = isUser ? 'U' : 'AI';

    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    messageContent.textContent = message;

    messageWrapper.appendChild(avatar);
    messageWrapper.appendChild(messageContent);
    chatMessages.appendChild(messageWrapper);

    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showTypingIndicator() {
    const messageWrapper = document.createElement('div');
    messageWrapper.className = 'message-wrapper assistant typing';
    messageWrapper.id = 'typingIndicator';

    const avatar = document.createElement('div');
    avatar.className = 'avatar assistant';
    avatar.textContent = 'AI';

    const typingDiv = document.createElement('div');
    typingDiv.className = 'typing-indicator';
    typingDiv.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';

    messageWrapper.appendChild(avatar);
    messageWrapper.appendChild(typingDiv);
    chatMessages.appendChild(messageWrapper);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) {
        indicator.remove();
    }
}

async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message) return;

    // Disable input while processing
    sendButton.disabled = true;
    messageInput.disabled = true;

    addMessage(message, true);
    chatHistory.push({ role: 'user', content: message });
    messageInput.value = '';
    autoResize();

    showTypingIndicator();

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message }),
        });

        removeTypingIndicator();

        if (!response.ok) {
            throw new Error('Server error');
        }

        const data = await response.json();
        addMessage(data.response, false);
        chatHistory.push({ role: 'assistant', content: data.response });
        
        // Update chat history in sidebar
        updateSidebarHistory(message);
    } catch (error) {
        removeTypingIndicator();
        addMessage('❌ Error: Unable to connect to the server. Make sure the backend is running.', false);
    } finally {
        // Re-enable input
        sendButton.disabled = false;
        messageInput.disabled = false;
        messageInput.focus();
    }
}

function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

function autoResize() {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 200) + 'px';
}

function newChat() {
    chatMessages.innerHTML = '<div class="welcome-message"><h1>How can I help you today?</h1></div>';
    chatHistory = [];
    messageInput.value = '';
    autoResize();
}

function updateSidebarHistory(message) {
    const historyList = document.getElementById('historyList');
    const historyItem = document.createElement('div');
    historyItem.className = 'history-item';
    historyItem.textContent = message.substring(0, 30) + (message.length > 30 ? '...' : '');
    historyList.insertBefore(historyItem, historyList.firstChild);
}

// Auto-resize textarea on input
messageInput.addEventListener('input', autoResize);

// Focus input on load
messageInput.focus();
