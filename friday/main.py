"""
Jarvis AI Assistant - Main Application
"""
import threading
from pathlib import Path
from datetime import datetime
from friday.utils.logger import get_logger
from friday.config import Config
from friday.gui.main_window import MainWindow
from friday.models.conversation import Conversation
from friday.ai.openai_client import OpenAIClient
from friday.ai.text_to_speech import TextToSpeech
from friday.ai.speech_to_text import SpeechToText
from friday.ai.vision_handler import encode_image_for_gpt4o
from friday.audio.audio_recorder import AudioRecorder
from friday.audio.wake_word_detector import WakeWordDetector
from friday.utils.screenshot import capture_screenshot
from friday.integrations.whatsapp_webjs_service import WhatsAppWebJSService
from friday.integrations.whatsapp_models import WhatsAppNotification
from friday.integrations.google_calendar import GoogleCalendarService
from friday.integrations.system_control import SystemControl
from friday.integrations.web_search import WebSearchService

logger = get_logger("main")


class FridayApp:
    """Main application class"""

    def __init__(self):
        logger.info("Initializing Jarvis AI Assistant")

        # Load system prompt from prompt.txt
        prompt_path = Path(__file__).parent.parent / "prompt.txt"
        if prompt_path.exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.system_prompt = f.read()
            logger.info("System prompt loaded from prompt.txt")
        else:
            logger.error("prompt.txt not found! Using default prompt")
            self.system_prompt = "You are Jarvis, a sophisticated AI assistant. Be concise and helpful."

        # Create GUI
        self.window = MainWindow(self)

        # Initialize AI components
        self.conversation = Conversation(max_messages=100)
        self.openai_client = OpenAIClient()
        self.tts = TextToSpeech()
        self.stt = SpeechToText()

        # Initialize audio components
        self.audio_recorder = AudioRecorder()
        self.wake_word_detector = WakeWordDetector(callback=self._on_wake_word_detected)

        # Initialize WhatsApp integration
        self.whatsapp = WhatsAppWebJSService()
        self.whatsapp.register_notification_callback(self._on_whatsapp_notification)
        self.whatsapp_enabled = False
        self.last_whatsapp_contact = None  # Track last contact for quick reply
        self.waiting_for_whatsapp_reply = False  # Track if waiting for user's WhatsApp reply
        self.pending_whatsapp_message = None  # Store the message we're waiting to reply to

        # Initialize new Jarvis services
        self.calendar = GoogleCalendarService()
        self.system_control = SystemControl()
        self.web_search = WebSearchService()

        # WhatsApp conversation memory - store history per contact
        self.whatsapp_conversations = {}  # {contact_name: [messages]}
        self.max_history_per_contact = 50  # Keep last 50 messages per contact

        # User context - remember what user tells Jarvis (for WhatsApp context)
        self.user_context = []  # Store recent things user said to Jarvis
        self.max_user_context = 30  # Keep last 30 user statements

        # State
        self.is_recording = False
        self.is_processing = False

        logger.info("Jarvis AI Assistant initialized")

    def handle_gui_event(self, event_type, data):
        """
        Handle events from GUI

        Args:
            event_type: Type of event
            data: Event data
        """
        logger.debug(f"GUI event: {event_type}")

        if event_type == "screenshot_capture":
            self._handle_screenshot_capture()

        elif event_type == "user_message":
            self._handle_user_message(data)

        elif event_type == "manual_record":
            self._handle_manual_record()

        elif event_type == "clear_conversation":
            self._handle_clear_conversation()

        elif event_type == "whatsapp_toggle":
            self._handle_whatsapp_toggle()

        elif event_type == "whatsapp_send":
            self._handle_whatsapp_send(data)

        elif event_type == "whatsapp_search":
            self._handle_whatsapp_search(data)

        elif event_type == "shutdown":
            self._handle_shutdown()

    def _handle_screenshot_capture(self):
        """Handle screenshot capture request"""
        try:
            logger.info("Capturing screenshot...")
            screenshot = capture_screenshot()
            self.window.add_event("screenshot_captured", {"image": screenshot})

        except Exception as e:
            logger.error(f"Screenshot capture failed: {e}")
            self.window.add_event("error", {"message": f"Screenshot failed: {e}"})

    def _handle_user_message(self, data):
        """Handle user text message"""
        text = data.get("text", "")
        has_screenshot = data.get("has_screenshot", False)
        screenshot = data.get("screenshot")

        logger.info(f"User message: {text} (screenshot: {has_screenshot})")

        # Process in separate thread to avoid blocking GUI
        thread = threading.Thread(
            target=self._process_user_message,
            args=(text, screenshot),
            daemon=True
        )
        thread.start()

    def _process_user_message(self, text, screenshot=None):
        """Process user message with AI"""
        try:
            self.window.add_event("status_update", {"status": "Processing"})
            self.is_processing = True

            # Pattern: "Tell [name] ..." - always route to WhatsApp
            # BUT exclude common question patterns like "tell me about", "tell me what", etc.
            import re

            # Excluded words that indicate it's a question to Jarvis, not a WhatsApp send
            excluded_tell_words = ["me", "us", "everyone", "somebody", "someone", "about", "what", "how", "why", "when", "where"]

            tell_pattern = r"^tell\s+([^,]+?)\s+(.+)$"
            tell_match = re.search(tell_pattern, text.lower())

            if tell_match and self.whatsapp_enabled:
                potential_contact = tell_match.group(1).strip()

                # Only treat as WhatsApp command if it's NOT an excluded word
                if potential_contact not in excluded_tell_words:
                    message_text = text[text.lower().find(tell_match.group(2)):].strip()  # Preserve original case

                    logger.info(f"'Tell' pattern detected: {potential_contact} -> {message_text}")

                    # Set up pending message context for rewriting
                    self.pending_whatsapp_message = {
                        'contact': potential_contact,
                        'sender': potential_contact,
                        'original_message': f"(Direct message via 'Tell' command)"
                    }

                    self._rewrite_and_send_whatsapp_reply(message_text)
                    self.is_processing = False
                    self.window.add_event("status_update", {"status": "Idle"})
                    return

            # Check if we're waiting for a WhatsApp reply (Jarvis explicitly asked)
            if self.waiting_for_whatsapp_reply and self.pending_whatsapp_message:
                logger.info(f"User responding to WhatsApp message. Rewriting: '{text}'")
                self._rewrite_and_send_whatsapp_reply(text)
                self.is_processing = False
                self.window.add_event("status_update", {"status": "Idle"})
                return

            # Check for system control commands
            system_handled = self._handle_system_control_intent(text)
            if system_handled:
                self.is_processing = False
                self.window.add_event("status_update", {"status": "Idle"})
                return

            # Check for basic time/date queries (don't need internet)
            datetime_handled = self._handle_datetime_query(text)
            if datetime_handled:
                self.is_processing = False
                self.window.add_event("status_update", {"status": "Idle"})
                return

            # Check for calendar commands
            calendar_handled = self._handle_calendar_intent(text)
            if calendar_handled:
                self.is_processing = False
                self.window.add_event("status_update", {"status": "Idle"})
                return

            # Check for web search commands
            search_handled = self._handle_search_intent(text)
            if search_handled:
                self.is_processing = False
                self.window.add_event("status_update", {"status": "Idle"})
                return

            # Check for WhatsApp commands first
            if self.whatsapp_enabled:
                whatsapp_handled = self._handle_whatsapp_intent(text)
                if whatsapp_handled:
                    self.is_processing = False
                    return

            # Store user's message in context (for WhatsApp decisions)
            self._add_user_context(text)

            # Encode screenshot if provided
            image_data = None
            if screenshot:
                image_data = encode_image_for_gpt4o(screenshot)

            # Add environmental context (calendar, time, etc.)
            env_context = self._get_environmental_context()

            # Add to conversation with WhatsApp context if enabled
            context_text = text
            if self.whatsapp_enabled:
                # Add WhatsApp context to system
                context_text = (
                    f"{env_context}\n\n"
                    f"{text}\n\n"
                    f"[WhatsApp active. ONLY use 'SEND_WHATSAPP:[name]:[message]' if the user explicitly tells you to CORRECT a previous WhatsApp message. "
                    f"Example: User says 'Actually I'm not available, tell Chen I can't make it' → SEND_WHATSAPP:Chen:Can't make it, sorry. "
                    f"For general questions like 'tell me about X' or 'update me on X', just answer normally - don't send WhatsApp.]"
                )
            else:
                context_text = f"{env_context}\n\n{text}"

            self.conversation.add_user_message(context_text, image_data)

            # Get AI response with system prompt
            messages = self.conversation.get_messages_for_api()

            # Inject system prompt at the beginning
            messages_with_prompt = [
                {"role": "system", "content": self.system_prompt}
            ] + messages

            response_text = self.openai_client.chat_completion(messages_with_prompt)

            # Add to conversation
            self.conversation.add_assistant_message(response_text)

            # Check if AI wants to send a WhatsApp message
            cleaned_response = response_text
            if "SEND_WHATSAPP:" in response_text and self.whatsapp_enabled:
                cleaned_response = self._handle_ai_whatsapp_send(response_text)

            # Update GUI with response (use cleaned version without SEND_WHATSAPP commands)
            self.window.add_event("ai_response", {"text": cleaned_response})

            # Speak response
            self.window.add_event("status_update", {"status": "Speaking"})
            self.tts.speak(cleaned_response, play_audio=True)

            self.window.add_event("status_update", {"status": "Idle"})

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            self.window.add_event("error", {"message": f"Processing error: {e}"})
            self.window.add_event("status_update", {"status": "Idle"})

        finally:
            self.is_processing = False

    def _handle_whatsapp_intent(self, text: str) -> bool:
        """
        Check if message is a WhatsApp command and handle it

        Returns:
            True if WhatsApp command was handled, False otherwise
        """
        import re

        text_lower = text.lower()

        # Pattern: Quick reply to last contact (short messages without "send" or "whatsapp")
        # If user just says something brief after a notification, treat it as a reply
        if self.last_whatsapp_contact and len(text.split()) <= 15:
            # Check if it's NOT explicitly a different command
            if not any(keyword in text_lower for keyword in ['send', 'what did', 'show messages', 'search', 'check']):
                logger.info(f"Quick reply detected for {self.last_whatsapp_contact}: {text}")

                # Format message with assistant prefix
                formatted_message = f"I am the assistant Jarvis, {text}"

                self._handle_whatsapp_send({
                    "contact": self.last_whatsapp_contact,
                    "message": formatted_message
                })

                # Clear last contact after reply
                self.last_whatsapp_contact = None
                return True

        # Pattern: "send [a] whatsapp [message] to [name]: [message]"
        # or "send to [name] on whatsapp: [message]"
        send_patterns = [
            r"send\s+(?:a\s+)?(?:whatsapp\s+)?(?:message\s+)?to\s+([^:]+):?\s*(.+)",
            r"whatsapp\s+([^:]+):?\s*(.+)",
            r"message\s+([^:]+)\s+on\s+whatsapp:?\s*(.+)"
        ]

        for pattern in send_patterns:
            match = re.search(pattern, text_lower)
            if match:
                contact = match.group(1).strip()
                message = match.group(2).strip()

                # Extract actual message from original text (preserve case)
                # Find where the message starts in original text
                message_start = text.lower().find(message.lower())
                if message_start >= 0:
                    message = text[message_start:].strip()

                logger.info(f"WhatsApp send intent detected: {contact} -> {message}")
                self._handle_whatsapp_send({"contact": contact, "message": message})
                return True

        # Pattern: "what did [name] say"
        search_patterns = [
            r"what\s+did\s+([^\s?]+)\s+say",
            r"show\s+messages?\s+from\s+([^\s?]+)",
            r"check\s+([^\s']+)'?s?\s+messages?",
            r"read\s+messages?\s+from\s+([^\s?]+)"
        ]

        for pattern in search_patterns:
            match = re.search(pattern, text_lower)
            if match:
                contact = match.group(1).strip()
                logger.info(f"WhatsApp search intent detected: {contact}")
                self._handle_whatsapp_search({"query": contact, "chat_name": contact})
                return True

        # Pattern: "search whatsapp for [query]"
        if "search" in text_lower and "whatsapp" in text_lower:
            match = re.search(r"search\s+(?:whatsapp\s+)?(?:for\s+)?(.+)", text_lower)
            if match:
                query = match.group(1).strip()
                logger.info(f"WhatsApp search intent detected: {query}")
                self._handle_whatsapp_search({"query": query})
                return True

        return False

    def _handle_ai_whatsapp_send(self, response_text: str) -> str:
        """
        Parse and send WhatsApp message from AI's response

        Format: SEND_WHATSAPP:[contact]:[message]
        Example: SEND_WHATSAPP:chen:Sorry, can't make it - meeting came up

        Returns:
            str: Cleaned response text without SEND_WHATSAPP commands
        """
        import re
        try:
            # Extract SEND_WHATSAPP command
            pattern = r"SEND_WHATSAPP:\s*([^:]+):\s*(.+?)(?:\n|$)"
            match = re.search(pattern, response_text)

            if match:
                contact = match.group(1).strip()
                message = match.group(2).strip()

                logger.info(f"AI requested WhatsApp send to {contact}: {message}")

                # Send the message
                self._handle_whatsapp_send({
                    "contact": contact,
                    "message": message
                })

            # Clean up the response text to remove the command
            clean_response = re.sub(pattern, "", response_text).strip()

            # Update conversation with cleaned response
            if self.conversation.messages and clean_response:
                self.conversation.messages[-1].content = clean_response

            return clean_response if clean_response else response_text

        except Exception as e:
            logger.error(f"Error handling AI WhatsApp send: {e}", exc_info=True)
            return response_text

    def _handle_manual_record(self):
        """Handle manual voice recording"""
        if self.is_recording:
            logger.warning("Already recording")
            return

        # Record in separate thread
        thread = threading.Thread(
            target=self._record_and_process,
            daemon=True
        )
        thread.start()

    def _record_and_process(self):
        """Record audio and process with AI"""
        try:
            self.is_recording = True
            self.window.add_event("status_update", {"status": "Listening"})

            # Record with silence detection
            audio_data = self.audio_recorder.record_with_silence_detection()

            # Convert to bytes
            audio_bytes = self.audio_recorder.recording_to_bytes(audio_data)

            # Transcribe
            self.window.add_event("status_update", {"status": "Processing"})
            text = self.stt.transcribe_bytes(audio_bytes)

            # Add to GUI as user message
            self.window.conversation_view.add_message("user", text, has_image=False)

            # Process with AI
            self._process_user_message(text, screenshot=None)

        except Exception as e:
            logger.error(f"Recording/processing error: {e}")
            self.window.add_event("error", {"message": f"Voice error: {e}"})
            self.window.add_event("status_update", {"status": "Idle"})

        finally:
            self.is_recording = False

    def _on_wake_word_detected(self):
        """Callback when wake word is detected"""
        logger.info("Wake word detected - starting recording")

        # Run in separate thread to avoid blocking wake word detector
        thread = threading.Thread(
            target=self._handle_wake_word_activation,
            daemon=True
        )
        thread.start()

    def _handle_wake_word_activation(self):
        """Handle wake word activation in separate thread"""
        try:
            # Stop wake word detection temporarily
            self.wake_word_detector.stop()

            # Record and process
            self._record_and_process()

        finally:
            # Always restart wake word detection
            try:
                self.wake_word_detector.start()
                logger.info("Wake word detection restarted")
            except Exception as e:
                logger.error(f"Failed to restart wake word detection: {e}")

    def _handle_clear_conversation(self):
        """Handle conversation clear"""
        self.conversation.clear()
        logger.info("Conversation cleared")

    def _handle_whatsapp_toggle(self):
        """Handle WhatsApp enable/disable toggle"""
        if not self.whatsapp_enabled:
            # Start WhatsApp
            logger.info("Starting WhatsApp integration...")
            self.window.conversation_view.add_message(
                "assistant",
                "Starting WhatsApp integration... This may take a moment."
            )

            # Start in separate thread
            thread = threading.Thread(target=self._start_whatsapp, daemon=True)
            thread.start()
        else:
            # Stop WhatsApp
            logger.info("Stopping WhatsApp integration...")
            self.whatsapp.stop()
            self.whatsapp_enabled = False
            self.window.add_event("whatsapp_status", {"enabled": False})
            self.window.conversation_view.add_message(
                "assistant",
                "WhatsApp integration stopped."
            )

    def _start_whatsapp(self):
        """Start WhatsApp service in background thread"""
        try:
            # Set GUI window reference for debug logging
            self.whatsapp.set_gui_window(self.window)

            success = self.whatsapp.start()

            if success:
                self.whatsapp_enabled = True
                self.window.add_event("whatsapp_status", {"enabled": True})
                self.window.conversation_view.add_message(
                    "assistant",
                    "✅ WhatsApp integration is now active!\n\n"
                    "I can now:\n"
                    "• Monitor incoming WhatsApp messages\n"
                    "• Notify you of new messages\n"
                    "• Send messages when you ask me to\n"
                    "• Search your chat history\n\n"
                    "Try saying: 'Send a WhatsApp message to [name]' or 'What did [name] say?'\n\n"
                    "💡 Click the '🔍 Debug' button to see real-time monitoring activity!"
                )

                # Start monitoring for messages
                thread = threading.Thread(target=self._monitor_whatsapp_messages, daemon=True)
                thread.start()
            else:
                self.window.conversation_view.add_message(
                    "assistant",
                    "❌ Failed to start WhatsApp integration. Please check the logs."
                )

        except Exception as e:
            logger.error(f"Error starting WhatsApp: {e}")
            self.window.conversation_view.add_message(
                "assistant",
                f"❌ WhatsApp integration error: {e}"
            )

    def _monitor_whatsapp_messages(self):
        """Monitor for new WhatsApp messages - No longer needed with whatsapp-web.js event-driven approach"""
        # This method is kept for compatibility but does nothing
        # Messages now come through _on_whatsapp_notification callback
        logger.info("WhatsApp message monitoring (callback-based, no polling needed)")

    def _on_whatsapp_notification(self, notification: WhatsAppNotification):
        """Callback when new WhatsApp message arrives - uses AI to decide how to respond"""
        logger.info(f"WhatsApp notification: {notification}")

        # Store incoming message in conversation history
        self._add_to_conversation_history(
            notification.chat_name,
            f"{notification.sender_name}: {notification.message_preview}",
            is_from_user=False
        )

        # Process in background thread to avoid blocking
        thread = threading.Thread(
            target=self._process_whatsapp_with_ai,
            args=(notification,),
            daemon=True
        )
        thread.start()

    def _add_to_conversation_history(self, contact_name: str, message: str, is_from_user: bool):
        """Add a message to conversation history for a contact"""
        if contact_name not in self.whatsapp_conversations:
            self.whatsapp_conversations[contact_name] = []

        # Add message with direction indicator
        direction = "THEM" if not is_from_user else "YOU"
        self.whatsapp_conversations[contact_name].append(f"[{direction}] {message}")

        # Keep only last N messages
        if len(self.whatsapp_conversations[contact_name]) > self.max_history_per_contact:
            self.whatsapp_conversations[contact_name] = self.whatsapp_conversations[contact_name][-self.max_history_per_contact:]

        logger.debug(f"Conversation history for {contact_name}: {len(self.whatsapp_conversations[contact_name])} messages")

    def _get_conversation_history_text(self, contact_name: str) -> str:
        """Get formatted conversation history for a contact"""
        if contact_name not in self.whatsapp_conversations or not self.whatsapp_conversations[contact_name]:
            return "No previous conversation history with this contact."

        history = "\n".join(self.whatsapp_conversations[contact_name])
        return f"RECENT CONVERSATION HISTORY:\n{history}"

    def _add_user_context(self, text: str):
        """Store user's message as context for WhatsApp decisions"""
        import time
        self.user_context.append({
            'text': text,
            'timestamp': time.time()
        })

        # Keep only last N contexts
        if len(self.user_context) > self.max_user_context:
            self.user_context = self.user_context[-self.max_user_context:]

        logger.debug(f"Stored user context: '{text[:50]}...' ({len(self.user_context)} total)")

    def _get_user_context_text(self) -> str:
        """Get formatted user context for WhatsApp AI"""
        if not self.user_context:
            return "No recent user context."

        # Filter to last 5 minutes
        import time
        recent = [ctx for ctx in self.user_context if time.time() - ctx['timestamp'] < 300]

        if not recent:
            return "No recent user context."

        context_lines = [ctx['text'] for ctx in recent]
        return "WHAT USER TOLD FRIDAY RECENTLY:\n" + "\n".join(f"- {line}" for line in context_lines)

    def _process_whatsapp_with_ai(self, notification: WhatsAppNotification):
        """Process WhatsApp message with AI to decide whether to auto-reply"""
        try:
            # Load the AI prompt from prompt.txt
            prompt_path = Path(__file__).parent.parent / "prompt.txt"
            if not prompt_path.exists():
                logger.error("prompt.txt not found!")
                return

            with open(prompt_path, "r", encoding="utf-8") as f:
                system_prompt = f.read()

            # Get conversation history for this contact
            conversation_history = self._get_conversation_history_text(notification.chat_name)

            # Get user context (what user told Jarvis recently)
            user_context = self._get_user_context_text()

            # Get current time context
            now = datetime.now()
            time_context = f"Current time: {now.strftime('%I:%M %p')}, {now.strftime('%A, %B %d, %Y')}"

            # Build message for GPT-4o
            user_message = (
                f"{time_context}\n\n"
                f"{conversation_history}\n\n"
                f"{user_context}\n\n"
                f"--- NEW MESSAGE ---\n"
                f"From: {notification.sender_name}\n"
                f"Chat: {notification.chat_name}\n"
                f"Message: {notification.message_preview}\n\n"
                f"Based on your stored meeting memory, conversation history, and what the user told Jarvis above, decide whether to auto-reply or notify the user. "
                f"IMPORTANT: Check your meeting memory for conflicts! If user has a meeting at the requested time, decline politely. "
                f"Use the user's recent statements to Jarvis as valuable context (e.g., if user said they're busy, decline invitations). "
                f"Remember commitments and important details from previous messages."
            )

            # Prepare messages for API (text only, no image)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]

            # Call GPT-4o
            logger.info("Calling GPT-4o to analyze WhatsApp message...")
            response = self.openai_client.chat_completion(messages)

            logger.info(f"GPT-4o response:\n{response}")

            # Clean the response - remove markdown code fences and extra whitespace
            cleaned_response = response.strip()

            # Remove markdown code fences if present
            if cleaned_response.startswith('```'):
                # Remove opening ```
                cleaned_response = cleaned_response.split('\n', 1)[1] if '\n' in cleaned_response else cleaned_response

            if cleaned_response.endswith('```'):
                # Remove closing ```
                cleaned_response = cleaned_response.rsplit('\n', 1)[0] if '\n' in cleaned_response else cleaned_response

            # Parse the structured output - filter out empty lines
            lines = [line.strip() for line in cleaned_response.strip().split('\n') if line.strip()]

            logger.info(f"Parsed lines: {lines}")

            if len(lines) < 3:
                logger.error(f"Invalid GPT-4o response format. Expected at least 3 lines, got {len(lines)}")
                return

            speak_aloud = lines[0].strip().upper() == "YES"
            should_send = lines[1].strip().upper() == "YES"

            if should_send:
                # Auto-reply mode
                if len(lines) < 5:
                    logger.error(f"Invalid GPT-4o response for auto-reply. Expected 5 lines, got {len(lines)}")
                    return

                send_to = lines[2].strip()
                message_text = lines[3].strip()
                summary = lines[4].strip()

                logger.info(f"Auto-replying to {send_to}: {message_text}")

                # Send the message
                success = self.whatsapp.send_message(send_to, message_text)

                if success:
                    logger.info("✓ Auto-reply sent successfully")

                    # Store AI's reply in conversation history
                    self._add_to_conversation_history(
                        send_to,
                        f"You (via Jarvis): {message_text}",
                        is_from_user=True
                    )

                    # Update GUI
                    self.window.conversation_view.add_message(
                        "assistant",
                        f"📱 Auto-replied to {send_to}\n\n"
                        f"Message: \"{message_text}\"\n\n"
                        f"Context: {summary}"
                    )

                    # Speak if needed
                    if speak_aloud:
                        self.tts.speak(summary, play_audio=True)
                else:
                    logger.error("✗ Failed to send auto-reply")
            else:
                # Just notify the user - need their input
                summary = lines[2].strip() if len(lines) >= 3 else notification.message_preview

                logger.info(f"Not auto-replying. Summary: {summary}")

                # Set flag to wait for user's reply
                self.waiting_for_whatsapp_reply = True
                self.pending_whatsapp_message = {
                    'contact': notification.chat_name,
                    'sender': notification.sender_name,
                    'original_message': notification.message_preview
                }

                # Update GUI
                self.window.conversation_view.add_message(
                    "assistant",
                    f"📱 New WhatsApp message from {notification.sender_name}\n\n{summary}"
                )

                # Store last contact for potential quick reply
                self.last_whatsapp_contact = notification.chat_name

                # Speak the summary
                if speak_aloud:
                    self.tts.speak(summary, play_audio=True)

        except Exception as e:
            logger.error(f"Error processing WhatsApp with AI: {e}", exc_info=True)
            self.window.conversation_view.add_message(
                "assistant",
                f"📱 Received message from {notification.sender_name}\n"
                f"❌ Error processing with AI: {e}"
            )

    def _rewrite_and_send_whatsapp_reply(self, user_text: str):
        """Rewrite user's casual response into a proper WhatsApp message and send it"""
        try:
            # Get contact info from pending_whatsapp_message
            if not self.pending_whatsapp_message:
                logger.error("No WhatsApp context available for rewriting")
                return

            contact = self.pending_whatsapp_message['contact']
            sender = self.pending_whatsapp_message['sender']
            original_message = self.pending_whatsapp_message['original_message']

            logger.info(f"Rewriting reply to {sender}: '{user_text}'")

            # Get conversation history
            conversation_history = self._get_conversation_history_text(contact)

            # Create rewriting prompt
            rewrite_prompt = (
                f"You are Jarvis, a personal AI assistant helping to rewrite the user's casual response into a proper WhatsApp message.\n\n"
                f"{conversation_history}\n\n"
                f"--- LATEST MESSAGE FROM {sender} ---\n"
                f"{original_message}\n\n"
                f"--- USER'S CASUAL RESPONSE ---\n"
                f"\"{user_text}\"\n\n"
                f"TASK: Rewrite the user's casual response into a natural, friendly WhatsApp message. Keep it SHORT and conversational.\n"
                f"Output ONLY the rewritten message, nothing else. No explanations, no quotes, just the message text."
            )

            # Call GPT to rewrite
            messages = [{"role": "user", "content": rewrite_prompt}]
            rewritten_message = self.openai_client.chat_completion(messages)

            # Clean up the response
            rewritten_message = rewritten_message.strip().strip('"').strip("'")

            logger.info(f"Rewritten message: '{rewritten_message}'")

            # Send the rewritten message
            success = self.whatsapp.send_message(contact, rewritten_message)

            if success:
                logger.info("✓ Rewritten message sent successfully")

                # Store in conversation history
                self._add_to_conversation_history(
                    contact,
                    f"You (via Jarvis): {rewritten_message}",
                    is_from_user=True
                )

                # Update GUI
                detection_note = " (auto-detected)" if smart_detected else ""
                self.window.conversation_view.add_message(
                    "assistant",
                    f"📱 Sent to {sender}{detection_note}\n\n"
                    f"Your input: \"{user_text}\"\n"
                    f"Sent: \"{rewritten_message}\""
                )

                # Speak confirmation
                self.tts.speak(f"Sent message to {sender}", play_audio=True)
            else:
                logger.error("✗ Failed to send rewritten message")
                self.window.conversation_view.add_message(
                    "assistant",
                    f"❌ Failed to send message to {sender}"
                )

            # Clear waiting flags
            self.waiting_for_whatsapp_reply = False
            self.pending_whatsapp_message = None

        except Exception as e:
            logger.error(f"Error rewriting WhatsApp reply: {e}", exc_info=True)
            self.window.conversation_view.add_message(
                "assistant",
                f"❌ Error rewriting message: {e}"
            )
            # Clear flags even on error
            self.waiting_for_whatsapp_reply = False
            self.pending_whatsapp_message = None

    def _handle_whatsapp_send(self, data):
        """Handle sending a WhatsApp message"""
        contact = data.get("contact", "")
        message = data.get("message", "")

        if not contact or not message:
            logger.warning("WhatsApp send: missing contact or message")
            return

        logger.info(f"Sending WhatsApp message to {contact}")

        # Send in background thread
        thread = threading.Thread(
            target=self._send_whatsapp_message,
            args=(contact, message),
            daemon=True
        )
        thread.start()

    def _send_whatsapp_message(self, contact: str, message: str):
        """Send WhatsApp message in background"""
        try:
            success = self.whatsapp.send_message(contact, message)

            if success:
                self.window.conversation_view.add_message(
                    "assistant",
                    f"✅ WhatsApp message sent to {contact}"
                )
            else:
                self.window.conversation_view.add_message(
                    "assistant",
                    f"❌ Failed to send WhatsApp message to {contact}"
                )

        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {e}")
            self.window.conversation_view.add_message(
                "assistant",
                f"❌ Error sending message: {e}"
            )

    def _handle_whatsapp_search(self, data):
        """Handle searching WhatsApp chat history"""
        query = data.get("query", "")
        chat_name = data.get("chat_name")

        if not query:
            return

        # Search in background
        thread = threading.Thread(
            target=self._search_whatsapp_history,
            args=(query, chat_name),
            daemon=True
        )
        thread.start()

    def _search_whatsapp_history(self, query: str, chat_name: str = None):
        """Search WhatsApp history in background"""
        try:
            if chat_name:
                messages = self.whatsapp.read_chat_history(chat_name, limit=100)
                # Filter messages by query
                results = [m for m in messages if query.lower() in m.content.lower()]
            else:
                results = self.whatsapp.search_messages(query, limit=20)

            if results:
                result_text = f"Found {len(results)} message(s) matching '{query}':\n\n"
                for msg in results[:5]:  # Show first 5
                    time_str = msg.timestamp.strftime("%Y-%m-%d %H:%M")
                    result_text += f"[{time_str}] {msg.sender_name}: {msg.content[:100]}\n\n"

                if len(results) > 5:
                    result_text += f"... and {len(results) - 5} more"

                self.window.conversation_view.add_message("assistant", result_text)
            else:
                self.window.conversation_view.add_message(
                    "assistant",
                    f"No messages found matching '{query}'"
                )

        except Exception as e:
            logger.error(f"Error searching WhatsApp history: {e}")
            self.window.conversation_view.add_message(
                "assistant",
                f"Error searching messages: {e}"
            )

    def _handle_shutdown(self):
        """Handle application shutdown"""
        logger.info("Shutting down Jarvis AI Assistant")

        # Stop WhatsApp integration
        if self.whatsapp_enabled:
            self.whatsapp.stop()

        # Stop wake word detection
        if self.wake_word_detector.is_running():
            self.wake_word_detector.stop()

    def run(self):
        """Run the application"""
        logger.info("Starting Jarvis AI Assistant")

        # Test microphone
        if not self.audio_recorder.test_microphone():
            logger.error("Microphone test failed!")
            self.window.conversation_view.add_message(
                "assistant",
                "⚠️ WARNING: Microphone access failed!\n\n"
                "Please check your microphone permissions in Windows Settings."
            )
        else:
            # Start wake word detection
            try:
                self.wake_word_detector.start()
                logger.info("Wake word detection started")

                # Welcome message
                self.window.conversation_view.add_message(
                    "assistant",
                    f"Hello! I'm Jarvis, your AI assistant.\n\n"
                    f"✅ All systems operational!\n\n"
                    f"🎤 Say '{Config.WAKE_WORD.title()}' to activate voice mode\n"
                    f"📸 Click 'Capture Screenshot' to share your screen\n"
                    f"🎙️ Click 'Record' to test voice input\n"
                    f"⌨️ Or just type a message!\n\n"
                    f"I can see screenshots, maintain conversation history, and respond with voice."
                )

            except Exception as e:
                logger.error(f"Failed to start wake word detection: {e}")
                self.window.conversation_view.add_message(
                    "assistant",
                    f"⚠️ Wake word detection failed: {e}\n\n"
                    f"You can still use text input and manual voice recording."
                )

        # Update status
        self.window.update_status("Idle")

        # Start GUI
        self.window.run()

    def _handle_datetime_query(self, text: str) -> bool:
        """
        Handle basic date/time queries without internet

        Returns:
            True if command was handled
        """
        import re

        text_lower = text.lower()
        now = datetime.now()

        # Pattern: date queries
        date_patterns = [
            r"what(?:'s|\s+is)\s+(?:the\s+)?date(?:\s+today)?",
            r"what\s+day\s+is\s+(?:it|today)",
            r"(?:what(?:'s|\s+is)|tell\s+me)\s+(?:the\s+)?(?:today(?:'s|\s+))?date",
            r"what(?:'s|\s+is)\s+today",
        ]

        for pattern in date_patterns:
            if re.search(pattern, text_lower):
                response = f"It's {now.strftime('%A, %B %d, %Y')}, sir."
                self.window.conversation_view.add_message("assistant", response)
                self.tts.speak(response, play_audio=True)
                return True

        # Pattern: time queries
        time_patterns = [
            r"what(?:'s|\s+is)\s+(?:the\s+)?time",
            r"what\s+time\s+is\s+it",
        ]

        for pattern in time_patterns:
            if re.search(pattern, text_lower):
                response = f"It's {now.strftime('%I:%M %p')}, sir."
                self.window.conversation_view.add_message("assistant", response)
                self.tts.speak(response, play_audio=True)
                return True

        return False

    def _handle_system_control_intent(self, text: str) -> bool:
        """
        Handle system control commands (open apps, files, websites)
        Uses GPT-4o to intelligently determine what to open

        Returns:
            True if command was handled
        """
        import re

        text_lower = text.lower()

        # Pattern: "open [something]"
        if "open" in text_lower:
            match = re.search(r"open\s+(.+?)(?:\s+please)?$", text_lower)
            if match:
                target = match.group(1).strip()

                # Use GPT-4o to intelligently decide what to open
                analysis_prompt = f"""Analyze this request and determine what to open: "{text}"

You must output EXACTLY 3 lines:
Line 1: TYPE - One of: WEBSITE, APP, STOCK, or UNKNOWN
Line 2: TARGET - The exact URL, app name, or stock ticker
Line 3: DISPLAY_NAME - Short name to tell the user (e.g., "Gmail", "Tesla stock", "Spotify")

Examples:
Input: "open gmail"
WEBSITE
https://gmail.com
Gmail

Input: "open gmail stock"
STOCK
https://www.google.com/finance/quote/GOOGL:NASDAQ
Gmail stock

Input: "open tesla stock"
STOCK
https://www.google.com/finance/quote/TSLA:NASDAQ
Tesla stock

Input: "open spotify"
APP
spotify
Spotify

Input: "open github.com"
WEBSITE
https://github.com
GitHub

Input: "open youtube"
WEBSITE
https://youtube.com
YouTube

Rules:
- If it says "stock" or "stock price", it's STOCK type
- If it ends with .com/.org/.net or is a known website, it's WEBSITE
- If it's a known app name (Spotify, Chrome, VS Code, etc.), it's APP
- For stocks, use Google Finance format: https://www.google.com/finance/quote/TICKER:NASDAQ
- For websites, add https:// if not present
- If unclear, default to WEBSITE for .com domains, else APP

Output ONLY 3 lines, no explanations."""

                try:
                    messages = [{"role": "user", "content": analysis_prompt}]
                    response = self.openai_client.chat_completion(messages)

                    # Parse response
                    lines = [line.strip() for line in response.strip().split('\n') if line.strip()]

                    if len(lines) >= 3:
                        action_type = lines[0].upper()
                        target_value = lines[1]
                        display_name = lines[2]

                        logger.info(f"GPT analyzed: TYPE={action_type}, TARGET={target_value}, NAME={display_name}")

                        # Execute based on type
                        if action_type == "WEBSITE" or action_type == "STOCK":
                            self.system_control.open_url(target_value)
                            response_msg = f"Opening {display_name}, sir."
                        elif action_type == "APP":
                            success = self.system_control.open_app(target_value)
                            if success:
                                response_msg = f"Opening {display_name}, sir."
                            else:
                                response_msg = f"I couldn't find the {display_name} application, sir."
                        else:
                            # UNKNOWN - try as website first, then app
                            if any(ext in target.lower() for ext in ['.com', '.org', '.net']):
                                self.system_control.open_url(target)
                                response_msg = f"Opening {target}, sir."
                            else:
                                success = self.system_control.open_app(target)
                                if success:
                                    response_msg = f"Opening {target}, sir."
                                else:
                                    return False

                        self.window.conversation_view.add_message("assistant", response_msg)
                        self.tts.speak(response_msg, play_audio=True)
                        return True

                except Exception as e:
                    logger.error(f"Error analyzing open request with GPT: {e}")
                    # Fallback to simple logic
                    if any(ext in target for ext in ['.com', '.org', '.net', 'http']):
                        url = target if target.startswith('http') else f"https://{target}"
                        self.system_control.open_url(url)
                        self.window.conversation_view.add_message("assistant", f"Opening {target}, sir.")
                        self.tts.speak(f"Opening {target}, sir", play_audio=True)
                        return True
                    else:
                        success = self.system_control.open_app(target)
                        if success:
                            self.window.conversation_view.add_message("assistant", f"Opening {target}, sir.")
                            self.tts.speak(f"Opening {target}, sir", play_audio=True)
                            return True

        # Pattern: "search google for [query]" or "google [query]"
        if "search" in text_lower and "google" in text_lower:
            match = re.search(r"(?:search\s+google\s+for|google)\s+(.+)", text_lower)
            if match:
                query = match.group(1).strip()
                self.system_control.search_google(query)
                self.window.conversation_view.add_message("assistant", f"Searching Google for '{query}', sir.")
                self.tts.speak(f"Searching Google, sir", play_audio=True)
                return True

        return False

    def _handle_search_intent(self, text: str) -> bool:
        """
        Handle web search commands

        Returns:
            True if command was handled
        """
        import re

        text_lower = text.lower()

        # SPECIAL CASE 1: Stock price queries - Use GPT-4o for intelligent stock lookup
        stock_patterns = [
            r"(?:what(?:'s|\s+is)|how(?:'s|\s+is))\s+(.+?)\s+(?:stock|price|trading|doing)",
            r"(?:get|give|show|tell|check|find)\s+(?:me\s+)?(?:the\s+)?(?:latest\s+)?(.+?)\s+(?:stock|price)",
        ]

        for pattern in stock_patterns:
            match = re.search(pattern, text_lower)
            if match:
                company = match.group(1).strip()

                # Skip if too short or looks like calendar
                if len(company) < 2 or any(kw in company for kw in ["calendar", "schedule", "meeting"]):
                    continue

                # Use GPT-4o to get correct stock URL
                stock_prompt = f"""Find the stock ticker and exchange for: "{company}"

Output EXACTLY 2 lines:
Line 1: The correct Google Finance URL
Line 2: Company display name

Examples:
Input: tesla
https://www.google.com/finance/quote/TSLA:NASDAQ
Tesla

Input: apple
https://www.google.com/finance/quote/AAPL:NASDAQ
Apple

Input: alphabet
https://www.google.com/finance/quote/GOOGL:NASDAQ
Alphabet (Google)

Rules:
- Use format: https://www.google.com/finance/quote/TICKER:EXCHANGE
- Common exchanges: NASDAQ, NYSE, LSE, TSE
- For major US tech stocks, use NASDAQ
- Output ONLY 2 lines."""

                try:
                    messages = [{"role": "user", "content": stock_prompt}]
                    response = self.openai_client.chat_completion(messages)

                    lines = [line.strip() for line in response.strip().split('\n') if line.strip()]

                    if len(lines) >= 2:
                        finance_url = lines[0]
                        display_name = lines[1]

                        logger.info(f"GPT stock lookup: {company} -> {finance_url}")

                        self.system_control.open_url(finance_url)

                        response_msg = f"Opening {display_name} stock on Google Finance, sir."
                        self.window.conversation_view.add_message("assistant", response_msg)
                        self.tts.speak(response_msg, play_audio=True)

                        return True

                except Exception as e:
                    logger.error(f"Error looking up stock with GPT: {e}")
                    # Fallback to simple mapping
                    ticker_map = {
                        "tesla": "TSLA",
                        "apple": "AAPL",
                        "microsoft": "MSFT",
                        "google": "GOOGL",
                        "amazon": "AMZN",
                        "meta": "META",
                        "nvidia": "NVDA",
                    }
                    ticker = ticker_map.get(company.lower(), company.upper())
                    finance_url = f"https://www.google.com/finance/quote/{ticker}:NASDAQ"
                    self.system_control.open_url(finance_url)

                    response_msg = f"Opening {company.title()} stock, sir."
                    self.window.conversation_view.add_message("assistant", response_msg)
                    self.tts.speak(response_msg, play_audio=True)

                    return True

        # SPECIAL CASE 2: Weather queries - Open Google search automatically
        weather_patterns = [
            r"(?:what(?:'s|\s+is)|how(?:'s|\s+is))\s+(?:the\s+)?weather\s+(?:in|at|for)\s+(.+)",
            r"weather\s+(?:in|at|for)\s+(.+)",
            r"(?:check|tell|show)\s+(?:me\s+)?(?:the\s+)?weather\s+(?:in|at|for)\s+(.+)",
        ]

        for pattern in weather_patterns:
            match = re.search(pattern, text_lower)
            if match:
                location = match.group(1).strip().rstrip("?")

                # Open Google search for weather
                search_query = f"weather in {location}"
                self.system_control.search_google(search_query)

                response = f"Opening weather for {location.title()}, sir."
                self.window.conversation_view.add_message("assistant", response)
                self.tts.speak(response, play_audio=True)

                return True

        # GENERAL CASE: Other search queries
        search_patterns = [
            r"search\s+(?:for\s+)?(.+)",
            r"look\s+up\s+(.+)",
            r"find\s+(?:information\s+(?:on|about)\s+)?(.+)",
            r"what(?:'s|\s+is)\s+(?:the\s+)?(.+?)(?:\?|$)",
            r"update\s+me\s+(?:on|with|about)\s+(?:the\s+)?(.+)",  # "update me on X"
            r"tell\s+me\s+about\s+(?:the\s+)?(.+)",  # "tell me about X"
            r"what(?:'s|\s+is)\s+the\s+latest\s+(?:on|about|with)\s+(.+)",  # "what's the latest on X"
            r"(?:give\s+me|get\s+me)\s+(?:an?\s+)?(?:update|info|information)\s+(?:on|about)\s+(.+)",  # "give me an update on X"
            r"check\s+(?:for\s+me\s+)?(?:the\s+)?(?:latest\s+)?(.+)",  # "check (for me) (the) (latest) X"
        ]

        for pattern in search_patterns:
            match = re.search(pattern, text_lower)
            if match and "google" not in text_lower:  # Avoid conflict with system_control
                query = match.group(1).strip().rstrip("?")

                # Skip if this looks like a calendar query (calendar-specific words)
                calendar_keywords = ["calendar", "schedule", "meeting", "event", "appointment"]
                if any(keyword in query for keyword in calendar_keywords):
                    continue

                # Don't search for very short queries (likely not search intent)
                if len(query) < 3:
                    continue

                self.window.conversation_view.add_message("assistant", f"Searching for '{query}', sir.")
                self.tts.speak(f"Searching, sir", play_audio=True)

                # Get search results and summarize
                summary = self.web_search.search_and_summarize(query, self.openai_client)

                self.window.conversation_view.add_message("assistant", summary)

                # Speak only first sentence for speed
                first_sentence = summary.split('.')[0] + '.' if '.' in summary else summary
                self.tts.speak(first_sentence, play_audio=True)

                return True

        return False

    def _handle_calendar_intent(self, text: str) -> bool:
        """
        Handle calendar-related commands

        Returns:
            True if command was handled
        """
        import re

        text_lower = text.lower()

        # Pattern: calendar queries
        calendar_patterns = [
            r"(?:check|show|tell|what(?:'s|\s+is))\s+(?:my\s+)?(?:on\s+my\s+)?calendar",  # "check my calendar", "check calendar", "what's on my calendar"
            r"(?:show|tell)\s+me\s+my\s+(?:calendar|schedule|meetings)",
            r"do\s+i\s+have\s+any\s+(?:meetings|events|appointments)",
            r"what(?:'s|\s+is)\s+my\s+schedule",
            r"what(?:'s|\s+do)\s+(?:do\s+)?i\s+have\s+(?:on\s+my\s+calendar|scheduled|coming\s+up|this\s+week|next\s+week|today|tomorrow)",  # "what do I have to do", "what do I have this week"
            r"(?:my\s+)?(?:schedule|calendar|meetings|events)\s+(?:for\s+)?(?:this\s+week|next\s+week|today|tomorrow|this\s+month)",  # "my schedule this week"
            r"(?:upcoming|coming)\s+(?:meetings|events|appointments)",  # "upcoming meetings"
        ]

        for pattern in calendar_patterns:
            if re.search(pattern, text_lower):
                if not self.calendar.enabled:
                    response = "Calendar integration is not set up yet, sir. Would you like me to guide you through the setup?"
                    self.window.conversation_view.add_message("assistant", response)
                    self.tts.speak("Calendar not yet configured, sir", play_audio=True)
                    return True

                # Check if asking about upcoming week vs today
                if any(word in text_lower for word in ["week", "coming", "upcoming"]):
                    # Get upcoming events for the week (7 days)
                    events = self.calendar.get_upcoming_events(hours=168)  # 7 days = 168 hours

                    if not events:
                        response = "No events scheduled for the upcoming week, sir."
                    elif len(events) == 1:
                        response = f"You have 1 event this week: {events[0]}, sir."
                    else:
                        response = f"You have {len(events)} events this week, sir."

                else:
                    # Get today's events
                    summary = self.calendar.get_events_summary()
                    response = summary

                self.window.conversation_view.add_message("assistant", response)
                self.tts.speak(response, play_audio=True)
                return True

        # Pattern: "when is my next meeting"
        if re.search(r"when\s+is\s+my\s+next\s+(?:meeting|event|appointment)", text_lower):
            if not self.calendar.enabled:
                response = "Calendar not configured, sir."
                self.window.conversation_view.add_message("assistant", response)
                self.tts.speak(response, play_audio=True)
                return True

            next_event = self.calendar.get_next_event()
            if next_event:
                response = f"Your next event is {next_event}, sir."
            else:
                response = "No upcoming events, sir."

            self.window.conversation_view.add_message("assistant", response)
            self.tts.speak(response, play_audio=True)
            return True

        return False

    def _get_environmental_context(self) -> str:
        """Get environmental context (time, calendar, etc.) for AI prompt"""
        now = datetime.now()

        context_parts = [
            f"Current time: {now.strftime('%I:%M %p')}",
            f"Date: {now.strftime('%A, %B %d, %Y')}",
        ]

        # Add calendar context if enabled
        if self.calendar.enabled:
            calendar_context = self.calendar.get_context_string()
            context_parts.append(calendar_context)

        return "[CONTEXT] " + ", ".join(context_parts)

    def _get_calendar_context_for_whatsapp(self) -> str:
        """Get detailed calendar context for WhatsApp auto-reply decisions"""
        if not self.calendar.enabled:
            return "CALENDAR: Not configured"

        try:
            # Get today's events
            today_events = self.calendar.get_todays_events()

            # Get upcoming events for the next 7 days
            upcoming_events = self.calendar.get_upcoming_events(hours=168)  # 7 days

            if not upcoming_events:
                return "CALENDAR: No upcoming events in the next 7 days"

            # Format calendar info
            calendar_lines = ["=== YOUR CALENDAR ==="]

            # Today's events
            if today_events:
                calendar_lines.append("\nTODAY:")
                for event in today_events:
                    time_str = event.start.strftime('%I:%M %p') if event.start else "All day"
                    calendar_lines.append(f"  - {time_str}: {event.summary}")

            # This week's events
            if len(upcoming_events) > len(today_events):
                calendar_lines.append("\nTHIS WEEK:")
                shown = 0
                for event in upcoming_events:
                    # Skip today's events (already shown)
                    if event.start and event.start.date() == datetime.now().date():
                        continue

                    if shown >= 10:  # Limit to 10 upcoming events
                        break

                    date_str = event.start.strftime('%a %b %d') if event.start else "TBD"
                    time_str = event.start.strftime('%I:%M %p') if event.start else "All day"
                    calendar_lines.append(f"  - {date_str} at {time_str}: {event.summary}")
                    shown += 1

            calendar_lines.append("\nIMPORTANT: Check for scheduling conflicts when deciding WhatsApp replies!")

            return "\n".join(calendar_lines)

        except Exception as e:
            logger.error(f"Error getting calendar context for WhatsApp: {e}")
            return "CALENDAR: Error loading schedule"
