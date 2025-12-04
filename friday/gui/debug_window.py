"""
Debug Window for WhatsApp Message Monitoring
"""
import customtkinter as ctk
from datetime import datetime
from typing import List


class DebugWindow(ctk.CTkToplevel):
    """Debug window to show WhatsApp monitoring activity"""

    def __init__(self, parent):
        super().__init__(parent)

        self.title("WhatsApp Debug Monitor")
        self.geometry("600x400")

        # Make it stay on top
        self.attributes('-topmost', True)

        # Create scrollable text area
        self.text_area = ctk.CTkTextbox(
            self,
            width=580,
            height=350,
            font=("Consolas", 10)
        )
        self.text_area.pack(padx=10, pady=(10, 5), fill="both", expand=True)

        # Clear button
        self.clear_btn = ctk.CTkButton(
            self,
            text="Clear Log",
            command=self.clear_log,
            width=100
        )
        self.clear_btn.pack(pady=5)

        # Initialize log
        self.log_message("Debug window initialized", "INFO")

    def log_message(self, message: str, level: str = "INFO"):
        """Add a log message to the debug window"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Color coding
        if level == "ERROR":
            color = "#ff4444"
        elif level == "WARNING":
            color = "#ffaa00"
        elif level == "SUCCESS":
            color = "#44ff44"
        elif level == "DEBUG":
            color = "#888888"
        else:
            color = "#ffffff"

        log_entry = f"[{timestamp}] [{level}] {message}\n"

        # Insert at the end
        self.text_area.insert("end", log_entry)
        self.text_area.see("end")  # Auto-scroll to bottom

    def clear_log(self):
        """Clear all log messages"""
        self.text_area.delete("1.0", "end")
        self.log_message("Log cleared", "INFO")

    def log_check_start(self, check_number: int):
        """Log start of message check"""
        self.log_message(f"=== Check #{check_number} ===", "DEBUG")

    def log_unread_found(self, count: int):
        """Log unread indicators found"""
        if count > 0:
            self.log_message(f"Found {count} unread chat(s)", "SUCCESS")
        else:
            self.log_message("No unread chats", "DEBUG")

    def log_chat_opened(self, chat_name: str):
        """Log chat being opened"""
        self.log_message(f"Opening chat: {chat_name}", "INFO")

    def log_message_received(self, sender: str, content: str):
        """Log new message received"""
        preview = content[:50] + "..." if len(content) > 50 else content
        self.log_message(f"NEW MESSAGE from {sender}: {preview}", "SUCCESS")

    def log_error(self, error_msg: str):
        """Log error"""
        self.log_message(error_msg, "ERROR")

    def log_notification_sent(self, recipient: str):
        """Log notification sent to user"""
        self.log_message(f"Notification sent to Friday for: {recipient}", "SUCCESS")
