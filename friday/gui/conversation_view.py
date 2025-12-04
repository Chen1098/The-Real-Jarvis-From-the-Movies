"""
Conversation view component for displaying chat history
"""
import customtkinter as ctk
from datetime import datetime


class ConversationView(ctk.CTkScrollableFrame):
    """Scrollable conversation display widget"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self.configure(fg_color="transparent")
        self.messages = []

    def add_message(self, role, content, has_image=False):
        """
        Add a message to the conversation view

        Args:
            role: 'user' or 'assistant'
            content: Message text
            has_image: Whether this message includes a screenshot
        """
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Message container
        msg_frame = ctk.CTkFrame(self, fg_color="transparent")
        msg_frame.pack(fill="x", padx=10, pady=5)

        # Determine styling based on role
        if role == "user":
            anchor = "e"
            bg_color = "#2B4B8C"  # Blue for user
            text_color = "white"
            prefix = "You"
        else:
            anchor = "w"
            bg_color = "#2D5F3F"  # Green for assistant
            text_color = "white"
            prefix = "Friday"

        # Message bubble
        bubble = ctk.CTkFrame(msg_frame, fg_color=bg_color, corner_radius=10)
        bubble.pack(anchor=anchor, padx=5)

        # Header with name and timestamp
        header = ctk.CTkLabel(
            bubble,
            text=f"{prefix} • {timestamp}",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=text_color
        )
        header.pack(anchor="w", padx=10, pady=(8, 2))

        # Image indicator if present
        if has_image:
            img_label = ctk.CTkLabel(
                bubble,
                text="📸 Screenshot attached",
                font=ctk.CTkFont(size=10),
                text_color="#FFD700"
            )
            img_label.pack(anchor="w", padx=10, pady=(0, 5))

        # Message content
        content_label = ctk.CTkLabel(
            bubble,
            text=content,
            font=ctk.CTkFont(size=13),
            text_color=text_color,
            wraplength=400,
            justify="left"
        )
        content_label.pack(anchor="w", padx=10, pady=(0, 8))

        # Store message
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": timestamp,
            "has_image": has_image
        })

        # Auto-scroll to bottom
        self.after(100, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        """Scroll to the bottom of the conversation"""
        self._parent_canvas.yview_moveto(1.0)

    def clear_conversation(self):
        """Clear all messages from the view"""
        for widget in self.winfo_children():
            widget.destroy()
        self.messages = []

    def get_messages(self):
        """Get all messages"""
        return self.messages
