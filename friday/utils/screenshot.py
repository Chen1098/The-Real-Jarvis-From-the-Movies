"""
Screenshot capture utility
"""
import mss
import mss.tools
from PIL import Image
from io import BytesIO
from friday.utils.logger import get_logger

logger = get_logger("screenshot")


def capture_screenshot():
    """
    Capture screenshot of the primary monitor

    Returns:
        PIL.Image: Screenshot as PIL Image object
    """
    try:
        with mss.mss() as sct:
            # Capture primary monitor
            monitor = sct.monitors[1]  # 0 is all monitors, 1 is primary
            screenshot = sct.grab(monitor)

            # Convert to PIL Image
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

            logger.info(f"Screenshot captured: {img.size[0]}x{img.size[1]}")
            return img

    except Exception as e:
        logger.error(f"Failed to capture screenshot: {e}")
        raise


def capture_screenshot_to_bytes(format="PNG"):
    """
    Capture screenshot and return as bytes

    Args:
        format: Image format (PNG, JPEG, etc.)

    Returns:
        bytes: Screenshot as bytes
    """
    img = capture_screenshot()

    # Convert to bytes
    buffer = BytesIO()
    img.save(buffer, format=format)
    buffer.seek(0)

    return buffer.getvalue()
