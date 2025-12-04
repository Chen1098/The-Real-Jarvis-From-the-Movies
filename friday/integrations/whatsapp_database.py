"""
WhatsApp chat history storage and retrieval
"""

import json
import sqlite3
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from friday.integrations.whatsapp_models import WhatsAppMessage, WhatsAppContact, WhatsAppChat, MessageDirection, MessageType
from friday.utils.logger import get_logger

logger = get_logger("whatsapp_db")


class WhatsAppDatabase:
    """SQLite database for storing WhatsApp chat history"""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path.home() / "AppData" / "Local" / "Friday" / "whatsapp_history.db"

        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.conn = None
        self._initialize_db()

    def _initialize_db(self):
        """Create database tables if they don't exist"""
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        cursor = self.conn.cursor()

        # Contacts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                name TEXT PRIMARY KEY,
                phone TEXT,
                is_group INTEGER,
                last_seen TEXT,
                profile_pic_url TEXT
            )
        """)

        # Messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                chat_name TEXT,
                sender_name TEXT,
                content TEXT,
                timestamp TEXT,
                direction TEXT,
                message_type TEXT,
                media_path TEXT,
                is_read INTEGER,
                is_from_me INTEGER,
                FOREIGN KEY (chat_name) REFERENCES contacts(name)
            )
        """)

        # Create indexes for faster queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_timestamp ON messages(chat_name, timestamp DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON messages(timestamp DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_unread ON messages(is_read, is_from_me)")

        self.conn.commit()
        logger.info(f"WhatsApp database initialized at {self.db_path}")

    def save_contact(self, contact: WhatsAppContact):
        """Save or update a contact"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO contacts (name, phone, is_group, last_seen, profile_pic_url)
            VALUES (?, ?, ?, ?, ?)
        """, (
            contact.name,
            contact.phone,
            1 if contact.is_group else 0,
            contact.last_seen.isoformat() if contact.last_seen else None,
            contact.profile_pic_url
        ))
        self.conn.commit()

    def save_message(self, message: WhatsAppMessage):
        """Save a message to the database"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO messages
            (id, chat_name, sender_name, content, timestamp, direction, message_type, media_path, is_read, is_from_me)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            message.id,
            message.chat_name,
            message.sender_name,
            message.content,
            message.timestamp.isoformat(),
            message.direction.value,
            message.message_type.value,
            message.media_path,
            1 if message.is_read else 0,
            1 if message.is_from_me else 0
        ))
        self.conn.commit()

    def get_messages_by_chat(self, chat_name: str, limit: int = 100) -> List[WhatsAppMessage]:
        """Get messages from a specific chat"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM messages
            WHERE chat_name = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (chat_name, limit))

        messages = []
        for row in cursor.fetchall():
            messages.append(self._row_to_message(row))

        return messages

    def get_recent_messages(self, limit: int = 50) -> List[WhatsAppMessage]:
        """Get most recent messages across all chats"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM messages
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))

        messages = []
        for row in cursor.fetchall():
            messages.append(self._row_to_message(row))

        return messages

    def get_unread_messages(self) -> List[WhatsAppMessage]:
        """Get all unread messages"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM messages
            WHERE is_read = 0 AND is_from_me = 0
            ORDER BY timestamp DESC
        """)

        messages = []
        for row in cursor.fetchall():
            messages.append(self._row_to_message(row))

        return messages

    def mark_message_read(self, message_id: str):
        """Mark a specific message as read"""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE messages SET is_read = 1 WHERE id = ?", (message_id,))
        self.conn.commit()

    def mark_chat_read(self, chat_name: str):
        """Mark all messages in a chat as read"""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE messages SET is_read = 1 WHERE chat_name = ? AND is_from_me = 0", (chat_name,))
        self.conn.commit()

    def search_messages(self, query: str, limit: int = 50) -> List[WhatsAppMessage]:
        """Search messages by content"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM messages
            WHERE content LIKE ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (f"%{query}%", limit))

        messages = []
        for row in cursor.fetchall():
            messages.append(self._row_to_message(row))

        return messages

    def get_messages_by_date(self, date: datetime, chat_name: Optional[str] = None) -> List[WhatsAppMessage]:
        """Get messages from a specific date"""
        start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)

        cursor = self.conn.cursor()
        if chat_name:
            cursor.execute("""
                SELECT * FROM messages
                WHERE chat_name = ? AND timestamp >= ? AND timestamp < ?
                ORDER BY timestamp ASC
            """, (chat_name, start_date.isoformat(), end_date.isoformat()))
        else:
            cursor.execute("""
                SELECT * FROM messages
                WHERE timestamp >= ? AND timestamp < ?
                ORDER BY timestamp ASC
            """, (start_date.isoformat(), end_date.isoformat()))

        messages = []
        for row in cursor.fetchall():
            messages.append(self._row_to_message(row))

        return messages

    def get_chat_statistics(self, chat_name: str) -> Dict:
        """Get statistics for a specific chat"""
        cursor = self.conn.cursor()

        cursor.execute("SELECT COUNT(*) as total FROM messages WHERE chat_name = ?", (chat_name,))
        total = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) as sent FROM messages WHERE chat_name = ? AND is_from_me = 1", (chat_name,))
        sent = cursor.fetchone()['sent']

        cursor.execute("SELECT COUNT(*) as received FROM messages WHERE chat_name = ? AND is_from_me = 0", (chat_name,))
        received = cursor.fetchone()['received']

        cursor.execute("SELECT MIN(timestamp) as first_msg FROM messages WHERE chat_name = ?", (chat_name,))
        first_msg = cursor.fetchone()['first_msg']

        return {
            'chat_name': chat_name,
            'total_messages': total,
            'sent': sent,
            'received': received,
            'first_message': first_msg
        }

    def get_all_chats(self) -> List[str]:
        """Get list of all chat names"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT chat_name FROM messages ORDER BY chat_name")
        return [row['chat_name'] for row in cursor.fetchall()]

    def _row_to_message(self, row: sqlite3.Row) -> WhatsAppMessage:
        """Convert database row to WhatsAppMessage object"""
        return WhatsAppMessage(
            id=row['id'],
            chat_name=row['chat_name'],
            sender_name=row['sender_name'],
            content=row['content'],
            timestamp=datetime.fromisoformat(row['timestamp']),
            direction=MessageDirection(row['direction']),
            message_type=MessageType(row['message_type']),
            media_path=row['media_path'],
            is_read=bool(row['is_read']),
            is_from_me=bool(row['is_from_me'])
        )

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("WhatsApp database connection closed")

    def __del__(self):
        """Cleanup on deletion"""
        self.close()
