"""
Text-to-Speech using OpenAI TTS API
"""
from openai import OpenAI
import io
import sounddevice as sd
import soundfile as sf
import numpy as np
from friday.config import Config
from friday.utils.logger import get_logger

logger = get_logger("tts")


class TextToSpeech:
    """Text-to-Speech handler using OpenAI TTS API"""

    def __init__(self):
        """Initialize TTS client"""
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.voice = Config.get("ai", "tts_voice", default="alloy")
        self.model = "tts-1"  # Use tts-1 for faster, lower latency (not tts-1-hd)

        logger.info(f"TTS initialized with voice: {self.voice}, model: {self.model}")

    def speak(self, text, play_audio=True):
        """
        Convert text to speech and optionally play it

        Args:
            text: Text to convert to speech
            play_audio: Whether to play the audio immediately

        Returns:
            bytes: Audio data
        """
        try:
            logger.info(f"Converting text to speech: '{text[:50]}...'")

            # Generate speech with streaming for lower latency
            response = self.client.audio.speech.create(
                model=self.model,
                voice=self.voice,
                input=text,
                response_format="mp3",  # MP3 is faster to generate
                speed=1.3  # Speed up by 30% (range: 0.25 to 4.0)
            )

            # Get audio bytes
            audio_bytes = response.content

            if play_audio:
                self.play_audio(audio_bytes)

            return audio_bytes

        except Exception as e:
            logger.error(f"TTS error: {e}")
            raise

    def play_audio(self, audio_bytes):
        """
        Play audio bytes in background thread for non-blocking playback

        Args:
            audio_bytes: Audio data in bytes (MP3 format)
        """
        try:
            # Convert bytes to file-like object
            audio_io = io.BytesIO(audio_bytes)

            # Read with soundfile (supports MP3)
            data, samplerate = sf.read(audio_io)

            logger.debug(f"Playing audio: {len(data)} samples at {samplerate}Hz")

            # Play audio without blocking (remove sd.wait())
            sd.play(data, samplerate)

            logger.info("Audio playback started (non-blocking)")

        except Exception as e:
            logger.error(f"Audio playback error: {e}")

    def save_audio(self, audio_bytes, file_path):
        """
        Save audio bytes to file

        Args:
            audio_bytes: Audio data
            file_path: Path to save file
        """
        try:
            with open(file_path, 'wb') as f:
                f.write(audio_bytes)

            logger.info(f"Audio saved to {file_path}")

        except Exception as e:
            logger.error(f"Failed to save audio: {e}")
            raise
