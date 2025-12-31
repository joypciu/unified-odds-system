# Chat History System - SQLite Integration

## Overview

The LLM Analysis page now includes a complete chat history system with SQLite database persistence, enabling seamless conversation management similar to ChatGPT, Claude, and Grok.

## Features Implemented

### 1. **SQLite Database Backend** (`utils/chat_db.py`)

**Schema:**

- `chat_sessions` table:

  - `id` - Unique session identifier
  - `title` - Auto-generated or custom chat title
  - `created_at` - Session creation timestamp
  - `updated_at` - Last message timestamp
  - `message_count` - Total messages in session

- `messages` table:
  - `id` - Message identifier
  - `session_id` - Foreign key to chat_sessions
  - `role` - 'user' or 'assistant'
  - `content` - Message text
  - `timestamp` - Message creation time
  - `metadata` - JSON metadata (used_real_data, etc.)

**Key Methods:**

- `create_session(title)` - Create new chat
- `list_sessions(limit, offset)` - Paginated session list
- `get_session_with_messages(id)` - Load full conversation
- `add_message(session_id, role, content)` - Save message
- `update_session_title(id, title)` - Rename chat
- `delete_session(id)` - Delete chat and messages
- `search_sessions(query)` - Search by title
- `generate_title_from_message()` - Auto-title from first message

**Optimizations:**

- Thread-safe connection pooling
- Indexed queries for fast lookups
- Cascading deletes for data integrity
- Automatic session timestamp updates

### 2. **FastAPI Endpoints** (`core/live_odds_viewer_clean.py`)

```
GET  /api/chat/sessions          - List all chat sessions
POST /api/chat/sessions          - Create new session
GET  /api/chat/sessions/{id}     - Get session with messages
PUT  /api/chat/sessions/{id}     - Rename session
DELETE /api/chat/sessions/{id}   - Delete session
GET  /api/chat/search?q=query    - Search sessions
POST /api/llm/ask                - Send message (auto-saves to DB)
```

**Enhanced `/api/llm/ask` endpoint:**

- Accepts `session_id` parameter
- Auto-creates session if not provided
- Generates title from first message
- Saves both user and assistant messages
- Returns `session_id` in response

### 3. **Frontend Features** (`html/llm_analysis_v2.html`)

**Sidebar Chat History:**

- ✅ Real-time session list (50 most recent)
- ✅ Active session highlighting
- ✅ Message count and timestamp display
- ✅ "Time ago" formatting (Just now, 5m ago, 2h ago, etc.)
- ✅ Hover actions: Rename ✏️ and Delete 🗑️
- ✅ Click to switch between chats
- ✅ "New Chat" button to start fresh conversation

**Session Management:**

- ✅ Auto-save all messages to database
- ✅ Persistent conversation history
- ✅ Load previous chats on click
- ✅ Rename chats with custom titles
- ✅ Delete unwanted conversations
- ✅ Auto-generated titles from first message
- ✅ Session updates on every message

**UI Improvements:**

- Clean action buttons with emoji icons
- Smooth transitions between chats
- Empty state when no history exists
- Active session visual indicator
- Hover effects on chat items
- Timestamp formatting

## Usage Examples

### Starting a New Chat

1. Click "➕ New Chat" button
2. Ask a question
3. Session auto-created with title from question
4. Appears in sidebar immediately

### Switching Between Chats

1. Click any chat in sidebar
2. Messages load instantly
3. Continue conversation from where you left off
4. All context preserved

### Renaming a Chat

1. Hover over chat item
2. Click ✏️ (edit) button
3. Enter new title
4. Saves automatically

### Deleting a Chat

1. Hover over chat item
2. Click 🗑️ (delete) button
3. Confirm deletion
4. Chat and all messages removed

## Performance Optimizations

### Database

- **Indexed Queries**: Fast lookups by session_id and updated_at
- **Prepared Statements**: SQL injection prevention
- **Thread-Safe**: Multiple concurrent requests handled safely
- **Connection Pooling**: Thread-local connections
- **Cascading Deletes**: Automatic message cleanup

### API

- **Pagination**: Limit 50 sessions by default (configurable)
- **Lazy Loading**: Messages only loaded when session opened
- **Efficient Updates**: Timestamp updates in same transaction
- **Error Handling**: Graceful failures with user feedback

### Frontend

- **Async Operations**: Non-blocking UI updates
- **Optimistic UI**: Immediate feedback before server response
- **Smart Rendering**: Only re-render changed elements
- **Memory Management**: Old messages not kept in memory
- **Debounced Actions**: Prevent duplicate API calls

## Data Flow

### New Message Flow:

```
1. User types message →
2. UI adds to screen immediately →
3. POST /api/llm/ask with session_id →
4. Backend saves user message to DB →
5. LLM generates response →
6. Backend saves AI response to DB →
7. Updates session timestamp →
8. Returns response + session_id →
9. UI updates conversation →
10. Sidebar refreshes session list
```

### Load Chat Flow:

```
1. User clicks chat in sidebar →
2. GET /api/chat/sessions/{id} →
3. Database returns session + all messages →
4. UI clears current chat →
5. Renders all messages in order →
6. Updates active state in sidebar →
7. Scrolls to bottom
```

## Database Location

- **Path**: `data/chat_history.db`
- **Size**: ~10KB per 100 messages
- **Backup**: Recommend periodic exports
- **Migration**: SQLite file is portable

## Future Enhancements

### Potential Improvements:

1. **Search Functionality** - Full-text search across messages
2. **Export Chats** - Download as JSON/PDF
3. **Sharing** - Share chat links
4. **Folders/Tags** - Organize chats by category
5. **Archive** - Hide old chats without deletion
6. **Cloud Sync** - Multi-device synchronization
7. **Auto-Cleanup** - Delete chats older than X days
8. **Analytics** - Usage statistics and insights
9. **Voice Input** - Speech-to-text for questions
10. **Favorites** - Pin important conversations

### Advanced Features:

- LLM-generated titles (using Gemini API)
- Conversation summarization
- Semantic search across all chats
- Chat templates for common queries
- Collaborative chats (multi-user)
- Version history for edited messages
- Message reactions/feedback

## API Testing

### Create Session:

```bash
curl -X POST http://localhost:8000/api/chat/sessions \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Chat"}'
```

### List Sessions:

```bash
curl http://localhost:8000/api/chat/sessions?limit=10
```

### Send Message:

```bash
curl -X POST http://localhost:8000/api/llm/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Show me the highest odds", "session_id": 1}'
```

### Delete Session:

```bash
curl -X DELETE http://localhost:8000/api/chat/sessions/1
```

## Troubleshooting

**Chat history not loading:**

- Check `data/chat_history.db` exists
- Verify database permissions
- Check browser console for errors

**Messages not saving:**

- Ensure server has write access to `data/` folder
- Check for SQLite errors in server logs
- Verify session_id is valid

**Performance issues:**

- Check database size (`data/chat_history.db`)
- Run cleanup: `db.cleanup_old_sessions(100)`
- Consider pagination for large histories

## Technical Stack

- **Database**: SQLite 3
- **Backend**: FastAPI + Python 3.8+
- **Frontend**: Vanilla JavaScript (ES6+)
- **Styling**: CSS Grid + Flexbox
- **Icons**: Unicode Emoji (✏️, 🗑️, ⚡)

## Conclusion

The chat history system provides a professional, production-ready conversation management experience matching the quality of leading AI chat platforms. All conversations are persisted, searchable, and fully manageable through an intuitive interface.

---

**Last Updated**: December 31, 2025  
**Status**: ✅ Production Ready  
**Database**: SQLite (chat_history.db)
