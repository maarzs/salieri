"""Shared pytest fixtures for the Salieri backend test suite.

The backend lives one directory above tests/, so make it importable first.
"""

import json
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from settings import SettingsStore  # noqa: E402


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeWebSocket:
    """Minimal stand-in for a websockets connection.

    Records every outgoing frame (parsed back to dicts) and can replay a
    scripted list of incoming raw messages for handler()-level tests.
    """

    def __init__(self, incoming=None):
        self.sent = []
        self.incoming = list(incoming or [])

    async def send(self, payload):
        self.sent.append(json.loads(payload))

    def frames(self, type_):
        return [f for f in self.sent if f.get("type") == type_]

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.incoming:
            raise StopAsyncIteration
        return self.incoming.pop(0)


class FakeSTT:
    """STT stand-in: no microphone, no whisper model download in tests."""

    def __init__(self):
        self.cleaned_up = False

    def start_listening(self):
        raise RuntimeError("no microphone in tests")

    async def stop_and_transcribe(self):
        return None

    def cleanup(self):
        self.cleaned_up = True


class FakeLLM:
    """LLM stand-in with canned streaming/non-streaming replies."""

    provider = "fake"
    model = "fake-model"
    base_url = ""

    def __init__(self, chunks=("Hello ", "there!"), reply="OK", fail_chat=None):
        self.chunks = chunks
        self.reply = reply
        self.fail_chat = fail_chat
        self.messages_seen = None

    async def chat_stream(self, messages):
        self.messages_seen = messages
        for chunk in self.chunks:
            yield chunk

    async def chat(self, messages):
        self.messages_seen = messages
        if self.fail_chat:
            raise self.fail_chat
        return self.reply

    async def list_models(self):
        return ["fake-model-1", "fake-model-2"]


class FakeTTS:
    """TTS stand-in mirroring the real engine's runtime configuration API."""

    def __init__(self, audio=None):
        self.audio = audio
        self.enabled = True
        self.voice = "en-US-AriaNeural"
        self.rate = "+10%"
        self.generate_calls = []

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        return self.enabled

    def set_voice(self, voice="", rate=""):
        if voice and voice.strip():
            self.voice = voice.strip()
        if rate and rate.strip():
            self.rate = rate.strip()

    async def generate(self, text):
        self.generate_calls.append(text)
        return self.audio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_settings(tmp_path, monkeypatch):
    """An isolated settings store that never touches the real settings.json.

    server.py loads backend/.env into os.environ at import time, and
    SettingsStore.get() falls back to those env vars — clear the known keys
    so tests see pure defaults regardless of the developer's machine.
    """
    for var in (
        "SALIERI_LLM_PROVIDER", "SALIERI_LLM_MODEL", "OPENAI_BASE_URL",
        "OPENAI_API_KEY", "OLLAMA_HOST", "SALIERI_TTS_ENABLED",
        "SALIERI_TTS_VOICE", "SALIERI_TTS_RATE", "SALIERI_PERSONALITY_NAME",
        "SALIERI_PERSONALITY_STYLE", "SALIERI_RESPONSE_LENGTH",
    ):
        monkeypatch.delenv(var, raising=False)
    return SettingsStore(tmp_path / "settings.json")


@pytest.fixture
def server_globals(tmp_path, monkeypatch, tmp_settings):
    """Point server.py's module-level globals at the temp directory.

    Must happen BEFORE SalieriBackend() is constructed: its __init__ reads
    DATA_DIR (memory DB path) and SETTINGS, and would otherwise touch the
    developer's real database and settings file.
    """
    import server as server_mod

    (tmp_path / "memory").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(server_mod, "DATA_DIR", tmp_path)
    monkeypatch.setattr(server_mod, "SETTINGS", tmp_settings)
    monkeypatch.setattr(server_mod, "STTEngine", FakeSTT)
    return server_mod


@pytest.fixture
def backend(server_globals):
    """A fully wired SalieriBackend backed by temp storage and fake engines."""
    return server_globals.SalieriBackend()


@pytest.fixture
def memory_store(tmp_path):
    """An isolated MemoryStore forced onto the keyword-search path.

    The embedding model is deliberately NOT loaded: tests must run offline
    and must never trigger a model download.
    """
    from memory import MemoryStore

    db_dir = tmp_path / "memory"
    db_dir.mkdir(parents=True, exist_ok=True)
    store = MemoryStore(str(db_dir / "test.db"))
    store._embedder_loaded = True
    store.embedder = None
    yield store
    store.close()
