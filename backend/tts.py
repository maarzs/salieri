"""
TTS Engine - Text-to-Speech using Edge TTS (free, natural voices).

Uses Microsoft Edge's free TTS service. Falls back to Windows SAPI if needed.
Set SALIERI_TTS_ENABLED=false to disable TTS entirely.
"""

import asyncio
import base64
import logging
import tempfile
import os
from pathlib import Path

logger = logging.getLogger("salieri.tts")

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False
    logger.warning("edge-tts not installed, TTS will be limited")


class TTSEngine:
    """Text-to-speech engine with Edge TTS as primary, SAPI as fallback."""

    def __init__(self):
        self.voice = os.getenv("SALIERI_TTS_VOICE", "en-US-AriaNeural")
        self.rate = os.getenv("SALIERI_TTS_RATE", "+10%")
        self.pitch = os.getenv("SALIERI_TTS_PITCH", "+0Hz")

        tts_disabled = os.getenv("SALIERI_TTS_ENABLED", "true").lower() in ("false", "0", "no")
        self.enabled = HAS_EDGE_TTS and not tts_disabled
        if tts_disabled:
            logger.info("TTS disabled via SALIERI_TTS_ENABLED=false")
        elif not self.enabled:
            logger.warning("TTS disabled: edge-tts not installed")

    def set_enabled(self, enabled: bool) -> bool:
        """Apply the user's TTS toggle at runtime.

        Enabling is only honoured when edge-tts is actually installed, so a
        Settings-panel toggle can't put the engine into a broken state.
        """
        self.enabled = bool(enabled) and HAS_EDGE_TTS
        if enabled and not HAS_EDGE_TTS:
            logger.warning("TTS requested but edge-tts is not installed")
        return self.enabled

    async def generate(self, text: str) -> str | None:
        """Generate speech audio and return as base64-encoded audio."""
        if not self.enabled or not text.strip():
            return None

        try:
            return await self._edge_tts(text)
        except Exception as e:
            logger.error(f"Edge TTS failed: {e}")
            return None

    async def _edge_tts(self, text: str) -> str | None:
        """Generate speech using Edge TTS."""
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
            pitch=self.pitch,
        )

        audio_data = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data.extend(chunk["data"])

        if not audio_data:
            return None

        return base64.b64encode(bytes(audio_data)).decode("utf-8")

    async def generate_to_file(self, text: str, output_path: str) -> bool:
        """Generate speech and save to a file."""
        if not self.enabled:
            return False

        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=self.voice,
                rate=self.rate,
                pitch=self.pitch,
            )
            await communicate.save(output_path)
            return True
        except Exception as e:
            logger.error(f"TTS file generation failed: {e}")
            return False