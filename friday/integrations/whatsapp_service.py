"""
WhatsApp Web integration service using Selenium
"""

import time
import uuid
from pathlib import Path
from queue import Queue
from threading import Thread, Event, Lock
from typing import List, Optional, Callable, Dict
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException
)

from friday.integrations.whatsapp_models import (
    WhatsAppMessage,
    WhatsAppContact,
    WhatsAppNotification,
    MessageDirection,
    MessageType
)
from friday.integrations.whatsapp_database import WhatsAppDatabase
from friday.utils.logger import get_logger
from friday.config import Config

logger = get_logger("whatsapp")


class WhatsAppService:
    """
    WhatsApp Web automation service for Friday AI Assistant

    Features:
    - Read chat history
    - Monitor incoming messages
    - Send messages
    - Notification system
    """

    def __init__(self, config: Config):
        self.config = config
        self.driver = None
        self.is_running = False
        self.is_connected = False
        self.message_queue = Queue()
        self.notification_callbacks: List[Callable] = []
        self.gui_window = None  # Reference to GUI window for debug logging

        # Database for chat history
        self.db = WhatsAppDatabase()

        # Session directory
        self.session_dir = Path.home() / "AppData" / "Local" / "Friday_WhatsApp_Session"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # Monitoring thread
        self.monitor_thread = None
        self.stop_event = Event()

        # Last seen message tracking
        self.last_seen_messages: Dict[str, str] = {}
        self.last_message_previews: Dict[str, str] = {}  # Track message previews in chat list
        self.last_check_time = datetime.now()

        # Thread safety
        self.driver_lock = Lock()

        logger.info("WhatsApp service initialized")

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

    def start(self, headless: bool = False) -> bool:
        """
        Start WhatsApp Web connection

        Args:
            headless: Run browser in headless mode (may be detected)

        Returns:
            True if successfully connected, False otherwise
        """
        try:
            logger.info("Starting WhatsApp integration...")

            # Use standard Selenium with webdriver-manager (more reliable)
            logger.info("Launching Chrome browser...")
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from webdriver_manager.chrome import ChromeDriverManager
            import shutil

            # Clean up any locked Chrome profile directories
            try:
                lock_file = self.session_dir / "SingletonLock"
                if lock_file.exists():
                    logger.info("Removing stale Chrome lock file...")
                    lock_file.unlink()
            except Exception as e:
                logger.debug(f"Could not remove lock file: {e}")

            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_argument(f"--user-data-dir={self.session_dir}")

            # Additional stability options
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-gpu")  # Helps with stability
            chrome_options.add_argument("--disable-software-rasterizer")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-background-timer-throttling")
            chrome_options.add_argument("--disable-backgrounding-occluded-windows")
            chrome_options.add_argument("--disable-renderer-backgrounding")
            chrome_options.add_argument("--no-first-run")
            chrome_options.add_argument("--no-default-browser-check")

            # Set window size explicitly
            chrome_options.add_argument("--window-size=1200,900")

            # Disable logging to reduce errors
            chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])

            # Use webdriver-manager to automatically get correct ChromeDriver
            logger.info("Installing/updating ChromeDriver...")
            service = Service(ChromeDriverManager().install())

            logger.info("Starting Chrome...")
            self.driver = webdriver.Chrome(service=service, options=chrome_options)

            logger.info("Navigating to WhatsApp Web...")
            self.driver.get('https://web.whatsapp.com')

            # Check if already logged in or need QR scan
            try:
                logger.info("Checking for existing session...")
                # Try multiple selectors and increase timeout to 60 seconds
                WebDriverWait(self.driver, 60).until(
                    lambda driver: (
                        driver.find_elements(By.CSS_SELECTOR, '[data-testid="chat-list"]') or
                        driver.find_elements(By.CSS_SELECTOR, '[data-testid="conversation-panel-wrapper"]') or
                        driver.find_elements(By.XPATH, '//div[@id="pane-side"]') or
                        driver.find_elements(By.CSS_SELECTOR, 'div[data-testid="chat"]')
                    )
                )
                logger.info("✓ WhatsApp session restored successfully")
                self.is_connected = True

            except TimeoutException:
                logger.warning("⚠ QR code scan required")
                logger.info("Please scan the QR code in the browser window...")

                # Wait up to 3 minutes for QR scan (increased from 2)
                try:
                    WebDriverWait(self.driver, 180).until(
                        lambda driver: (
                            driver.find_elements(By.CSS_SELECTOR, '[data-testid="chat-list"]') or
                            driver.find_elements(By.CSS_SELECTOR, '[data-testid="conversation-panel-wrapper"]') or
                            driver.find_elements(By.XPATH, '//div[@id="pane-side"]') or
                            driver.find_elements(By.CSS_SELECTOR, 'div[data-testid="chat"]')
                        )
                    )
                    logger.info("✓ QR code scanned successfully!")
                    self.is_connected = True

                except TimeoutException:
                    logger.error("✗ QR code scan timeout. Please try again.")
                    self.stop()
                    return False

            # Minimize window after successful login
            try:
                self.driver.minimize_window()
                logger.info("Browser window minimized")
            except Exception as e:
                logger.warning(f"Could not minimize window: {e}")

            # Start monitoring thread
            self.is_running = True
            self.stop_event.clear()
            self.monitor_thread = Thread(target=self._monitor_messages, daemon=True)
            self.monitor_thread.start()

            logger.info("✓ WhatsApp service is ready")
            return True

        except Exception as e:
            logger.error(f"Failed to start WhatsApp service: {e}")
            self.stop()
            return False

    def _monitor_messages(self):
        """Background thread to monitor for new messages"""
        logger.info("Message monitoring started")
        self._log_debug("Message monitoring thread started", "SUCCESS")
        check_count = 0

        while self.is_running and not self.stop_event.is_set():
            try:
                if not self.is_connected:
                    logger.debug("Not connected, waiting...")
                    time.sleep(5)
                    continue

                check_count += 1
                logger.debug(f"[Check #{check_count}] Checking for new messages...")
                self._log_debug(f"Check #{check_count}: Scanning for new messages...", "DEBUG")

                # Check for new messages
                new_messages = self._check_for_new_messages()

                if new_messages:
                    logger.info(f"✓ Found {len(new_messages)} new message(s)")
                    self._log_debug(f"Found {len(new_messages)} new message(s)!", "SUCCESS")

                    for message in new_messages:
                        logger.info(f"  - From: {message.sender_name}, Content: {message.content[:50]}...")
                        self._log_debug(f"📩 Message from {message.sender_name}: {message.content[:50]}...", "SUCCESS")

                        # Save to database
                        self.db.save_message(message)

                        # Add to queue
                        self.message_queue.put(message)

                        # Trigger notifications
                        self._trigger_notification(message)
                        self._log_debug(f"Notification triggered for {message.sender_name}", "SUCCESS")
                else:
                    logger.debug(f"[Check #{check_count}] No new messages")

                # Check every 3 seconds
                time.sleep(3)

            except Exception as e:
                logger.error(f"Error in message monitor: {e}", exc_info=True)
                self._log_debug(f"Error in monitor: {str(e)}", "ERROR")
                time.sleep(5)

        logger.info("Message monitoring stopped")
        self._log_debug("Message monitoring stopped", "WARNING")

    def _check_for_new_messages(self) -> List[WhatsAppMessage]:
        """Check for new messages by monitoring chat list for changes"""
        new_messages = []

        try:
            with self.driver_lock:
                self._log_debug("Checking all visible chats for new messages...", "DEBUG")

                # DEBUG: Dump page source on first check to see what's actually there
                if not hasattr(self, '_dumped_html'):
                    try:
                        page_html = self.driver.page_source
                        dump_file = Path.home() / "whatsapp_page_dump.html"
                        dump_file.write_text(page_html, encoding='utf-8')
                        logger.info(f"📄 Dumped page HTML to: {dump_file}")
                        self._log_debug(f"Page HTML dumped to: {dump_file}", "DEBUG")
                        self._dumped_html = True
                    except Exception as e:
                        logger.error(f"Could not dump HTML: {e}")

                # Try multiple selectors for chat list
                all_chats = []

                # Method 1: role="listitem"
                all_chats = self.driver.find_elements(By.CSS_SELECTOR, 'div[role="listitem"]')
                logger.debug(f"Method 1 (role=listitem): Found {len(all_chats)} chats")

                # Method 2: If method 1 fails, try data-testid
                if len(all_chats) == 0:
                    all_chats = self.driver.find_elements(By.CSS_SELECTOR, '[data-testid="chat"]')
                    logger.debug(f"Method 2 (data-testid=chat): Found {len(all_chats)} chats")

                # Method 3: Try class-based selector
                if len(all_chats) == 0:
                    all_chats = self.driver.find_elements(By.CSS_SELECTOR, '._3m_Xw')
                    logger.debug(f"Method 3 (class _3m_Xw): Found {len(all_chats)} chats")

                # Method 4: Try finding the sidebar and getting all divs with specific structure
                if len(all_chats) == 0:
                    try:
                        sidebar = self.driver.find_element(By.CSS_SELECTOR, '#pane-side')
                        all_chats = sidebar.find_elements(By.XPATH, './/div[contains(@class, "chat")]')
                        logger.debug(f"Method 4 (sidebar divs): Found {len(all_chats)} chats")
                    except:
                        pass

                logger.debug(f"Found {len(all_chats)} total chat(s) in list")
                self._log_debug(f"Scanning {len(all_chats)} chat(s) for changes...", "DEBUG")

                # If we found chats, check each one
                if len(all_chats) > 0:
                    # Check first 20 chats for new messages (should cover recent conversations)
                    for idx, chat in enumerate(all_chats[:20], 1):
                        try:
                            # NEW APPROACH: Look for unread indicator badges/spans
                            has_unread = False

                            # Check for unread badge (green circle with number)
                            try:
                                unread_badge = chat.find_element(By.CSS_SELECTOR, 'span[data-testid="icon-unread"], span[aria-label*="unread"]')
                                has_unread = True
                                logger.debug(f"Chat #{idx} has unread badge")
                            except:
                                pass

                            # Check for bold text (indicates unread)
                            try:
                                bold_elem = chat.find_element(By.CSS_SELECTOR, 'span[title][dir="auto"]')
                                font_weight = bold_elem.value_of_css_property('font-weight')
                                if font_weight and int(font_weight) >= 600:
                                    has_unread = True
                                    logger.debug(f"Chat #{idx} has bold text (unread)")
                            except:
                                pass

                            if not has_unread:
                                continue  # Skip read messages

                            logger.debug(f"Chat #{idx} appears to have unread messages!")

                            # Get chat name
                            chat_name = None
                            try:
                                chat_name_elem = chat.find_element(
                                    By.CSS_SELECTOR,
                                    'span[dir="auto"][title]'
                                )
                                chat_name = chat_name_elem.get_attribute('title')
                            except:
                                try:
                                    chat_name_elem = chat.find_element(
                                        By.CSS_SELECTOR,
                                        'span[title]'
                                    )
                                    chat_name = chat_name_elem.get_attribute('title')
                                except:
                                    continue

                            if not chat_name or len(chat_name.strip()) == 0:
                                continue

                            # Get message preview (last message text shown in chat list)
                            try:
                                # Try to find the message preview span
                                preview_elem = chat.find_element(
                                    By.CSS_SELECTOR,
                                    'span[dir="ltr"]'
                                )
                                message_preview = preview_elem.text.strip()
                            except:
                                try:
                                    # Alternative: look for any span with message text
                                    preview_spans = chat.find_elements(By.CSS_SELECTOR, 'span')
                                    message_preview = ""
                                    for span in preview_spans:
                                        text = span.text.strip()
                                        if len(text) > 5:  # Meaningful text
                                            message_preview = text
                                            break
                                except:
                                    message_preview = ""

                            if not message_preview:
                                continue

                            # Check if this is a new/changed message preview
                            if chat_name in self.last_message_previews:
                                last_preview = self.last_message_previews[chat_name]
                                if last_preview == message_preview:
                                    # No change in this chat
                                    continue
                                else:
                                    # Message preview changed - new message!
                                    logger.info(f"✓ Detected new message in chat: {chat_name}")
                                    self._log_debug(f"NEW: Message preview changed for {chat_name}", "SUCCESS")

                                    # Update preview
                                    self.last_message_previews[chat_name] = message_preview

                                    # Click to open chat and read the new message
                                    logger.debug(f"  Opening chat to read new message...")
                                    chat.click()
                                    time.sleep(1.5)

                                    # Read messages from this chat
                                    chat_messages = self._read_current_chat_messages(chat_name)
                                    logger.info(f"  Read {len(chat_messages)} new message(s) from {chat_name}")
                                    if chat_messages:
                                        self._log_debug(f"Read {len(chat_messages)} new message(s) from {chat_name}", "SUCCESS")
                                    new_messages.extend(chat_messages)
                            else:
                                # First time seeing this chat - store preview but don't trigger notification
                                logger.debug(f"First time seeing chat: {chat_name}, storing preview")
                                self.last_message_previews[chat_name] = message_preview

                        except (StaleElementReferenceException, NoSuchElementException) as e:
                            logger.debug(f"  Error processing chat #{idx}: {e}")
                            continue
                        except Exception as e:
                            logger.debug(f"  Unexpected error processing chat #{idx}: {e}")
                            continue

                    if not new_messages:
                        logger.debug("No new messages detected")
                else:
                    # No chats found at all - might be page loading issue
                    self._log_debug("WARNING: Could not find any chats! Check if page loaded correctly.", "WARNING")
                    logger.warning("Could not find any chat elements on page")

        except Exception as e:
            logger.error(f"Error checking for new messages: {e}", exc_info=True)
            self._log_debug(f"Error checking messages: {str(e)}", "ERROR")

        return new_messages

    def _read_current_chat_messages(self, chat_name: str, limit: int = 10) -> List[WhatsAppMessage]:
        """Read messages from the currently open chat"""
        messages = []

        try:
            # Wait for messages to load
            time.sleep(1)

            logger.debug(f"    Reading messages from {chat_name}...")

            # Find message container
            message_container = self.driver.find_element(
                By.CSS_SELECTOR,
                '[data-testid="conversation-panel-messages"]'
            )
            logger.debug(f"    Found message container")

            # Find all message elements (recent ones)
            message_elements = message_container.find_elements(
                By.CSS_SELECTOR,
                'div[data-testid="msg-container"]'
            )
            logger.debug(f"    Found {len(message_elements)} total message elements")

            # Get last N messages
            recent_messages = message_elements[-limit:]
            logger.debug(f"    Processing last {len(recent_messages)} messages")

            for idx, msg_elem in enumerate(recent_messages, 1):
                try:
                    # Check if message is incoming or outgoing
                    is_from_me = 'message-out' in msg_elem.get_attribute('class')

                    # Get message text
                    try:
                        text_elem = msg_elem.find_element(By.CSS_SELECTOR, 'span.selectable-text')
                        message_text = text_elem.text
                    except:
                        message_text = "[Media or unsupported message]"

                    logger.debug(f"      Msg #{idx}: from_me={is_from_me}, text='{message_text[:30]}...'")

                    # Get timestamp
                    try:
                        time_elem = msg_elem.find_element(By.CSS_SELECTOR, 'span[data-testid="msg-time"]')
                        time_text = time_elem.text
                        # For now, use current time (parsing WhatsApp time is complex)
                        timestamp = datetime.now()
                    except:
                        timestamp = datetime.now()

                    # Get sender name (for groups)
                    sender_name = chat_name
                    if not is_from_me:
                        try:
                            sender_elem = msg_elem.find_element(By.CSS_SELECTOR, 'span[dir="auto"][role="button"]')
                            sender_name = sender_elem.text
                        except:
                            pass
                    else:
                        sender_name = "Me"

                    # Create message ID
                    message_id = str(uuid.uuid4())

                    # Check if we've seen this message before
                    if chat_name in self.last_seen_messages:
                        if message_text == self.last_seen_messages[chat_name]:
                            logger.debug(f"      Msg #{idx}: Already seen, skipping")
                            continue  # Already processed

                    # Only process incoming messages
                    if not is_from_me:
                        # Create WhatsAppMessage object
                        wa_message = WhatsAppMessage(
                            id=message_id,
                            chat_name=chat_name,
                            sender_name=sender_name,
                            content=message_text,
                            timestamp=timestamp,
                            direction=MessageDirection.INCOMING,
                            message_type=MessageType.TEXT,
                            is_from_me=False,
                            is_read=False
                        )

                        messages.append(wa_message)
                        logger.info(f"      ✓ New message from {sender_name}: {message_text[:50]}...")

                    # Update last seen
                    self.last_seen_messages[chat_name] = message_text

                except Exception as e:
                    logger.debug(f"      Error parsing message #{idx}: {e}")
                    continue

            logger.debug(f"    Collected {len(messages)} new incoming message(s)")

        except Exception as e:
            logger.error(f"    Error reading chat messages: {e}", exc_info=True)

        return messages

    def send_message(self, contact_name: str, message: str, retries: int = 3) -> bool:
        """
        Send a message to a contact

        Args:
            contact_name: Name of contact or group
            message: Message text to send
            retries: Number of retry attempts

        Returns:
            True if successful, False otherwise
        """
        for attempt in range(retries):
            try:
                logger.info(f"Sending message to '{contact_name}' (attempt {attempt + 1}/{retries})")

                with self.driver_lock:
                    # Find and click search box
                    search_box = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'div[contenteditable="true"][data-tab="3"]'))
                    )
                    search_box.click()
                    time.sleep(0.5)

                    # Clear and search for contact
                    search_box.clear()
                    search_box.send_keys(contact_name)
                    time.sleep(2)

                    # Click on contact from search results
                    try:
                        contact_elem = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, f'//span[@title="{contact_name}"]'))
                        )
                        contact_elem.click()
                        time.sleep(1)
                    except TimeoutException:
                        logger.warning(f"Contact '{contact_name}' not found")
                        return False

                    # Find message input box
                    message_box = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'div[contenteditable="true"][data-tab="10"]'))
                    )
                    message_box.click()
                    time.sleep(0.3)

                    # Type message (handle multi-line)
                    lines = message.split('\n')
                    for i, line in enumerate(lines):
                        message_box.send_keys(line)
                        if i < len(lines) - 1:
                            message_box.send_keys(Keys.SHIFT, Keys.ENTER)

                    time.sleep(0.3)

                    # Send message
                    message_box.send_keys(Keys.ENTER)
                    time.sleep(0.5)

                    logger.info(f"✓ Message sent to '{contact_name}'")

                    # Save to database
                    sent_message = WhatsAppMessage(
                        id=str(uuid.uuid4()),
                        chat_name=contact_name,
                        sender_name="Me",
                        content=message,
                        timestamp=datetime.now(),
                        direction=MessageDirection.OUTGOING,
                        message_type=MessageType.TEXT,
                        is_from_me=True,
                        is_read=True
                    )
                    self.db.save_message(sent_message)

                    return True

            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(2)
                    # Try to recover
                    try:
                        self.driver.refresh()
                        time.sleep(3)
                    except:
                        pass

        logger.error(f"Failed to send message after {retries} attempts")
        return False

    def read_chat_history(self, chat_name: str, limit: int = 100) -> List[WhatsAppMessage]:
        """
        Read chat history from database

        Args:
            chat_name: Name of contact or group
            limit: Maximum number of messages to retrieve

        Returns:
            List of WhatsAppMessage objects
        """
        return self.db.get_messages_by_chat(chat_name, limit)

    def search_messages(self, query: str, limit: int = 50) -> List[WhatsAppMessage]:
        """Search messages in history"""
        return self.db.search_messages(query, limit)

    def get_all_chats(self) -> List[str]:
        """Get list of all chat names"""
        return self.db.get_all_chats()

    def get_unread_messages(self) -> List[WhatsAppMessage]:
        """Get unread messages from queue"""
        messages = []
        while not self.message_queue.empty():
            messages.append(self.message_queue.get())
        return messages

    def register_notification_callback(self, callback: Callable[[WhatsAppNotification], None]):
        """Register a callback function for new message notifications"""
        self.notification_callbacks.append(callback)
        logger.info(f"Registered notification callback: {callback.__name__}")

    def _trigger_notification(self, message: WhatsAppMessage):
        """Trigger notification callbacks for a new message"""
        notification = WhatsAppNotification(
            chat_name=message.chat_name,
            sender_name=message.sender_name,
            message_preview=message.content[:100],  # First 100 chars
            timestamp=message.timestamp
        )

        for callback in self.notification_callbacks:
            try:
                callback(notification)
            except Exception as e:
                logger.error(f"Error in notification callback: {e}")

    def check_health(self) -> Dict[str, bool]:
        """Check WhatsApp service health"""
        health = {
            'browser_running': False,
            'logged_in': False,
            'phone_connected': False
        }

        try:
            with self.driver_lock:
                # Check browser
                self.driver.current_url
                health['browser_running'] = True

                # Check login
                try:
                    self.driver.find_element(By.CSS_SELECTOR, '[data-testid="chat-list"]')
                    health['logged_in'] = True
                except:
                    health['logged_in'] = False

                # Check phone connection
                try:
                    self.driver.find_element(By.XPATH, '//*[contains(text(), "Phone not connected")]')
                    health['phone_connected'] = False
                except:
                    health['phone_connected'] = True

        except Exception as e:
            logger.error(f"Health check error: {e}")

        return health

    def stop(self):
        """Stop WhatsApp service and cleanup"""
        logger.info("Stopping WhatsApp service...")

        self.is_running = False
        self.stop_event.set()

        # Wait for monitor thread to stop
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)

        # Close browser
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass

        # Close database
        self.db.close()

        logger.info("WhatsApp service stopped")

    def __del__(self):
        """Cleanup on deletion"""
        self.stop()
