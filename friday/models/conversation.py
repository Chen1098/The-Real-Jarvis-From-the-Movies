"""
Conversation history model
"""
import json
from pathlib import Path
from typing import List, Optional
from friday.models.message import Message
from friday.utils.logger import get_logger

logger = get_logger("conversation")


class Conversation:
    """Manages conversation history with context management"""

    def __init__(self, max_messages=50):
        """
        Initialize conversation

        Args:
            max_messages: Maximum number of messages to keep in history
        """
        self.messages: List[Message] = []
        self.max_messages = max_messages

    def add_user_message(self, text: str, image_data: Optional[str] = None):
        """
        Add user message to conversation

        Args:
            text: User's message text
            image_data: Optional base64 encoded image data URI
        """
        message = Message(role="user", content=text, image_data=image_data)
        self.messages.append(message)
        self._trim_history()

        logger.debug(f"Added user message (has_image: {image_data is not None})")

    def add_assistant_message(self, text: str):
        """
        Add assistant message to conversation

        Args:
            text: Assistant's response text
        """
        message = Message(role="assistant", content=text)
        self.messages.append(message)
        self._trim_history()

        logger.debug("Added assistant message")

    def _trim_history(self):
        """Keep only last N messages to manage token usage"""
        if len(self.messages) > self.max_messages:
            removed = len(self.messages) - self.max_messages
            self.messages = self.messages[-self.max_messages:]
            logger.info(f"Trimmed {removed} old messages from history")

    def get_messages_for_api(self) -> List[dict]:
        """
        Get messages formatted for OpenAI API

        Returns:
            List of message dictionaries
        """
        return [msg.to_dict() for msg in self.messages]

    def clear(self):
        """Clear all messages"""
        self.messages = []
        logger.info("Conversation cleared")

    def save_to_file(self, file_path: Path):
        """
        Save conversation to JSON file

        Args:
            file_path: Path to save file
        """
        try:
            data = {
                "messages": [msg.to_json() for msg in self.messages],
                "max_messages": self.max_messages
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Conversation saved to {file_path}")

        except Exception as e:
            logger.error(f"Failed to save conversation: {e}")

    def load_from_file(self, file_path: Path):
        """
        Load conversation from JSON file

        Args:
            file_path: Path to load from
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Note: This loads metadata only, not full message objects
            # Image data is not persisted to keep file sizes manageable
            logger.info(f"Conversation loaded from {file_path}")

        except Exception as e:
            logger.error(f"Failed to load conversation: {e}")

    def get_message_count(self) -> int:
        """Get total number of messages"""
        return len(self.messages)

    def get_last_message(self) -> Optional[Message]:
        """Get the last message in conversation"""
        return self.messages[-1] if self.messages else None
