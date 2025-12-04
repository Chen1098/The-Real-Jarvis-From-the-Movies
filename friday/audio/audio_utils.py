"""
Audio utilities and format conversions
"""
import numpy as np
import wave
from friday.config import Config
from friday.utils.logger import get_logger

logger = get_logger("audio_utils")


def detect_silence(audio_chunk, threshold=None):
    """
    Check if audio chunk is below silence threshold

    Args:
        audio_chunk: Numpy array of audio data
        threshold: Silence threshold (uses config default if None)

    Returns:
        bool: True if silent, False if sound detected
    """
    if threshold is None:
        threshold = Config.get("audio", "silence_threshold", default=0.02)

    # Calculate RMS (root mean square) of audio chunk
    rms = np.sqrt(np.mean(audio_chunk ** 2))

    return rms < threshold


def save_audio_to_wav(audio_data, file_path, sample_rate=16000, channels=1):
    """
    Save audio data to WAV file

    Args:
        audio_data: Numpy array or list of audio frames
        file_path: Path to save WAV file
        sample_rate: Sample rate in Hz
        channels: Number of audio channels
    """
    try:
        # Convert list of frames to single numpy array if needed
        if isinstance(audio_data, list):
            audio_data = np.concatenate(audio_data)

        # Ensure audio is in correct format
        if audio_data.dtype != np.int16:
            # Convert float to int16
            audio_data = (audio_data * 32767).astype(np.int16)

        # Write WAV file
        with wave.open(str(file_path), 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)  # 2 bytes for int16
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data.tobytes())

        logger.info(f"Audio saved to {file_path}")

    except Exception as e:
        logger.error(f"Failed to save audio: {e}")
        raise


def audio_to_bytes(audio_data, sample_rate=16000, channels=1):
    """
    Convert audio data to WAV bytes

    Args:
        audio_data: Numpy array of audio data
        sample_rate: Sample rate in Hz
        channels: Number of channels

    Returns:
        bytes: WAV file as bytes
    """
    import io

    # Ensure audio is in correct format
    if audio_data.dtype != np.int16:
        audio_data = (audio_data * 32767).astype(np.int16)

    # Create in-memory bytes buffer
    buffer = io.BytesIO()

    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data.tobytes())

    buffer.seek(0)
    return buffer.getvalue()
