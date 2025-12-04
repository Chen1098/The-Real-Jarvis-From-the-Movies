"""
Speech-to-Text using OpenAI Whisper API
"""
from openai import OpenAI
from pathlib import Path
from friday.config import Config
from friday.utils.logger import get_logger

logger = get_logger("stt")


class SpeechToText:
    """Speech-to-Text handler using OpenAI Whisper API"""

    def __init__(self):
        """Initialize STT client"""
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = "whisper-1"

        logger.info("STT initialized with Whisper API")

    def transcribe_file(self, audio_file_path):
        """
        Transcribe audio file to text

        Args:
            audio_file_path: Path to audio file (wav, mp3, etc.)

        Returns:
            str: Transcribed text
        """
        try:
            logger.info(f"Transcribing audio file: {audio_file_path}")

            with open(audio_file_path, 'rb') as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file
                )

            text = transcript.text
            logger.info(f"Transcription: '{text}'")

            return text

        except Exception as e:
            logger.error(f"STT error: {e}")
            raise

    def transcribe_bytes(self, audio_bytes, filename="audio.wav"):
        """
        Transcribe audio from bytes

        Args:
            audio_bytes: Audio data as bytes
            filename: Filename hint for the API

        Returns:
            str: Transcribed text
        """
        try:
            logger.info("Transcribing audio from bytes")

            # Create a file-like object from bytes
            from io import BytesIO
            audio_file = BytesIO(audio_bytes)
            audio_file.name = filename

            transcript = self.client.audio.transcriptions.create(
                model=self.model,
                file=audio_file
            )

            text = transcript.text
            logger.info(f"Transcription: '{text}'")

            return text

        except Exception as e:
            logger.error(f"STT error: {e}")
            raise
