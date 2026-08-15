"""
STT Engine - Speech-to-Text using faster-whisper (local, free, offline).

Uses faster-whisper for local speech recognition with no API costs.
"""

import asyncio
import logging
import os
import tempfile
import wave
import threading
from pathlib import Path

logger = logging.getLogger("salieri.stt")

try:
    import pyaudio
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False
    logger.warning("pyaudio not installed, microphone input disabled")

try:
    from faster_whisper import WhisperModel
    HAS_WHISPER = True
except ImportError as exc:
    HAS_WHISPER = False
    logger.warning("faster-whisper unavailable, speech recognition disabled: %s", exc)


class STTEngine:
    """Speech-to-text engine using faster-whisper locally."""

    def __init__(self):
        self.model_size = os.getenv("SALIERI_STT_MODEL", "small")
        self.model = None
        self.recording = False
        self.audio_frames = []
        self._pyaudio = None
        self._stream = None
        self._thread = None

        if HAS_WHISPER:
            self._load_model()

    def _load_model(self):
        """Load the Whisper model (lazy, on first use)."""
        try:
            device = "cpu"
            compute_type = "int8"

            # Try CUDA if available
            try:
                import torch
                if torch.cuda.is_available():
                    device = "cuda"
                    compute_type = "float16"
            except ImportError:
                pass

            self.model = WhisperModel(
                self.model_size,
                device=device,
                compute_type=compute_type,
            )
            logger.info(f"STT: Whisper model loaded ({self.model_size}, {device})")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            self.model = None

    def start_listening(self):
        """Start recording audio from microphone."""
        if not HAS_PYAUDIO:
            raise RuntimeError("pyaudio not installed")

        self._pyaudio = pyaudio.PyAudio()
        self.audio_frames = []
        self.recording = True

        self._stream = self._pyaudio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024,
        )

        def _record():
            while self.recording:
                try:
                    data = self._stream.read(1024, exception_on_overflow=False)
                    self.audio_frames.append(data)
                except Exception as e:
                    logger.error(f"Recording error: {e}")
                    break

        self._thread = threading.Thread(target=_record, daemon=True)
        self._thread.start()
        logger.info("STT: Started recording")

    async def stop_and_transcribe(self) -> str | None:
        """Stop recording and transcribe the audio."""
        if not self.recording:
            return None

        self.recording = False

        if self._thread:
            self._thread.join(timeout=2)

        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None

        if self._pyaudio:
            self._pyaudio.terminate()
            self._pyaudio = None

        if not self.audio_frames:
            logger.warning("STT: No audio recorded")
            return None

        # Save audio to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name

        try:
            with wave.open(temp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(16000)
                wf.writeframes(b"".join(self.audio_frames))

            # Transcribe
            text = await self._transcribe_file(temp_path)
            return text

        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    async def _transcribe_file(self, file_path: str) -> str | None:
        """Transcribe an audio file using Whisper."""
        if not self.model:
            logger.error("STT: Whisper model not loaded")
            return None

        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            segments, info = await loop.run_in_executor(
                None,
                lambda: self.model.transcribe(file_path, beam_size=5)
            )

            # Collect all segments
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())

            result = " ".join(text_parts).strip()
            logger.info(f"STT: Transcribed: {result}")
            return result if result else None

        except Exception as e:
            logger.error(f"STT transcription error: {e}")
            return None

    def cleanup(self):
        """Clean up resources."""
        self.recording = False
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        if self._pyaudio:
            self._pyaudio.terminate()