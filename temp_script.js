
        let conversationHistory = [];
        let isLoading = false;
        let currentSessionId = null;
        let allSessions = [];

        // Auto-resize textarea
        function autoResize(textarea) {
            textarea.style.height = 'auto';
            textarea.style.height = textarea.scrollHeight + 'px';
            
            const sendBtn = document.getElementById('sendBtn');
            sendBtn.disabled = !textarea.value.trim();
        }

        // Handle key press
        function handleKeyPress(event) {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                sendMessage();
            }
        }

        // Start new chat
        async function startNewChat() {
            conversationHistory = [];
            currentSessionId = null;
            
            // Update UI to show active state
            const chatItems = document.querySelectorAll('.chat-item');
            chatItems.forEach(item => item.classList.remove('active'));
            
            const messagesWrapper = document.getElementById('messagesWrapper');
            messagesWrapper.innerHTML = `
                <div class="empty-state" id="emptyState">
                    <div class="empty-state-icon">ðŸŽ¯</div>
                    <h2>What can I help you analyze today?</h2>
                    <p>I can analyze odds data, identify betting opportunities, compare bookmakers, and provide insights from your unified and OddsMagnet data.</p>
                    
                    <div class="suggestions-grid">
                        <div class="suggestion-card" onclick="sendSuggestion('Show me the highest odds available in OddsMagnet right now')">
                            <div class="suggestion-icon">ðŸ“ˆ</div>
                            <div class="suggestion-title">Highest Odds</div>
                            <div class="suggestion-desc">Find the best value bets across all bookmakers</div>
                        </div>
                        <div class="suggestion-card" onclick="sendSuggestion('Which matches have odds above 2.0 from OddsMagnet?')">
                            <div class="suggestion-icon">ðŸŽ²</div>
                            <div class="suggestion-title">Value Matches</div>
                            <div class="suggestion-desc">Discover matches with favorable odds</div>
                        </div>
                        <div class="suggestion-card" onclick="sendSuggestion('Compare coverage between unified data and OddsMagnet')">
                            <div class="suggestion-icon">ðŸ“Š</div>
                            <div class="suggestion-title">Data Coverage</div>
                            <div class="suggestion-desc">Analyze data sources and coverage rates</div>
                        </div>
                        <div class="suggestion-card" onclick="sendSuggestion('Show me live matches with the best odds right now')">
                            <div class="suggestion-icon">âš¡</div>
                            <div class="suggestion-title">Live Opportunities</div>
                            <div class="suggestion-desc">Real-time betting opportunities</div>
                        </div>
                    </div>
                </div>
            `;
        }

        // Send suggestion
        function sendSuggestion(text) {
            document.getElementById('messageInput').value = text;
            sendMessage();
        }

        // Send quick action
        function sendQuickAction(action) {
            const questions = {
                'Status check': 'What is the current status of the data collection?',
                'Quick analysis': 'Give me a quick analysis of the current odds data',
                'Best odds': 'Show me the highest odds available right now',
                'Live matches': 'What live matches are currently available?'
            };
            sendSuggestion(questions[action] || action);
        }

        // Add message to UI
        function addMessage(role, content) {
            const emptyState = document.getElementById('emptyState');
            if (emptyState) {
                emptyState.remove();
            }

            const messagesWrapper = document.getElementById('messagesWrapper');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message';
            
            const avatar = role === 'user' ? 'Y' : 'âš¡';
            const roleLabel = role === 'user' ? 'You' : 'OddsFlow AI';
            
            messageDiv.innerHTML = `
                <div class="message-header">
                    <div class="message-avatar ${role}">${avatar}</div>
                    <div class="message-role">${roleLabel}</div>
                </div>
                <div class="message-content">${formatContent(content)}</div>
            `;
            
            messagesWrapper.appendChild(messageDiv);
            scrollToBottom();
        }

        // Format message content
        function formatContent(content) {
            if (typeof content === 'string') {
                // Convert markdown-style formatting
                content = content
                    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                    .replace(/\*(.*?)\*/g, '<em>$1</em>')
                    .replace(/`(.*?)`/g, '<code>$1</code>')
                    .replace(/\n/g, '<br>');
                
                return content;
            }
            return content;
        }

        // Show typing indicator
        function showTyping() {
            const messagesWrapper = document.getElementById('messagesWrapper');
            const typingDiv = document.createElement('div');
            typingDiv.id = 'typingIndicator';
            typingDiv.innerHTML = `
                <div class="message">
                    <div class="message-header">
                        <div class="message-avatar ai">âš¡</div>
                        <div class="message-role">OddsFlow AI</div>
                    </div>
                    <div class="typing-indicator">
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                    </div>
                </div>
            `;
            messagesWrapper.appendChild(typingDiv);
            scrollToBottom();
        }

        // Hide typing indicator
        function hideTyping() {
            const typing = document.getElementById('typingIndicator');
            if (typing) typing.remove();
        }

        // Scroll to bottom
        function scrollToBottom() {
            const chatContainer = document.getElementById('chatContainer');
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }

        // Update status
        function updateStatus(status, type = 'success') {
            const statusBadge = document.getElementById('statusBadge');
            const colors = {
                success: 'var(--success)',
                error: 'var(--error)',
                warning: 'var(--warning)',
                info: 'var(--accent-primary)'
            };
            
            statusBadge.innerHTML = `
                <div class="status-dot" style="background: ${colors[type]}"></div>
                <span>${status}</span>
            `;
        }

        // Load chat sessions from database
        async function loadChatSessions() {
            try {
                const response = await fetch('/api/chat/sessions?limit=50');
                const data = await response.json();
                
                if (data.success) {
                    allSessions = data.sessions;
                    renderChatHistory();
                }
            } catch (error) {
                console.error('Failed to load chat sessions:', error);
            }
        }
        
        // Render chat history in sidebar
        function renderChatHistory() {
            const chatHistory = document.getElementById('chatHistory');
            
            if (allSessions.length === 0) {
                chatHistory.innerHTML = '<div class="chat-item" style="color: var(--text-tertiary); text-align: center;">No chat history yet</div>';
                return;
            }
            
            chatHistory.innerHTML = allSessions.map(session => {
                const isActive = session.id === currentSessionId;
                const date = new Date(session.updated_at);
                const timeAgo = formatTimeAgo(date);
                
                return `
                    <div class="chat-item ${isActive ? 'active' : ''}" 
                         onclick="loadChatSession(${session.id})"
                         title="${session.title}">
                        <div class="chat-item-title">${session.title}</div>
                        <div style="font-size: 11px; color: var(--text-tertiary); margin-top: 4px;">
                            ${timeAgo} â€¢ ${session.message_count} msgs
                        </div>
                        <div class="chat-item-actions" onclick="event.stopPropagation()">
                            <button class="chat-action-btn" onclick="renameSession(${session.id})" title="Rename">
                                âœï¸
                            </button>
                            <button class="chat-action-btn delete" onclick="deleteSession(${session.id})" title="Delete">
                                ðŸ—‘ï¸
                            </button>
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        // Format time ago
        function formatTimeAgo(date) {
            const seconds = Math.floor((new Date() - date) / 1000);
            
            if (seconds < 60) return 'Just now';
            if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
            if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
            if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
            
            return date.toLocaleDateString();
        }
        
        // Load a specific chat session
        async function loadChatSession(sessionId) {
            try {
                const response = await fetch(`/api/chat/sessions/${sessionId}`);
                const data = await response.json();
                
                if (data.success) {
                    currentSessionId = sessionId;
                    conversationHistory = [];
                    
                    // Clear messages
                    const messagesWrapper = document.getElementById('messagesWrapper');
                    messagesWrapper.innerHTML = '';
                    async () => {
            await loadStatus();
            await loadChatSession/ Load all messages
                    data.session.messages.forEach(msg => {
                        addMessage(msg.role === 'user' ? 'user' : 'ai', msg.content);
                        conversationHistory.push({ role: msg.role, content: msg.content });
                    });
                    
                    // Update sidebar
                    renderChatHistory();
                    
                    // Scroll to bottom
                    scrollToBottom();
                }
            } catch (error) {
                console.error('Failed to load chat session:', error);
                updateStatus('Error loading chat', 'error');
            }
        }
        
        // Delete chat session
        async function deleteSession(sessionId) {
            if (!confirm('Delete this chat? This cannot be undone.')) return;
            
            try {
                const response = await fetch(`/api/chat/sessions/${sessionId}`, {
                    method: 'DELETE'
                });
                
                const data = await response.json();
                
                if (data.success) {
                    // If deleted current session, start new chat
                    if (sessionId === currentSessionId) {
                        startNewChat();
                    }
                    
                    // Reload sessions
                    await loadChatSessions();
                }
            } catch (error) {
                console.error('Failed to delete session:', error);
            }
        }
        
        // Rename chat session
        async function renameSession(sessionId) {
            const session = allSessions.find(s => s.id === sessionId);
            if (!session) return;
            
            const newTitle = prompt('Enter new title:', session.title);
            if (!newTitle || newTitle === session.title) return;
            
            try {
                const response = await fetch(`/api/chat/sessions/${sessionId}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ title: newTitle })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    await loadChatSessions();
                }
            } catch (error) {
                console.error('Failed to rename session:', error);
            }
        }
        
        // Show context menu for session
        function showSessionMenu(event, sessionId) {
            event.preventDefault();
            
            // Simple context menu using confirm/prompt
            const action = confirm('Delete this chat? (OK = Delete, Cancel = Rename)');
            
            if (action) {
                deleteSession(sessionId);
            } else {
                renameSession(sessionId);
            }
        }
        
        // Send message
        async function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            
            if (!message || isLoading) return;
            
            // Add user message to UI immediately
            addMessage('user', message);
            
            // Clear input
            input.value = '';
            input.style.height = 'auto';
            document.getElementById('sendBtn').disabled = true;
            
            // Show loading
            isLoading = true;
            showTyping();
            updateStatus('Analyzing...', 'info');
            
            try {
                const response = await fetch('/api/llm/ask', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ 
                        question: message,
                        session_id: currentSessionId 
                    })
                });
                
                const data = await response.json();
                
                hideTyping();
                
                if (data.success) {
                    // Update current session ID if this was a new chat
                    if (data.session_id && !currentSessionId) {
                        currentSessionId = data.session_id;
                        // Reload sessions to show the new chat
                        await loadChatSessions();
                    }
                    
                    addMessage('ai', data.answer);
                    conversationHistory.push({ role: 'user', content: message });
                    conversationHistory.push({ role: 'assistant', content: data.answer });
                    updateStatus('Ready', 'success');
                } else {
                    addMessage('ai', `Error: ${data.error || 'Failed to get response'}`);
                    updateStatus('Error', 'error');
                }
            } catch (error) {
                hideTyping();
                addMessage('ai', `Error: ${error.message}`);
                updateStatus('Error', 'error');
            } finally {
                isLoading = false;
            }
        }

        // Load initial status
        async function loadStatus() {
            try {
                const response = await fetch('/api/llm/status');
                const data = await response.json();
                
                if (data.llm_initialized) {
                    updateStatus('Ready', 'success');
                } else {
                    updateStatus('Initializing...', 'warning');
                }
            } catch (error) {
                updateStatus('Offline', 'error');
            }
        }

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            loadStatus();
            
            // Focus input
            const input = document.getElementById('messageInput');
            input.focus();
        });
    
