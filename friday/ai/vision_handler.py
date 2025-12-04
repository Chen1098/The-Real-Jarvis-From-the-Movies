"""
Vision handler for encoding images for GPT-4o
"""
import base64
from io import BytesIO
from PIL import Image
from friday.utils.logger import get_logger

logger = get_logger("vision")


def encode_image_for_gpt4o(image, max_size=2048, quality=85):
    """
    Encode PIL Image for GPT-4o vision API

    Args:
        image: PIL Image object
        max_size: Maximum dimension size (default 2048px)
        quality: JPEG quality (1-100)

    Returns:
        str: Base64 encoded image with data URI prefix
    """
    try:
        # Make a copy to avoid modifying original
        img = image.copy()

        # Resize if too large (for token efficiency)
        if max(img.size) > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            logger.info(f"Resized image from {image.size} to {img.size}")

        # Convert to JPEG with compression
        buffered = BytesIO()

        # Convert RGBA to RGB if needed
        if img.mode == 'RGBA':
            # Create white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])  # Use alpha channel as mask
            img = background

        img.save(buffered, format="JPEG", quality=quality)

        # Get base64 string
        img_bytes = buffered.getvalue()
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')

        # Return with data URI prefix for OpenAI API
        data_uri = f"data:image/jpeg;base64,{img_base64}"

        logger.info(f"Encoded image: {len(img_base64)} chars, {len(img_bytes)} bytes")
        return data_uri

    except Exception as e:
        logger.error(f"Failed to encode image: {e}")
        raise


def encode_image_file(file_path, max_size=2048, quality=85):
    """
    Encode image file for GPT-4o vision API

    Args:
        file_path: Path to image file
        max_size: Maximum dimension size
        quality: JPEG quality

    Returns:
        str: Base64 encoded image with data URI prefix
    """
    try:
        img = Image.open(file_path)
        return encode_image_for_gpt4o(img, max_size, quality)
    except Exception as e:
        logger.error(f"Failed to encode image file {file_path}: {e}")
        raise
