"""
Wake word detection using Porcupine
"""
import pvporcupine
import sounddevice as sd
import numpy as np
from collections import deque
from friday.config import Config
from friday.utils.logger import get_logger

logger = get_logger("wake_word")


class WakeWordDetector:
    """Wake word detector using Picovoice Porcupine"""

    def __init__(self, callback=None):
        """
        Initialize wake word detector

        Args:
            callback: Function to call when wake word detected
        """
        self.access_key = Config.PORCUPINE_ACCESS_KEY
        self.wake_word = Config.WAKE_WORD.lower()
        self.callback = callback

        self.porcupine = None
        self.audio_stream = None
        self.is_listening = False
        self.audio_buffer = deque()

        logger.info(f"WakeWordDetector initialized with wake word: '{self.wake_word}'")

    def start(self):
        """Start listening for wake word"""
        try:
            # Map of supported wake words (Porcupine built-in keywords)
            supported_keywords = ['alexa', 'americano', 'blueberry', 'bumblebee', 'computer',
                                 'grapefruit', 'grasshopper', 'hey google', 'hey siri', 'jarvis',
                                 'ok google', 'picovoice', 'porcupine', 'terminator']

            # Check if wake word is supported
            if self.wake_word not in supported_keywords:
                logger.warning(f"Wake word '{self.wake_word}' not available. Using 'jarvis' instead.")
                self.wake_word = 'jarvis'

            # Create Porcupine instance with keyword string
            self.porcupine = pvporcupine.create(
                access_key=self.access_key,
                keywords=[self.wake_word]
            )

            logger.info(f"Porcupine initialized: {self.porcupine.sample_rate}Hz, frame_length={self.porcupine.frame_length}")

            # Start audio stream
            self.is_listening = True

            self.audio_stream = sd.InputStream(
                samplerate=self.porcupine.sample_rate,
                channels=1,
                dtype='int16',
                blocksize=self.porcupine.frame_length,
                callback=self._audio_callback
            )

            self.audio_stream.start()

            logger.info(f"Now listening for wake word: '{self.wake_word}'...")

        except Exception as e:
            logger.error(f"Failed to start wake word detection: {e}")
            raise

    def stop(self):
        """Stop listening for wake word"""
        try:
            self.is_listening = False

            if self.audio_stream:
                self.audio_stream.stop()
                self.audio_stream.close()
                self.audio_stream = None

            if self.porcupine:
                self.porcupine.delete()
                self.porcupine = None

            logger.info("Wake word detection stopped")

        except Exception as e:
            logger.error(f"Error stopping wake word detection: {e}")

    def _audio_callback(self, indata, frames, time, status):
        """
        Audio stream callback for wake word detection

        Args:
            indata: Input audio data
            frames: Number of frames
            time: Time info
            status: Stream status
        """
        if status:
            logger.warning(f"Audio stream status: {status}")

        if not self.is_listening:
            return

        try:
            # Get audio frame (flatten from 2D to 1D)
            audio_frame = indata.flatten()

            # Process with Porcupine
            keyword_index = self.porcupine.process(audio_frame)

            # Check if wake word detected
            if keyword_index >= 0:
                logger.info(f"🎤 Wake word '{self.wake_word}' detected!")

                # Call callback if provided
                if self.callback:
                    self.callback()

        except Exception as e:
            logger.error(f"Error in audio callback: {e}")

    def is_running(self):
        """Check if wake word detection is running"""
        return self.is_listening and self.audio_stream is not None
