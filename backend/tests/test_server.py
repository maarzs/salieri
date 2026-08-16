"""Tests for server.py — WebSocket handler routing and the chat pipeline.

All heavy dependencies are stubbed via conftest fakes:
- FakeSTT (patched into the server module by the server_globals fixture)
- FakeLLM / FakeTTS swapped onto the backend instance per test
- MemoryStore forced onto the keyword path (no embedding model download)
"""

import json

import pytest


@pytest.fixture
def chat_backend(backend):
    """Backend with fake LLM/TTS and the offline keyword-search memory path."""
    backend.memory._embedder_loaded = True
    backend.memory.embedder = None
    return backend


def _ws(incoming=None):
    from conftest import FakeWebSocket

    return FakeWebSocket(incoming)


# ---------------------------------------------------------------------------
# Routing basics
# ---------------------------------------------------------------------------

async def test_ping_pong(chat_backend):
    ws = _ws()
    await chat_backend.handle_message(ws, {"type": "ping"})
    assert ws.sent == [{"type": "pong"}]


async def test_unknown_message_type_returns_error(chat_backend):
    ws = _ws()
    await chat_backend.handle_message(ws, {"type": "teleport"})
    errors = ws.frames("error")
    assert len(errors) == 1
    assert "teleport" in errors[0]["message"]


async def test_voice_call_start_and_end(chat_backend):
    ws = _ws()
    await chat_backend.handle_message(ws, {"type": "voice_call_start"})
    assert chat_backend.active_voice_call is True
    await chat_backend.handle_message(ws, {"type": "voice_call_end"})
    assert chat_backend.active_voice_call is False
    assert [f["status"] for f in ws.frames("status")] == ["connected", "idle"]


# ---------------------------------------------------------------------------
# Chat pipeline
# ---------------------------------------------------------------------------

async def test_chat_full_pipeline(chat_backend):
    from conftest import FakeLLM, FakeTTS

    chat_backend.llm = FakeLLM(chunks=("That's wonderful, ", "I'm glad!"))
    chat_backend.tts = FakeTTS(audio="QkFTRTY0")

    ws = _ws()
    await chat_backend.handle_message(ws, {"type": "chat", "content": "My name is Alice"})

    # Streamed chunks in order, then stream_end.
    streams = ws.frames("chat_stream")
    assert [c["content"] for c in streams] == ["That's wonderful, ", "I'm glad!"]
    assert all(c["streamId"] == "current" for c in streams)
    assert len(ws.frames("stream_end")) == 1

    # Final response carries the detected emotion.
    final = ws.frames("chat_response")
    assert len(final) == 1
    assert final[0]["content"] == "That's wonderful, I'm glad!"
    assert final[0]["emotion"] == "happy"

    # TTS audio delivered, then the deterministic end-of-turn marker.
    audio = ws.frames("tts_audio")
    assert len(audio) == 1 and audio[0]["audio"] == "QkFTRTY0"
    assert len(ws.frames("tts_done")) == 1

    # Conversation persisted; fact extracted from THIS message.
    history = chat_backend.memory.get_history()
    assert len(history) == 1
    assert history[0]["user_message"] == "My name is Alice"
    assert chat_backend.memory.get_user_profile()["name"] == "Alice"

    # The LLM received a personality-shaped message array.
    sent = chat_backend.llm.messages_seen
    assert sent[0]["role"] == "system"
    assert "Salieri" in sent[0]["content"]
    assert sent[-1] == {"role": "user", "content": "My name is Alice"}


async def test_chat_without_audio_still_sends_tts_done(chat_backend):
    from conftest import FakeLLM, FakeTTS

    chat_backend.llm = FakeLLM(chunks=("Plain reply",))
    chat_backend.tts = FakeTTS(audio=None)  # TTS yields nothing

    ws = _ws()
    await chat_backend.handle_message(ws, {"type": "chat", "content": "hi"})

    assert ws.frames("tts_audio") == []
    assert len(ws.frames("tts_done")) == 1  # end-of-turn marker always sent


async def test_chat_llm_failure_reports_error(chat_backend):
    from conftest import FakeLLM

    class FailingLLM(FakeLLM):
        async def chat_stream(self, messages):
            raise RuntimeError("model offline")
            yield  # pragma: no cover

    chat_backend.llm = FailingLLM()
    ws = _ws()
    await chat_backend.handle_message(ws, {"type": "chat", "content": "hi"})

    errors = ws.frames("error")
    assert len(errors) == 1
    assert "model offline" in errors[0]["message"]


# ---------------------------------------------------------------------------
# Settings handlers
# ---------------------------------------------------------------------------

async def test_get_settings_masks_api_key(chat_backend):
    ws = _ws()
    await chat_backend.handle_message(ws, {"type": "get_settings"})
    frames = ws.frames("settings")
    assert len(frames) == 1
    settings = frames[0]["settings"]
    assert "api_key" not in settings
    assert settings["api_key_set"] is False
    assert settings["provider"] == "ollama"  # built-in default


async def test_update_settings_persists_and_applies(chat_backend):
    from conftest import FakeTTS

    chat_backend.tts = FakeTTS()
    ws = _ws()
    await chat_backend.handle_message(ws, {
        "type": "update_settings",
        "settings": {
            "mascot_character": "male",
            "tts_voice": "en-GB-RyanNeural",
            "tts_rate": "-5%",
            "personality_name": "Mozart",
            "personality_style": "Extra dramatic.",
            "response_length": "concise",
            "not_a_real_key": "ignored",
        },
    })

    frames = ws.frames("settings")
    assert len(frames) == 1
    assert frames[0]["saved"] is True
    assert frames[0]["settings"]["tts_voice"] == "en-GB-RyanNeural"
    assert "not_a_real_key" not in frames[0]["settings"]

    # Persisted to the isolated settings file.
    on_disk = json.loads(chat_backend.settings.path.read_text(encoding="utf-8"))
    assert on_disk["personality_name"] == "Mozart"
    assert "not_a_real_key" not in on_disk

    # Applied to the engines immediately, no restart needed. The selected
    # persona owns the name and default voice; style notes remain minor flavor.
    assert chat_backend.personality.character["name"] == "Salieri"
    assert chat_backend.personality.character["variant"] == "male"
    assert chat_backend.personality.character["style_notes"] == "Extra dramatic."
    assert chat_backend.personality.character["response_length"] == "concise"
    assert chat_backend.tts.voice == "en-US-GuyNeural"
    assert chat_backend.tts.rate == "-10%"


async def test_character_selector_switches_persona_and_voice_immediately(chat_backend):
    from conftest import FakeTTS

    chat_backend.tts = FakeTTS()
    ws = _ws()
    await chat_backend.handle_message(ws, {
        "type": "update_settings",
        "settings": {"mascot_character": "female"},
    })
    assert "sharp and prickly" in chat_backend.personality.system_prompt
    assert chat_backend.tts.voice == "en-US-AriaNeural"
    assert chat_backend.tts.rate == "-5%"

    await chat_backend.handle_message(ws, {
        "type": "update_settings",
        "settings": {"mascot_character": "male"},
    })
    assert "Machine-like" in chat_backend.personality.system_prompt
    assert "Master" in chat_backend.personality.system_prompt
    assert chat_backend.tts.voice == "en-US-GuyNeural"
    assert chat_backend.tts.rate == "-10%"


async def test_update_settings_invalid_enum_falls_back(chat_backend):
    ws = _ws()
    await chat_backend.handle_message(ws, {
        "type": "update_settings",
        "settings": {"response_length": "essay"},
    })
    assert chat_backend.settings.get("response_length") == "normal"


async def test_update_settings_empty_api_key_keeps_existing(chat_backend):
    ws = _ws()
    await chat_backend.handle_message(ws, {
        "type": "update_settings",
        "settings": {"api_key": "sk-test-1234"},
    })
    await chat_backend.handle_message(ws, {
        "type": "update_settings",
        "settings": {"api_key": ""},  # UI re-submits form without the secret
    })
    assert chat_backend.settings.get("api_key") == "sk-test-1234"


async def test_list_models(chat_backend):
    from conftest import FakeLLM

    chat_backend.llm = FakeLLM()
    ws = _ws()
    await chat_backend.handle_message(ws, {"type": "list_models"})
    frames = ws.frames("models")
    assert frames == [{"type": "models", "models": ["fake-model-1", "fake-model-2"]}]


async def test_test_connection_success_and_failure(chat_backend):
    from conftest import FakeLLM

    ws = _ws()
    chat_backend.llm = FakeLLM(reply="OK")
    await chat_backend.handle_message(ws, {"type": "test_connection"})
    ok = ws.frames("test_result")
    assert ok[0]["ok"] is True
    assert "fake/fake-model replied: OK" in ok[0]["message"]

    ws = _ws()
    chat_backend.llm = FakeLLM(fail_chat=RuntimeError("endpoint unreachable"))
    await chat_backend.handle_message(ws, {"type": "test_connection"})
    bad = ws.frames("test_result")
    assert bad[0]["ok"] is False
    assert "endpoint unreachable" in bad[0]["message"]


# ---------------------------------------------------------------------------
# History handlers
# ---------------------------------------------------------------------------

async def test_load_history_roundtrip(chat_backend):
    chat_backend.memory.store_conversation("q1", "a1", emotion="happy")
    chat_backend.memory.store_conversation("q2", "a2")

    ws = _ws()
    await chat_backend.handle_message(ws, {"type": "load_history", "limit": 10})
    frames = ws.frames("history")
    assert len(frames) == 1
    assert [h["user_message"] for h in frames[0]["history"]] == ["q1", "q2"]
    assert frames[0]["history"][0]["emotion"] == "happy"


async def test_load_history_bad_limit_falls_back(chat_backend):
    chat_backend.memory.store_conversation("q", "a")
    ws = _ws()
    await chat_backend.handle_message(ws, {"type": "load_history", "limit": "garbage"})
    assert len(ws.frames("history")) == 1  # defaulted to 100, no error frame


async def test_clear_history(chat_backend):
    chat_backend.memory.store_conversation("q1", "a1")
    chat_backend.memory.store_conversation("q2", "a2")

    ws = _ws()
    await chat_backend.handle_message(ws, {"type": "clear_history"})
    frames = ws.frames("history_cleared")
    assert frames == [{"type": "history_cleared", "removed": 2}]
    assert chat_backend.memory.get_history() == []


# ---------------------------------------------------------------------------
# STT handlers (FakeSTT: no microphone available)
# ---------------------------------------------------------------------------

async def test_stt_start_failure_reports_error(chat_backend):
    ws = _ws()
    await chat_backend.handle_message(ws, {"type": "stt_start"})
    errors = ws.frames("error")
    assert len(errors) == 1
    assert "microphone" in errors[0]["message"]


async def test_stt_stop_without_text_is_quiet(chat_backend):
    ws = _ws()
    await chat_backend.handle_message(ws, {"type": "stt_stop"})
    assert ws.sent == []  # nothing transcribed -> nothing sent


# ---------------------------------------------------------------------------
# handler() — top-level connection entrypoint
# ---------------------------------------------------------------------------

async def test_handler_routes_frames_and_cleans_up(server_globals):
    ws = _ws(incoming=[
        json.dumps({"type": "ping"}),
        json.dumps({"type": "get_settings"}),
    ])
    await server_globals.handler(ws)

    assert ws.frames("pong") == [{"type": "pong"}]
    assert len(ws.frames("settings")) == 1


async def test_handler_invalid_json_reports_error(server_globals):
    ws = _ws(incoming=["this is not json"])
    await server_globals.handler(ws)
    errors = ws.frames("error")
    assert len(errors) == 1
    assert errors[0]["message"] == "Invalid JSON"
