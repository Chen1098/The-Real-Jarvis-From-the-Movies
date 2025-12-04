"""
Audio recorder with silence detection
"""
import sounddevice as sd
import numpy as np
from pathlib import Path
from friday.config import Config
from friday.audio.audio_utils import detect_silence, save_audio_to_wav, audio_to_bytes
from friday.utils.logger import get_logger

logger = get_logger("audio_recorder")


class AudioRecorder:
    """Audio recorder with silence detection"""

    def __init__(self):
        """Initialize audio recorder"""
        self.sample_rate = Config.get("audio", "sample_rate", default=16000)
        self.channels = Config.get("audio", "channels", default=1)

        # Use environment variable for silence settings (overrides JSON config)
        self.silence_threshold = float(Config.SILENCE_THRESHOLD)
        self.silence_duration = float(Config.SILENCE_DURATION)
        self.max_duration = Config.get("audio", "max_recording_duration", default=30)

        # Calculate chunks needed for silence detection
        self.chunk_size = 1024
        self.silence_chunks_needed = int(
            (self.silence_duration * self.sample_rate) / self.chunk_size
        )
        self.max_chunks = int((self.max_duration * self.sample_rate) / self.chunk_size)

        self.is_recording = False
        self.audio_frames = []

        logger.info(f"AudioRecorder initialized: {self.sample_rate}Hz, {self.channels}ch")
        logger.info(f"Silence settings: threshold={self.silence_threshold}, duration={self.silence_duration}s")

    def record_with_silence_detection(self):
        """
        Record audio until silence detected

        Returns:
            numpy.ndarray: Recorded audio data
        """
        try:
            logger.info("Starting recording with silence detection...")
            logger.info(f"Using threshold={self.silence_threshold}, duration={self.silence_duration}s")

            self.audio_frames = []
            silence_counter = 0
            self.is_recording = True

            # Minimum recording time before checking for silence (3 seconds - longer!)
            min_recording_chunks = int((3.0 * self.sample_rate) / self.chunk_size)
            logger.info(f"Will record minimum {3.0}s before checking for silence")

            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype='float32',
                blocksize=self.chunk_size
            ) as stream:

                while self.is_recording:
                    # Read audio chunk
                    audio_chunk, overflowed = stream.read(self.chunk_size)

                    if overflowed:
                        logger.warning("Audio buffer overflow")

                    # Store audio
                    self.audio_frames.append(audio_chunk.copy())

                    # Only start checking for silence after minimum recording time
                    if len(self.audio_frames) > min_recording_chunks:
                        # Check for silence
                        is_silent = detect_silence(audio_chunk, self.silence_threshold)

                        if is_silent:
                            silence_counter += 1
                        else:
                            silence_counter = 0  # Reset on sound

                        # Stop if enough silence detected
                        if silence_counter >= self.silence_chunks_needed:
                            logger.info(f"Silence detected for {self.silence_duration}s, stopping...")
                            break
                    else:
                        # Still in minimum recording period
                        current_time = len(self.audio_frames) * self.chunk_size / self.sample_rate
                        if int(current_time * 10) % 10 == 0:  # Log every 0.1s
                            logger.debug(f"Recording... {current_time:.1f}s (min 3.0s)")

                    # Safety: stop if max duration reached
                    if len(self.audio_frames) >= self.max_chunks:
                        logger.warning(f"Max duration {self.max_duration}s reached, stopping...")
                        break

            # Combine all frames
            audio_data = np.concatenate(self.audio_frames)

            duration = len(audio_data) / self.sample_rate
            logger.info(f"Recording complete: {duration:.2f}s, {len(audio_data)} samples")

            return audio_data

        except Exception as e:
            logger.error(f"Recording error: {e}")
            raise

        finally:
            self.is_recording = False

    def record_fixed_duration(self, duration=5.0):
        """
        Record audio for a fixed duration

        Args:
            duration: Recording duration in seconds

        Returns:
            numpy.ndarray: Recorded audio data
        """
        try:
            logger.info(f"Recording for {duration}s...")

            audio_data = sd.rec(
                int(duration * self.sample_rate),
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype='float32'
            )

            sd.wait()  # Wait for recording to complete

            logger.info(f"Fixed duration recording complete")

            return audio_data.flatten()

        except Exception as e:
            logger.error(f"Recording error: {e}")
            raise

    def stop_recording(self):
        """Stop ongoing recording"""
        self.is_recording = False
        logger.info("Recording stopped manually")

    def save_recording(self, audio_data, file_path):
        """
        Save recorded audio to file

        Args:
            audio_data: Numpy array of audio data
            file_path: Path to save file
        """
        save_audio_to_wav(audio_data, file_path, self.sample_rate, self.channels)

    def recording_to_bytes(self, audio_data):
        """
        Convert recording to WAV bytes

        Args:
            audio_data: Numpy array of audio data

        Returns:
            bytes: WAV file bytes
        """
        return audio_to_bytes(audio_data, self.sample_rate, self.channels)

    def test_microphone(self):
        """
        Test microphone access

        Returns:
            bool: True if microphone accessible
        """
        try:
            logger.info("Testing microphone...")

            # Try to record 0.5 seconds
            test_audio = sd.rec(
                int(0.5 * self.sample_rate),
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype='float32'
            )
            sd.wait()

            logger.info("Microphone test successful")
            return True

        except Exception as e:
            logger.error(f"Microphone test failed: {e}")
            return False
