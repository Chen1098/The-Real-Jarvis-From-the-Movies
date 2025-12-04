"""
Data models for WhatsApp integration
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum


class MessageType(Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    STICKER = "sticker"
    LOCATION = "location"
    CONTACT = "contact"
    UNKNOWN = "unknown"


class MessageDirection(Enum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"


@dataclass
class WhatsAppMessage:
    """Represents a WhatsApp message"""
    id: str
    chat_name: str
    sender_name: str
    content: str
    timestamp: datetime
    direction: MessageDirection
    message_type: MessageType = MessageType.TEXT
    media_path: Optional[str] = None
    is_read: bool = False
    is_from_me: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for storage"""
        return {
            'id': self.id,
            'chat_name': self.chat_name,
            'sender_name': self.sender_name,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'direction': self.direction.value,
            'message_type': self.message_type.value,
            'media_path': self.media_path,
            'is_read': self.is_read,
            'is_from_me': self.is_from_me
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'WhatsAppMessage':
        """Create from dictionary"""
        return cls(
            id=data['id'],
            chat_name=data['chat_name'],
            sender_name=data['sender_name'],
            content=data['content'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            direction=MessageDirection(data['direction']),
            message_type=MessageType(data['message_type']),
            media_path=data.get('media_path'),
            is_read=data.get('is_read', False),
            is_from_me=data.get('is_from_me', False)
        )


@dataclass
class WhatsAppContact:
    """Represents a WhatsApp contact"""
    name: str
    phone: Optional[str] = None
    is_group: bool = False
    last_seen: Optional[datetime] = None
    profile_pic_url: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'phone': self.phone,
            'is_group': self.is_group,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'profile_pic_url': self.profile_pic_url
        }


@dataclass
class WhatsAppChat:
    """Represents a WhatsApp chat conversation"""
    contact: WhatsAppContact
    messages: List[WhatsAppMessage] = field(default_factory=list)
    unread_count: int = 0
    last_message_time: Optional[datetime] = None
    is_pinned: bool = False
    is_archived: bool = False

    def add_message(self, message: WhatsAppMessage):
        """Add a message to the chat"""
        self.messages.append(message)
        if message.timestamp:
            self.last_message_time = message.timestamp
        if not message.is_read and not message.is_from_me:
            self.unread_count += 1

    def mark_as_read(self):
        """Mark all messages as read"""
        for msg in self.messages:
            msg.is_read = True
        self.unread_count = 0

    def get_recent_messages(self, count: int = 10) -> List[WhatsAppMessage]:
        """Get the most recent messages"""
        return sorted(self.messages, key=lambda m: m.timestamp, reverse=True)[:count]

    def to_dict(self) -> dict:
        return {
            'contact': self.contact.to_dict(),
            'messages': [m.to_dict() for m in self.messages],
            'unread_count': self.unread_count,
            'last_message_time': self.last_message_time.isoformat() if self.last_message_time else None,
            'is_pinned': self.is_pinned,
            'is_archived': self.is_archived
        }


@dataclass
class WhatsAppNotification:
    """Represents a notification for a new WhatsApp message"""
    chat_name: str
    sender_name: str
    message_preview: str
    timestamp: datetime
    unread_count: int = 1

    def __str__(self) -> str:
        time_str = self.timestamp.strftime("%I:%M %p")
        if self.unread_count > 1:
            return f"[{time_str}] {self.chat_name} - {self.sender_name}: {self.message_preview} (+{self.unread_count-1} more)"
        return f"[{time_str}] {self.chat_name} - {self.sender_name}: {self.message_preview}"
