"""
Jarvis AI Assistant - Launcher Script
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from friday.utils.logger import get_logger
from friday.config import Config

logger = get_logger("launcher")


def main():
    """Main entry point"""
    logger.info("Starting Jarvis AI Assistant...")

    # Validate configuration
    errors = Config.validate()
    if errors:
        logger.error("Configuration errors found:")
        for error in errors:
            logger.error(f"  - {error}")
        logger.error("\nPlease check your .env file and ensure all API keys are set correctly.")
        logger.error("Copy .env.example to .env and add your API keys.")
        return 1

    # Import and run main application
    try:
        from friday.main import FridayApp
        app = FridayApp()
        app.run()
    except KeyboardInterrupt:
        logger.info("\nShutting down Jarvis...")
        return 0
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
