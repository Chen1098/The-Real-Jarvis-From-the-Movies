"""
WhatsApp Web.js Service - Python Wrapper
Communicates with Node.js bridge via HTTP
"""

import requests
import subprocess
import time
import logging
from pathlib import Path
from typing import List, Optional, Callable
from threading import Thread, Event
from dataclasses import dataclass

from .whatsapp_models import WhatsAppMessage, WhatsAppNotification, MessageDirection, MessageType

logger = logging.getLogger(__name__)


class WhatsAppWebJSService:
    """WhatsApp service using whatsapp-web.js via Node.js bridge"""

    def __init__(self):
        self.bridge_url = "http://127.0.0.1:3000"
        self.bridge_process = None
        self.is_running = False
        self.is_connected = False
        self.stop_event = Event()
        self.monitor_thread = None
        self.notification_callbacks = []
        self.gui_window = None
        self.last_whatsapp_contact = None

    def set_gui_window(self, window):
        """Set reference to GUI window for debug logging"""
        self.gui_window = window

    def _log_debug(self, message: str, level: str = "INFO"):
        """Send log to both logger and debug window if available"""
        if self.gui_window:
            try:
                self.gui_window.log_debug(message, level)
            except:
                pass  # Ignore if window is closed

    def start(self) -> bool:
        """Start WhatsApp Web.js bridge"""
        try:
            logger.info("Starting WhatsApp Web.js bridge...")
            self._log_debug("Starting WhatsApp Web.js bridge...", "INFO")

            # Check if Node.js is installed
            try:
                result = subprocess.run(['node', '--version'], capture_output=True, text=True)
                logger.info(f"Node.js version: {result.stdout.strip()}")
            except FileNotFoundError:
                logger.error("Node.js is not installed! Please install Node.js from https://nodejs.org/")
                self._log_debug("ERROR: Node.js not found! Install from https://nodejs.org/", "ERROR")
                return False

            # Get bridge directory
            bridge_dir = Path(__file__).parent
            bridge_script = bridge_dir / "whatsapp_bridge.js"
            package_json = bridge_dir / "package.json"

            if not bridge_script.exists():
                logger.error(f"Bridge script not found: {bridge_script}")
                return False

            # Check if node_modules exists, if not, run npm install
            node_modules = bridge_dir / "node_modules"
            if not node_modules.exists():
                logger.info("Installing Node.js dependencies...")
                self._log_debug("Installing Node.js dependencies (this may take a minute)...", "INFO")

                try:
                    # On Windows, use npm.cmd instead of npm
                    import platform
                    import os
                    npm_cmd = 'npm.cmd' if platform.system() == 'Windows' else 'npm'

                    # Set environment variable to skip Chromium download
                    env = os.environ.copy()
                    env['PUPPETEER_SKIP_DOWNLOAD'] = 'true'
                    env['PUPPETEER_SKIP_CHROMIUM_DOWNLOAD'] = 'true'

                    install_result = subprocess.run(
                        [npm_cmd, 'install'],
                        cwd=bridge_dir,
                        capture_output=True,
                        text=True,
                        timeout=180,  # 3 minutes timeout
                        shell=True,  # Use shell on Windows to find npm.cmd in PATH
                        env=env  # Pass environment with skip flags
                    )

                    if install_result.returncode != 0:
                        logger.error(f"npm install failed: {install_result.stderr}")
                        self._log_debug(f"npm install failed: {install_result.stderr}", "ERROR")
                        return False

                    logger.info("Node.js dependencies installed successfully")
                    self._log_debug("Dependencies installed successfully", "SUCCESS")

                except FileNotFoundError:
                    logger.error("npm is not installed! Please install Node.js with npm from https://nodejs.org/")
                    self._log_debug("ERROR: npm not found! Install Node.js from https://nodejs.org/", "ERROR")
                    return False
                except subprocess.TimeoutExpired:
                    logger.error("npm install timed out")
                    self._log_debug("npm install timed out", "ERROR")
                    return False

            # Start the bridge process
            logger.info("Launching Node.js bridge...")
            self._log_debug("Launching Node.js bridge...", "INFO")

            self.bridge_process = subprocess.Popen(
                ['node', str(bridge_script)],
                cwd=bridge_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Redirect stderr to stdout
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Start thread to monitor Node.js output
            def monitor_nodejs_output():
                for line in self.bridge_process.stdout:
                    line = line.strip()
                    if line:
                        logger.info(f"[Node.js] {line}")
                        if 'ERROR' in line or 'error' in line:
                            self._log_debug(f"Node.js: {line}", "ERROR")
                        elif 'ready' in line.lower() or 'success' in line.lower():
                            self._log_debug(f"Node.js: {line}", "SUCCESS")
                        else:
                            self._log_debug(f"Node.js: {line}", "INFO")

            nodejs_monitor_thread = Thread(target=monitor_nodejs_output, daemon=True)
            nodejs_monitor_thread.start()

            # Wait for bridge to be ready
            logger.info("Waiting for bridge to start...")
            max_wait = 30  # 30 seconds
            for i in range(max_wait):
                try:
                    response = requests.get(f"{self.bridge_url}/health", timeout=1)
                    if response.status_code == 200:
                        logger.info("✓ Bridge is running")
                        self._log_debug("Bridge is running", "SUCCESS")
                        break
                except requests.exceptions.RequestException:
                    time.sleep(1)

                if i == max_wait - 1:
                    logger.error("Bridge failed to start within timeout")
                    self._log_debug("Bridge failed to start", "ERROR")
                    self.stop()
                    return False

            # Check WhatsApp client status
            logger.info("Checking WhatsApp client status...")
            status = self._get_status()

            if status and status.get('needsQR'):
                logger.info("⚠ QR code scan required - check the Node.js console window")
                self._log_debug("QR code displayed in Node.js console - please scan!", "WARNING")

            # Start monitoring thread
            self.is_running = True
            self.stop_event.clear()
            self.monitor_thread = Thread(target=self._monitor_messages, daemon=True)
            self.monitor_thread.start()

            # Wait for client to be ready
            logger.info("Waiting for WhatsApp client to be ready...")
            for i in range(120):  # 2 minutes
                status = self._get_status()
                if status and status.get('ready'):
                    self.is_connected = True
                    logger.info("✓ WhatsApp client is ready!")
                    self._log_debug("WhatsApp client ready!", "SUCCESS")
                    return True
                time.sleep(1)

            logger.warning("WhatsApp client not ready yet, but continuing...")
            return True

        except Exception as e:
            logger.error(f"Failed to start WhatsApp bridge: {e}")
            self._log_debug(f"Failed to start: {e}", "ERROR")
            self.stop()
            return False

    def stop(self):
        """Stop the WhatsApp bridge"""
        logger.info("Stopping WhatsApp Web.js service...")

        self.is_running = False
        self.is_connected = False
        self.stop_event.set()

        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)

        if self.bridge_process:
            try:
                self.bridge_process.terminate()
                self.bridge_process.wait(timeout=5)
            except:
                self.bridge_process.kill()

        logger.info("WhatsApp Web.js service stopped")

    def _get_status(self) -> Optional[dict]:
        """Get bridge status"""
        try:
            response = requests.get(f"{self.bridge_url}/status", timeout=2)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None

    def _monitor_messages(self):
        """Background thread to poll for new messages"""
        logger.info("Message monitoring started")
        self._log_debug("Message monitoring started", "SUCCESS")

        while self.is_running and not self.stop_event.is_set():
            try:
                # Poll for new messages
                response = requests.get(f"{self.bridge_url}/messages/new", timeout=2)

                if response.status_code == 200:
                    data = response.json()
                    messages = data.get('messages', [])

                    if messages:
                        logger.info(f"✓ Received {len(messages)} new message(s)")
                        self._log_debug(f"Received {len(messages)} new message(s)", "SUCCESS")

                        for msg_data in messages:
                            # Convert to WhatsAppMessage
                            from datetime import datetime

                            # Convert Unix timestamp to datetime
                            try:
                                timestamp = datetime.fromtimestamp(msg_data['timestamp'])
                            except:
                                timestamp = datetime.now()

                            message = WhatsAppMessage(
                                id=msg_data['id'],
                                chat_name=msg_data['chatName'],
                                sender_name=msg_data['senderName'],
                                content=msg_data['body'],
                                timestamp=timestamp,
                                direction=MessageDirection.INCOMING,  # Fixed: use INCOMING not RECEIVED
                                message_type=MessageType.TEXT,
                                is_from_me=msg_data['isFromMe'],
                                is_read=True
                            )

                            # Store the 'from' field for direct replies
                            message.from_id = msg_data['from']

                            logger.info(f"  📩 From {message.sender_name}: {message.content[:50]}...")
                            self._log_debug(f"📩 {message.sender_name}: {message.content[:50]}...", "SUCCESS")

                            # Trigger notification
                            self._trigger_notification(message)

                # Check every 2 seconds (faster polling)
                time.sleep(2)

            except Exception as e:
                logger.error(f"Error in message monitor: {e}")
                self._log_debug(f"Monitor error: {e}", "ERROR")
                time.sleep(5)

        logger.info("Message monitoring stopped")
        self._log_debug("Message monitoring stopped", "WARNING")

    def _trigger_notification(self, message: WhatsAppMessage):
        """Trigger notification callbacks"""
        notification = WhatsAppNotification(
            chat_name=message.chat_name,
            sender_name=message.sender_name,
            message_preview=message.content[:100],
            timestamp=message.timestamp,
            unread_count=1
        )

        # Store the chat ID for direct replies (avoid search)
        self._last_chat_from = message.from_id if hasattr(message, 'from_id') else None

        for callback in self.notification_callbacks:
            try:
                callback(notification)
            except Exception as e:
                logger.error(f"Error in notification callback: {e}", exc_info=True)
                self._log_debug(f"Callback error: {e}", "ERROR")

    def register_notification_callback(self, callback: Callable):
        """Register a callback for new message notifications"""
        self.notification_callbacks.append(callback)
        logger.info(f"Registered notification callback: {callback.__name__}")

    def send_message(self, contact_name: str, message: str) -> bool:
        """Send a message to a contact"""
        try:
            # First, search for the contact
            search_response = requests.post(
                f"{self.bridge_url}/contacts/search",
                json={"query": contact_name},
                timeout=5
            )

            if search_response.status_code != 200:
                logger.error(f"Failed to search for contact: {contact_name}")
                return False

            results = search_response.json().get('results', [])

            if not results:
                logger.error(f"Contact not found: {contact_name}")
                self._log_debug(f"Contact not found: {contact_name}", "ERROR")
                return False

            # Use first match
            chat_id = results[0]['id']
            chat_name = results[0]['name']

            logger.info(f"Sending message to {chat_name}...")
            self._log_debug(f"Sending to {chat_name}...", "INFO")

            # Send message
            send_response = requests.post(
                f"{self.bridge_url}/messages/send",
                json={
                    "chatId": chat_id,
                    "message": message
                },
                timeout=10
            )

            if send_response.status_code == 200:
                logger.info(f"✓ Message sent to {chat_name}")
                self._log_debug(f"✓ Message sent to {chat_name}", "SUCCESS")
                return True
            else:
                error = send_response.json().get('error', 'Unknown error')
                logger.error(f"Failed to send message: {error}")
                self._log_debug(f"Send failed: {error}", "ERROR")
                return False

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self._log_debug(f"Error: {e}", "ERROR")
            return False

    def get_chats(self) -> List[dict]:
        """Get all chats"""
        try:
            response = requests.get(f"{self.bridge_url}/chats", timeout=5)
            if response.status_code == 200:
                return response.json().get('chats', [])
        except Exception as e:
            logger.error(f"Error getting chats: {e}")

        return []

    def get_chat_messages(self, chat_id: str, limit: int = 50) -> List[dict]:
        """Get messages from a specific chat"""
        try:
            response = requests.get(
                f"{self.bridge_url}/chats/{chat_id}/messages",
                params={"limit": limit},
                timeout=10
            )
            if response.status_code == 200:
                return response.json().get('messages', [])
        except Exception as e:
            logger.error(f"Error getting chat messages: {e}")

        return []
