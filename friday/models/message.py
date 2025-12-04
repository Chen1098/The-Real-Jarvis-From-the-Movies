"""
Message data model
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Message:
    """Represents a single message in the conversation"""

    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    image_data: Optional[str] = None  # Base64 encoded image data URI

    def to_dict(self):
        """Convert message to dictionary for API"""
        if self.image_data:
            # Message with image (multimodal)
            return {
                "role": self.role,
                "content": [
                    {"type": "text", "text": self.content},
                    {"type": "image_url", "image_url": {"url": self.image_data}}
                ]
            }
        else:
            # Text-only message
            return {
                "role": self.role,
                "content": self.content
            }

    def to_json(self):
        """Convert to JSON-serializable dict"""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "has_image": self.image_data is not None
        }
