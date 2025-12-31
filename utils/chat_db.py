"""
SQLite database manager for LLM chat history
Handles chat sessions and message persistence
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import threading

class ChatDatabase:
    """Thread-safe SQLite database for chat history"""
    
    def __init__(self, db_path: str = "data/chat_history.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection"""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn
    
    def _init_db(self):
        """Initialize database schema"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Chat sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                message_count INTEGER DEFAULT 0
            )
        ''')
        
        # Messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT,
                FOREIGN KEY (session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE
            )
        ''')
        
        # Create indexes for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_messages_session 
            ON messages(session_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sessions_updated 
            ON chat_sessions(updated_at DESC)
        ''')
        
        conn.commit()
    
    def create_session(self, title: str = "New Chat") -> int:
        """Create a new chat session"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'INSERT INTO chat_sessions (title) VALUES (?)',
            (title,)
        )
        conn.commit()
        return cursor.lastrowid
    
    def get_session(self, session_id: int) -> Optional[Dict]:
        """Get a specific chat session"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT * FROM chat_sessions WHERE id = ?',
            (session_id,)
        )
        row = cursor.fetchone()
        
        if row:
            return dict(row)
        return None
    
    def list_sessions(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """List all chat sessions, ordered by most recent"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            '''SELECT * FROM chat_sessions 
               ORDER BY updated_at DESC 
               LIMIT ? OFFSET ?''',
            (limit, offset)
        )
        
        return [dict(row) for row in cursor.fetchall()]
    
    def update_session_title(self, session_id: int, title: str) -> bool:
        """Update session title"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            '''UPDATE chat_sessions 
               SET title = ?, updated_at = CURRENT_TIMESTAMP 
               WHERE id = ?''',
            (title, session_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    
    def delete_session(self, session_id: int) -> bool:
        """Delete a chat session and all its messages"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM chat_sessions WHERE id = ?', (session_id,))
        conn.commit()
        return cursor.rowcount > 0
    
    def add_message(self, session_id: int, role: str, content: str, 
                   metadata: Optional[Dict] = None) -> int:
        """Add a message to a session"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Insert message
        metadata_json = json.dumps(metadata) if metadata else None
        cursor.execute(
            '''INSERT INTO messages (session_id, role, content, metadata) 
               VALUES (?, ?, ?, ?)''',
            (session_id, role, content, metadata_json)
        )
        message_id = cursor.lastrowid
        
        # Update session's updated_at and message_count
        cursor.execute(
            '''UPDATE chat_sessions 
               SET updated_at = CURRENT_TIMESTAMP,
                   message_count = message_count + 1
               WHERE id = ?''',
            (session_id,)
        )
        
        conn.commit()
        return message_id
    
    def get_messages(self, session_id: int, limit: int = 100, 
                    offset: int = 0) -> List[Dict]:
        """Get messages for a session"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            '''SELECT * FROM messages 
               WHERE session_id = ? 
               ORDER BY timestamp ASC 
               LIMIT ? OFFSET ?''',
            (session_id, limit, offset)
        )
        
        messages = []
        for row in cursor.fetchall():
            msg = dict(row)
            if msg['metadata']:
                msg['metadata'] = json.loads(msg['metadata'])
            messages.append(msg)
        
        return messages
    
    def get_session_with_messages(self, session_id: int) -> Optional[Dict]:
        """Get session and all its messages"""
        session = self.get_session(session_id)
        if not session:
            return None
        
        session['messages'] = self.get_messages(session_id)
        return session
    
    def search_sessions(self, query: str, limit: int = 20) -> List[Dict]:
        """Search sessions by title"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            '''SELECT * FROM chat_sessions 
               WHERE title LIKE ? 
               ORDER BY updated_at DESC 
               LIMIT ?''',
            (f'%{query}%', limit)
        )
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_total_sessions(self) -> int:
        """Get total number of sessions"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM chat_sessions')
        return cursor.fetchone()[0]
    
    def cleanup_old_sessions(self, keep_count: int = 100) -> int:
        """Keep only the most recent N sessions, delete older ones"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            '''DELETE FROM chat_sessions 
               WHERE id NOT IN (
                   SELECT id FROM chat_sessions 
                   ORDER BY updated_at DESC 
                   LIMIT ?
               )''',
            (keep_count,)
        )
        conn.commit()
        return cursor.rowcount
    
    def generate_title_from_message(self, first_message: str, max_length: int = 50) -> str:
        """Generate a session title from the first message"""
        # Clean up the message
        title = first_message.strip()
        
        # Remove line breaks
        title = ' '.join(title.split())
        
        # Truncate if too long
        if len(title) > max_length:
            title = title[:max_length].rsplit(' ', 1)[0] + '...'
        
        return title or "New Chat"
    
    def close(self):
        """Close database connection"""
        if hasattr(self._local, 'conn'):
            self._local.conn.close()
            delattr(self._local, 'conn')


# Global database instance
_db_instance = None

def get_chat_db() -> ChatDatabase:
    """Get singleton database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = ChatDatabase()
    return _db_instance
