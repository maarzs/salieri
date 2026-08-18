"""
Salieri AI - Desktop AI Companion Backend
Inspired by the Amadeus system from Steins;Gate 0

Architecture:
- WebSocket server for real-time communication with Electron frontend
- Ollama LLM for local, free AI conversation
- faster-whisper for local speech-to-text
- Edge TTS for free, natural text-to-speech
- SQLite + vector embeddings for persistent memory
- Personality system based on character cards
"""

import asyncio
import json
import base64
import io
import wave
import uuid
import logging
import os
import multiprocessing
from datetime import datetime
from pathlib import Path
from typing import Optional

# Required for frozen (PyInstaller) builds on Windows: sentence_transformers /
# joblib spawn multiprocessing workers, which re-executes the entrypoint.
multiprocessing.freeze_support()

# Auto-load .env file.
# When frozen with PyInstaller, __file__ points inside the temp extraction dir,
# so also check next to the executable and in the current working directory.
def _candidate_env_paths():
    import sys
    paths = [Path(__file__).parent / ".env", Path.cwd() / ".env"]
    if getattr(sys, "frozen", False):  # PyInstaller bundle
        paths.insert(0, Path(sys.executable).parent / ".env")
    return paths

try:
    from dotenv import load_dotenv
    for env_path in _candidate_env_paths():
        if env_path.exists():
            load_dotenv(env_path)
            logging.info(f"Loaded .env from {env_path}")
            break
except ImportError:
    pass  # python-dotenv not installed, use system env vars

import websockets
from websockets.asyncio.server import serve

from llm import LLMEngine
from memory import MemoryStore
from personality import PersonalityEngine
from settings import SettingsStore
from tts import TTSEngine
from stt import STTEngine

from tools.reminders import ReminderStore, parse_time, parse_reminder_intent, reminder_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("salieri-backend")

BACKEND_DIR = Path(__file__).parent


def _data_dir() -> Path:
    """Writable directory for persistent data (settings + memory DB).

    Dev runs write next to the source. Packaged runs must NOT: the backend is
    a sidecar under ``<installDir>/resources/backend`` — in Program Files that
    is not user-writable (and for the portable build it's a temp dir that is
    wiped between launches). Detect packaged mode by an embedded-Python
    sibling (``python/python.exe`` next to the backend source) or PyInstaller's
    ``sys.frozen``, and store data under the user's app-data folder instead.
    """
    import sys
    packaged = (
        getattr(sys, "frozen", False)  # PyInstaller bundle
        or (BACKEND_DIR / "python" / "python.exe").exists()  # embedded sidecar
    )
    if packaged:
        base = Path(os.getenv("APPDATA", Path.home() / "AppData/Roaming"))
        d = base / "Salieri"
        d.mkdir(parents=True, exist_ok=True)
        (d / "memory").mkdir(parents=True, exist_ok=True)
        return d
    return BACKEND_DIR


DATA_DIR = _data_dir()

# Runtime-installed modules (Settings -> Modules) are pip-installed with
# --target into this directory (NOT the sidecar's site-packages), because the
# zip/portable release folder may be read-only. Prepending it to sys.path lets
# the backend import them. Must happen before llm/memory/tts/stt are imported.
MODULES_DIR = DATA_DIR / "py_modules"
MODULES_DIR.mkdir(parents=True, exist_ok=True)
import sys as _sys
if str(MODULES_DIR) not in _sys.path:
    _sys.path.insert(0, str(MODULES_DIR))

# Shared across connections: a new SalieriBackend is constructed per WebSocket
# client, so the settings store must live at module scope to stay consistent.
SETTINGS = SettingsStore(DATA_DIR / "settings.json")


class SalieriBackend:
    """Main backend orchestrator for Salieri AI."""

    def __init__(self):
        self.settings = SETTINGS
        self.llm = LLMEngine(self.settings.effective())
        self.memory = MemoryStore(DATA_DIR / "memory" / "salieri.db")
        self.reminders = ReminderStore(DATA_DIR / "memory" / "salieri.db")
        self.personality = PersonalityEngine()
        self.tts = TTSEngine()
        self.stt = STTEngine()
        self.active_voice_call = False
        self.websocket = None
        self._scheduler_task = None
        # Apply the persisted voice/personality settings from the last session
        # so the first chat already reflects what the user configured.
        self._apply_user_settings()

    def _apply_user_settings(self):
        """Push voice + personality settings into the engines.

        Idempotent — called at startup and again after every successful
        settings update. Failures here must never break chat, so this only
        touches presentation (voice, prompt style), never the LLM client.
        """
        eff = self.settings.effective()
        self.personality.apply_settings(eff)

        # Character variant owns the default voice/rate — the persona
        # determines how it sounds. TTS override from the Settings panel
        # is only applied here when the character is NOT being switched
        # (handled in the update_settings handler).
        self.tts.set_voice(self.personality.default_voice, self.personality.default_rate)

    async def handle_message(self, websocket, data: dict):
        """Route incoming messages from the frontend."""
        msg_type = data.get("type", "")

        if msg_type == "chat":
            await self.handle_chat(websocket, data.get("content", ""))

        elif msg_type == "stt_start":
            await self.handle_stt_start(websocket)

        elif msg_type == "stt_stop":
            await self.handle_stt_stop(websocket)

        elif msg_type == "voice_call_start":
            self.active_voice_call = True
            await self.send_json(websocket, {"type": "status", "status": "connected"})

        elif msg_type == "voice_call_end":
            self.active_voice_call = False
            await self.send_json(websocket, {"type": "status", "status": "idle"})

        elif msg_type == "get_settings":
            await self.send_json(websocket, {
                "type": "settings",
                "settings": self.settings.public(),
            })

        elif msg_type == "load_history":
            await self.handle_load_history(websocket, data.get("limit", 100))

        elif msg_type == "clear_history":
            await self.handle_clear_history(websocket)

        elif msg_type == "set_reminder":
            await self.handle_set_reminder(websocket, data)

        elif msg_type == "list_reminders":
            await self.handle_list_reminders(websocket)

        elif msg_type == "cancel_reminder":
            await self.handle_cancel_reminder(websocket, data.get("query", ""))

        elif msg_type == "update_settings":
            await self.handle_update_settings(websocket, data.get("settings", {}))

        elif msg_type == "list_models":
            await self.handle_list_models(websocket)

        elif msg_type == "test_connection":
            await self.handle_test_connection(websocket)

        elif msg_type == "ping":
            await self.send_json(websocket, {"type": "pong"})

        else:
            await self.send_json(websocket, {
                "type": "error",
                "message": f"Unknown message type: {msg_type}"
            })

    async def handle_chat(self, websocket, content: str):
        """Process a chat message through the full pipeline."""
        try:
            # Check for reminder intent before the full LLM pipeline
            reminder_intent = parse_reminder_intent(content)
            if reminder_intent:
                fire_at = parse_time(reminder_intent["fire_at"])
                reminder_id = self.reminders.add_reminder(
                    reminder_intent["message"], fire_at, reminder_intent.get("recurring")
                )
                await self.send_json(websocket, {
                    "type": "reminder_set",
                    "id": reminder_id,
                    "message": reminder_intent["message"],
                    "fire_at": fire_at,
                    "recurring": reminder_intent.get("recurring"),
                })
                await self.send_json(websocket, {
                    "type": "chat_response",
                    "content": f"I've set a reminder: '{reminder_intent['message']}' at {reminder_intent['fire_at']}.",
                    "emotion": "neutral",
                })
                return

            # Extract personal facts (name, age, occupation, ...) from the
            # user's message and persist them. Runs on a worker thread so a
            # slow/blocked DB never stalls the websocket loop. Extract BEFORE
            # building the prompt so this very message can benefit.
            try:
                await asyncio.to_thread(self.memory.extract_facts, content)
            except Exception as fact_err:
                logger.warning(f"Fact extraction failed (non-critical): {fact_err}")

            # Retrieve relevant memories and recent context
            memories = self.memory.search(content, limit=5)
            recent_context = self.memory.get_recent_context(count=10)
            profile = self.memory.profile_summary()

            # Build the message array with personality, memory, and context
            messages = self.personality.build_messages(
                content, memories, recent_context, user_profile=profile
            )

            # Generate response from LLM
            response_text = ""
            emotion = "neutral"

            async for chunk in self.llm.chat_stream(messages):
                response_text += chunk
                await self.send_json(websocket, {
                    "type": "chat_stream",
                    "content": chunk,
                    "streamId": "current",
                })

            # Signal end of stream
            await self.send_json(websocket, {"type": "stream_end"})

            # Detect emotion from response
            emotion = self.personality.detect_emotion(response_text)

            # Send final response with emotion
            await self.send_json(websocket, {
                "type": "chat_response",
                "content": response_text,
                "emotion": emotion,
            })

            # Store conversation in memory
            self.memory.store_conversation(content, response_text)

            # Generate TTS audio. Non-critical: a hung edge-tts call (flaky
            # network) must never block the chat loop, so it's bounded by a
            # timeout. `tts_done` is ALWAYS sent — success, failure, or TTS
            # disabled — so clients have a deterministic end-of-turn marker.
            try:
                audio_base64 = await asyncio.wait_for(
                    self.tts.generate(response_text), timeout=30
                )
                if audio_base64:
                    await self.send_json(websocket, {
                        "type": "tts_audio",
                        "audio": audio_base64,
                    })
            except asyncio.TimeoutError:
                logger.warning("TTS timed out after 30s (non-critical), skipping audio")
            except Exception as tts_err:
                logger.warning(f"TTS failed (non-critical): {tts_err}")
            finally:
                await self.send_json(websocket, {"type": "tts_done"})

        except Exception as e:
            logger.error(f"Chat error: {e}")
            await self.send_json(websocket, {
                "type": "error",
                "message": f"Failed to generate response: {str(e)}"
            })

    async def handle_load_history(self, websocket, limit: int = 100):
        """Restore prior exchanges so the UI isn't blank on every launch.

        Runs on a worker thread: sqlite reads can block when the DB is large,
        and we never want to stall the websocket loop.
        """
        try:
            limit = max(1, min(int(limit or 100), 1000))
        except (TypeError, ValueError):
            limit = 100
        try:
            history = await asyncio.to_thread(self.memory.get_history, limit)
            await self.send_json(websocket, {"type": "history", "history": history})
        except Exception as e:
            logger.error(f"History load failed: {e}")
            await self.send_json(websocket, {
                "type": "error",
                "message": f"Failed to load history: {str(e)}",
            })

    async def handle_clear_history(self, websocket):
        """Wipe stored exchanges and tell the UI to clear its transcript."""
        try:
            removed = await asyncio.to_thread(self.memory.clear_conversations)
            await self.send_json(websocket, {"type": "history_cleared", "removed": removed})
            logger.info(f"Cleared {removed} conversation exchanges")
        except Exception as e:
            logger.error(f"History clear failed: {e}")
            await self.send_json(websocket, {
                "type": "error",
                "message": f"Failed to clear history: {str(e)}",
            })

    async def handle_set_reminder(self, websocket, data: dict):
        """Create a new reminder."""
        message = data.get("message", "")
        fire_at_str = data.get("fire_at", "")
        recurring = data.get("recurring")

        try:
            fire_at = parse_time(fire_at_str)
            if fire_at is None:
                await self.send_json(websocket, {
                    "type": "error",
                    "message": "Could not parse time. Use formats like 'in 5 minutes', 'at 18:00', 'tomorrow at 19:00', or ISO format.",
                })
                return

            reminder_id = self.reminders.add_reminder(message, fire_at, recurring)
            await self.send_json(websocket, {
                "type": "reminder_set",
                "id": reminder_id,
                "message": message,
                "fire_at": fire_at,
                "recurring": recurring,
            })
            logger.info(f"Reminder set: {message} at {fire_at}")
        except Exception as e:
            logger.error(f"Failed to set reminder: {e}")
            await self.send_json(websocket, {
                "type": "error",
                "message": f"Failed to set reminder: {str(e)}",
            })

    async def handle_list_reminders(self, websocket):
        """List all pending reminders."""
        try:
            reminders = self.reminders.list_reminders()
            await self.send_json(websocket, {
                "type": "reminders_list",
                "reminders": reminders,
            })
        except Exception as e:
            logger.error(f"Failed to list reminders: {e}")
            await self.send_json(websocket, {
                "type": "error",
                "message": f"Failed to list reminders: {str(e)}",
            })

    async def handle_cancel_reminder(self, websocket, query: str):
        """Cancel a reminder by id or message."""
        try:
            removed = self.reminders.cancel_reminder(query)
            if removed == 0:
                await self.send_json(websocket, {
                    "type": "error",
                    "message": "No reminder found matching query.",
                })
            else:
                await self.send_json(websocket, {
                    "type": "reminder_cancelled",
                    "removed": removed,
                })
        except Exception as e:
            logger.error(f"Failed to cancel reminder: {e}")
            await self.send_json(websocket, {
                "type": "error",
                "message": f"Failed to cancel reminder: {str(e)}",
            })

    async def handle_update_settings(self, websocket, patch: dict):
        """Persist new settings and rebuild the LLM client in place.

        On failure the previous working client is restored so a bad base URL or
        key can't leave the app unable to chat.
        """
        previous = self.llm
        try:
            public = self.settings.update(patch)
            self.llm = LLMEngine(self.settings.effective())
            # Respect the user's toggle, but never enable TTS when the
            # edge-tts package is missing.
            self.tts.set_enabled(self.settings.effective()["tts_enabled"])
            # Apply personality (character switch, style notes, etc.).
            self.personality.apply_settings(self.settings.effective())
            # Voice: switching character owns the voice — the persona's
            # default wins. A manual tts_voice change (no character switch in
            # this patch) is honored as an explicit user override.
            if "mascot_character" in patch and patch.get("mascot_character"):
                self.tts.set_voice(
                    self.personality.default_voice,
                    self.personality.default_rate,
                )
            elif patch.get("tts_voice"):
                self.tts.set_voice(patch["tts_voice"], patch.get("tts_rate") or "")
            else:
                self.tts.set_voice(
                    self.personality.default_voice,
                    self.personality.default_rate,
                )
            await self.send_json(websocket, {
                "type": "settings",
                "settings": public,
                "saved": True,
            })
            logger.info(
                f"Settings updated: provider={self.llm.provider} "
                f"model={self.llm.model} base_url={self.llm.base_url}"
            )
        except Exception as e:
            self.llm = previous
            logger.error(f"Settings update failed: {e}")
            await self.send_json(websocket, {
                "type": "error",
                "message": f"Failed to apply settings: {str(e)}",
            })

    async def handle_list_models(self, websocket):
        """Send the model list from the currently configured endpoint."""
        models = await self.llm.list_models()
        await self.send_json(websocket, {"type": "models", "models": models})

    async def handle_test_connection(self, websocket):
        """Round-trip a tiny prompt so the user can validate their config."""
        try:
            reply = await self.llm.chat(
                [{"role": "user", "content": "Reply with the single word: OK"}]
            )
            await self.send_json(websocket, {
                "type": "test_result",
                "ok": True,
                "message": f"{self.llm.provider}/{self.llm.model} replied: "
                           f"{reply.strip()[:60]}",
            })
        except Exception as e:
            await self.send_json(websocket, {
                "type": "test_result",
                "ok": False,
                "message": str(e)[:300],
            })

    async def handle_stt_start(self, websocket):
        """Start listening for speech."""
        try:
            self.stt.start_listening()
            await self.send_json(websocket, {"type": "status", "status": "listening"})
        except Exception as e:
            logger.error(f"STT start error: {e}")
            await self.send_json(websocket, {
                "type": "error",
                "message": f"Failed to start microphone: {str(e)}"
            })

    async def handle_stt_stop(self, websocket):
        """Stop listening and transcribe."""
        try:
            text = await self.stt.stop_and_transcribe()
            if text:
                await self.send_json(websocket, {
                    "type": "stt_result",
                    "content": text,
                })
                # Auto-send the transcribed text as a chat message
                await self.handle_chat(websocket, text)
        except Exception as e:
            logger.error(f"STT stop error: {e}")
            await self.send_json(websocket, {
                "type": "error",
                "message": f"Speech recognition failed: {str(e)}"
            })

    async def send_json(self, websocket, data: dict):
        """Send JSON to the frontend."""
        try:
            await websocket.send(json.dumps(data))
        except websockets.exceptions.ConnectionClosed:
            pass


async def _fire_reminder(backend: "SalieriBackend", reminder: dict):
    """Callback invoked when a reminder is due: broadcast to websocket and trigger TTS."""
    reminder_obj = {
        "id": reminder["id"],
        "message": reminder["message"],
        "time": reminder["fire_at"],
        "fired_at": int(datetime.now().timestamp()),
    }
    if backend.websocket:
        await backend.send_json(backend.websocket, {
            "type": "reminder_fired",
            "reminder": reminder_obj,
        })
        try:
            audio_base64 = await asyncio.wait_for(
                backend.tts.generate(reminder["message"]), timeout=30
            )
            if audio_base64:
                await backend.send_json(backend.websocket, {
                    "type": "tts_audio",
                    "audio": audio_base64,
                })
        except asyncio.TimeoutError:
            pass
        finally:
            await backend.send_json(backend.websocket, {"type": "tts_done"})


async def handler(websocket):
    """Handle a new WebSocket connection."""
    backend = SalieriBackend()
    backend.websocket = websocket
    logger.info("Client connected")

    backend._scheduler_task = asyncio.create_task(
        reminder_scheduler(backend.reminders, lambda r: _fire_reminder(backend, r))
    )

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                await backend.handle_message(websocket, data)
            except json.JSONDecodeError:
                await backend.send_json(websocket, {
                    "type": "error",
                    "message": "Invalid JSON"
                })
    except websockets.exceptions.ConnectionClosed:
        logger.info("Client disconnected")
    finally:
        if backend._scheduler_task:
            backend._scheduler_task.cancel()
            try:
                await backend._scheduler_task
            except asyncio.CancelledError:
                pass
        backend.stt.cleanup()


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Salieri AI backend")
    parser.add_argument("--port", type=int, default=9876, help="WebSocket port")
    args, _unknown = parser.parse_known_args()

    port = args.port
    logger.info(f"Salieri AI backend starting on ws://localhost:{port}")
    async with serve(handler, "localhost", port):
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    asyncio.run(main())