"""
Main application window for Jarvis AI Assistant
"""
import customtkinter as ctk
import queue
from friday.config import Config
from friday.utils.logger import get_logger
from friday.gui.conversation_view import ConversationView
from friday.gui.debug_window import DebugWindow

logger = get_logger("gui")


class MainWindow:
    """Main application window"""

    def __init__(self, app):
        self.app = app
        self.event_queue = queue.Queue()
        self.screenshot_attached = False
        self.current_screenshot = None
        self.debug_window = None  # Debug window for WhatsApp monitoring

        # Set appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Create window
        self.root = ctk.CTk()
        self.root.title("Jarvis AI Assistant")

        # Get window dimensions from config
        width = Config.get("gui", "window_width", default=800)
        height = Config.get("gui", "window_height", default=600)

        # Center window on screen
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2

        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(600, 400)

        # Setup UI
        self._create_widgets()

        # Start event polling
        self.root.after(100, self._check_events)

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        logger.info("Main window initialized")

    def _create_widgets(self):
        """Create all UI widgets"""

        # Main container
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Top bar with status and controls
        self._create_top_bar()

        # Conversation view (scrollable)
        self.conversation_view = ConversationView(
            self.main_frame,
            width=760,
            height=400
        )
        self.conversation_view.pack(fill="both", expand=True, padx=10, pady=(10, 5))

        # Bottom bar with input and controls
        self._create_bottom_bar()

    def _create_top_bar(self):
        """Create top bar with status indicator"""
        top_bar = ctk.CTkFrame(self.main_frame, height=50, fg_color="transparent")
        top_bar.pack(fill="x", padx=10, pady=(10, 0))
        top_bar.pack_propagate(False)

        # Status indicator
        status_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        status_frame.pack(side="left")

        self.status_indicator = ctk.CTkLabel(
            status_frame,
            text="●",
            font=ctk.CTkFont(size=20),
            text_color="#666666"
        )
        self.status_indicator.pack(side="left", padx=(0, 5))

        self.status_label = ctk.CTkLabel(
            status_frame,
            text="Idle",
            font=ctk.CTkFont(size=14)
        )
        self.status_label.pack(side="left")

        # WhatsApp toggle button
        self.whatsapp_btn = ctk.CTkButton(
            top_bar,
            text="📱 Enable WhatsApp",
            width=150,
            command=self._toggle_whatsapp,
            fg_color="#25D366"
        )
        self.whatsapp_btn.pack(side="right", padx=5)

        # Debug window button (initially hidden, shown when WhatsApp active)
        self.debug_btn = ctk.CTkButton(
            top_bar,
            text="🔍 Debug",
            width=100,
            command=self._toggle_debug_window,
            fg_color="#555555"
        )
        # Don't pack it yet, will show when WhatsApp is enabled

        # Settings button
        self.settings_btn = ctk.CTkButton(
            top_bar,
            text="⚙ Settings",
            width=100,
            command=self._open_settings
        )
        self.settings_btn.pack(side="right", padx=5)

        # Clear conversation button
        self.clear_btn = ctk.CTkButton(
            top_bar,
            text="🗑 Clear",
            width=100,
            command=self._clear_conversation
        )
        self.clear_btn.pack(side="right")

    def _create_bottom_bar(self):
        """Create bottom bar with input and controls"""
        bottom_bar = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        bottom_bar.pack(fill="x", padx=10, pady=10)

        # Screenshot controls frame
        screenshot_frame = ctk.CTkFrame(bottom_bar, height=40, fg_color="transparent")
        screenshot_frame.pack(fill="x", pady=(0, 5))

        self.screenshot_btn = ctk.CTkButton(
            screenshot_frame,
            text="📸 Capture Screenshot",
            width=180,
            command=self._capture_screenshot
        )
        self.screenshot_btn.pack(side="left", padx=(0, 5))

        self.attach_btn = ctk.CTkButton(
            screenshot_frame,
            text="📎 Attach to Next Message",
            width=180,
            command=self._toggle_attach_screenshot,
            state="disabled"
        )
        self.attach_btn.pack(side="left", padx=(0, 5))

        self.screenshot_status = ctk.CTkLabel(
            screenshot_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#888888"
        )
        self.screenshot_status.pack(side="left", padx=10)

        # Text input frame
        input_frame = ctk.CTkFrame(bottom_bar, height=60, fg_color="transparent")
        input_frame.pack(fill="x")

        # Text entry
        self.text_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Type a message or say 'Jarvis' to use voice...",
            height=40,
            font=ctk.CTkFont(size=13)
        )
        self.text_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.text_entry.bind("<Return>", self._on_send_text)

        # Send button
        self.send_btn = ctk.CTkButton(
            input_frame,
            text="Send",
            width=100,
            height=40,
            command=self._send_text_message
        )
        self.send_btn.pack(side="left")

        # Record button (for manual testing)
        self.record_btn = ctk.CTkButton(
            input_frame,
            text="🎤 Record",
            width=100,
            height=40,
            command=self._toggle_manual_record,
            fg_color="#8B0000"
        )
        self.record_btn.pack(side="left", padx=(5, 0))

    def _capture_screenshot(self):
        """Handle screenshot capture button"""
        logger.info("Screenshot button clicked")
        # Publish event for screenshot capture
        self.publish_event("screenshot_capture", {})

    def _toggle_attach_screenshot(self):
        """Toggle screenshot attachment"""
        self.screenshot_attached = not self.screenshot_attached

        if self.screenshot_attached:
            self.attach_btn.configure(fg_color="#2D5F3F", text="✓ Attached")
            self.screenshot_status.configure(text="Screenshot will be included in next message", text_color="#4CAF50")
        else:
            self.attach_btn.configure(fg_color="#1f538d", text="📎 Attach to Next Message")
            self.screenshot_status.configure(text="Screenshot captured", text_color="#888888")

    def _send_text_message(self):
        """Send text message from entry field"""
        text = self.text_entry.get().strip()
        if not text:
            return

        # Add user message to conversation
        self.conversation_view.add_message("user", text, has_image=self.screenshot_attached)

        # Clear entry
        self.text_entry.delete(0, "end")

        # Publish event with text and screenshot
        self.publish_event("user_message", {
            "text": text,
            "has_screenshot": self.screenshot_attached,
            "screenshot": self.current_screenshot if self.screenshot_attached else None
        })

        # Clear screenshot after sending
        if self.screenshot_attached:
            self._clear_screenshot()

    def _on_send_text(self, event):
        """Handle Enter key in text entry"""
        self._send_text_message()

    def _toggle_manual_record(self):
        """Handle manual record button"""
        logger.info("Manual record button clicked")
        self.publish_event("manual_record", {})

    def _clear_conversation(self):
        """Clear conversation history"""
        self.conversation_view.clear_conversation()
        self.publish_event("clear_conversation", {})
        logger.info("Conversation cleared")

    def _toggle_whatsapp(self):
        """Toggle WhatsApp integration"""
        logger.info("WhatsApp toggle clicked")
        self.publish_event("whatsapp_toggle", {})

    def _open_settings(self):
        """Open settings dialog"""
        logger.info("Settings button clicked")
        # TODO: Implement settings dialog
        self.show_info("Settings", "Settings dialog not yet implemented")

    def _on_closing(self):
        """Handle window close event"""
        logger.info("Window closing")
        self.publish_event("shutdown", {})
        self.root.destroy()

    def _clear_screenshot(self):
        """Clear current screenshot"""
        self.screenshot_attached = False
        self.current_screenshot = None
        self.attach_btn.configure(state="disabled", text="📎 Attach to Next Message", fg_color="#1f538d")
        self.screenshot_status.configure(text="")

    def update_status(self, status, color=None):
        """
        Update status indicator

        Args:
            status: Status text ('Idle', 'Listening', 'Processing', 'Speaking')
            color: Color for indicator dot (optional, auto-determined if None)
        """
        self.status_label.configure(text=status)

        # Status color mapping
        status_colors = {
            "Idle": "#666666",
            "Listening": "#FF6B6B",
            "Processing": "#FFA500",
            "Speaking": "#4CAF50"
        }

        # Use provided color or auto-determine from status
        if color is None:
            color = status_colors.get(status, "#666666")

        self.status_indicator.configure(text_color=color)

    def on_screenshot_captured(self, screenshot_image):
        """Handle screenshot captured event"""
        self.current_screenshot = screenshot_image
        self.attach_btn.configure(state="normal")
        self.screenshot_status.configure(
            text="Screenshot captured! Click 'Attach' to include in next message",
            text_color="#4CAF50"
        )
        logger.info("Screenshot captured and ready to attach")

    def show_info(self, title, message):
        """Show info dialog"""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title(title)
        dialog.geometry("400x150")

        label = ctk.CTkLabel(dialog, text=message, wraplength=350)
        label.pack(padx=20, pady=20)

        btn = ctk.CTkButton(dialog, text="OK", command=dialog.destroy)
        btn.pack(pady=10)

        dialog.transient(self.root)
        dialog.grab_set()

    def publish_event(self, event_type, data):
        """Publish event to application"""
        if hasattr(self.app, 'handle_gui_event'):
            self.app.handle_gui_event(event_type, data)

    def _check_events(self):
        """Poll event queue for updates from other threads"""
        try:
            while True:
                event = self.event_queue.get_nowait()
                self._handle_event(event)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._check_events)

    def _handle_event(self, event):
        """Handle events from other threads"""
        event_type = event.get("type")
        data = event.get("data", {})

        if event_type == "status_update":
            self.update_status(data.get("status"), data.get("color"))

        elif event_type == "ai_response":
            self.conversation_view.add_message("assistant", data.get("text", ""))

        elif event_type == "screenshot_captured":
            self.on_screenshot_captured(data.get("image"))

        elif event_type == "whatsapp_status":
            self._update_whatsapp_button(data.get("enabled", False))

        elif event_type == "error":
            self.show_info("Error", data.get("message", "Unknown error"))

    def _update_whatsapp_button(self, enabled: bool):
        """Update WhatsApp button based on connection status"""
        if enabled:
            self.whatsapp_btn.configure(
                text="📱 WhatsApp Active",
                fg_color="#128C7E"  # Darker green when active
            )
            # Show debug button when WhatsApp is active
            self.debug_btn.pack(side="right", padx=5, before=self.whatsapp_btn)
        else:
            self.whatsapp_btn.configure(
                text="📱 Enable WhatsApp",
                fg_color="#25D366"  # WhatsApp green
            )
            # Hide debug button when WhatsApp is inactive
            self.debug_btn.pack_forget()

    def _toggle_debug_window(self):
        """Toggle debug window visibility"""
        if self.debug_window is None or not self.debug_window.winfo_exists():
            # Create new debug window
            self.debug_window = DebugWindow(self.root)
            logger.info("Debug window opened")
        else:
            # Close existing window
            self.debug_window.destroy()
            self.debug_window = None
            logger.info("Debug window closed")

    def log_debug(self, message: str, level: str = "INFO"):
        """Send log message to debug window if open"""
        if self.debug_window and self.debug_window.winfo_exists():
            self.debug_window.log_message(message, level)

    def add_event(self, event_type, data):
        """Add event to queue (called from other threads)"""
        self.event_queue.put({"type": event_type, "data": data})

    def run(self):
        """Start the GUI main loop"""
        logger.info("Starting GUI main loop")
        self.root.mainloop()
