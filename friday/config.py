"""
Configuration management for Friday AI Assistant
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)


class Config:
    """Application configuration"""

    # Project paths
    BASE_DIR = Path(__file__).parent.parent
    CONFIG_DIR = BASE_DIR / "config"
    LOGS_DIR = BASE_DIR / "logs"
    ASSETS_DIR = BASE_DIR / "assets"

    # API Keys
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    PORCUPINE_ACCESS_KEY = os.getenv("PORCUPINE_ACCESS_KEY", "")

    # Audio settings
    WAKE_WORD = os.getenv("WAKE_WORD", "jarvis")
    SILENCE_THRESHOLD = float(os.getenv("SILENCE_THRESHOLD", "0.02"))
    SILENCE_DURATION = float(os.getenv("SILENCE_DURATION", "1.5"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # Default settings from JSON
    _settings = {}

    @classmethod
    def load_settings(cls):
        """Load settings from JSON file"""
        settings_file = cls.CONFIG_DIR / "settings.json"
        if settings_file.exists():
            with open(settings_file, 'r') as f:
                cls._settings = json.load(f)
        else:
            # Default settings if file doesn't exist
            cls._settings = {
                "audio": {
                    "sample_rate": 16000,
                    "channels": 1,
                    "silence_threshold": 0.02,
                    "silence_duration": 1.5,
                    "max_recording_duration": 30
                },
                "ai": {
                    "model": "gpt-4o",
                    "max_tokens": 500,
                    "temperature": 0.7,
                    "tts_voice": "alloy"
                },
                "gui": {
                    "window_width": 800,
                    "window_height": 600,
                    "theme": "dark"
                }
            }

    @classmethod
    def get(cls, *keys, default=None):
        """Get nested configuration value"""
        if not cls._settings:
            cls.load_settings()

        value = cls._settings
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, default)
            else:
                return default
        return value

    @classmethod
    def validate(cls):
        """Validate required configuration"""
        errors = []

        if not cls.OPENAI_API_KEY or not cls.OPENAI_API_KEY.startswith("sk-"):
            errors.append("Invalid or missing OPENAI_API_KEY")

        if not cls.PORCUPINE_ACCESS_KEY:
            errors.append("Missing PORCUPINE_ACCESS_KEY")

        return errors


# Load settings on import
Config.load_settings()
