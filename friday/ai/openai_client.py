"""
OpenAI API client wrapper
"""
from openai import OpenAI
from openai import OpenAIError, RateLimitError, APIError
import time
from friday.config import Config
from friday.utils.logger import get_logger

logger = get_logger("openai_client")


class OpenAIClient:
    """Wrapper for OpenAI API with error handling and retry logic"""

    def __init__(self):
        """Initialize OpenAI client"""
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.get("ai", "model", default="gpt-4o")
        self.max_tokens = Config.get("ai", "max_tokens", default=500)
        self.temperature = Config.get("ai", "temperature", default=0.7)

        logger.info(f"OpenAI client initialized with model: {self.model}")

    def chat_completion(self, messages, max_retries=3):
        """
        Send chat completion request with retry logic

        Args:
            messages: List of message dicts for the API
            max_retries: Maximum number of retry attempts

        Returns:
            str: Assistant's response text
        """
        for attempt in range(max_retries):
            try:
                logger.debug(f"Sending chat completion request (attempt {attempt + 1})")

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature
                )

                assistant_message = response.choices[0].message.content
                logger.info(f"Received response: {len(assistant_message)} chars")

                return assistant_message

            except RateLimitError as e:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.warning(f"Rate limit hit, waiting {wait_time}s: {e}")
                if attempt < max_retries - 1:
                    time.sleep(wait_time)
                else:
                    raise

            except APIError as e:
                logger.error(f"API error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    raise

            except OpenAIError as e:
                logger.error(f"OpenAI error: {e}")
                raise

            except Exception as e:
                logger.error(f"Unexpected error in chat completion: {e}")
                raise

    def test_connection(self):
        """
        Test OpenAI API connection

        Returns:
            bool: True if connection successful
        """
        try:
            test_messages = [{"role": "user", "content": "Hello"}]
            response = self.chat_completion(test_messages)
            logger.info("OpenAI API connection test successful")
            return True

        except Exception as e:
            logger.error(f"OpenAI API connection test failed: {e}")
            return False
