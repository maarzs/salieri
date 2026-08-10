"""Tests for settings.py — precedence, persistence, masking, validation.

An autouse fixture strips every settings-related env var first: on a
developer machine backend/.env may have been loaded into os.environ by an
earlier test importing server.py, and CI must behave identically.
"""

import json

import pytest

from settings import SettingsStore

_ENV_KEYS = [
    "SALIERI_LLM_PROVIDER",
    "SALIERI_LLM_MODEL",
    "OPENAI_BASE_URL",
    "OPENAI_API_KEY",
    "OLLAMA_HOST",
    "SALIERI_TTS_ENABLED",
    "SALIERI_TTS_VOICE",
    "SALIERI_TTS_RATE",
    "SALIERI_PERSONALITY_NAME",
    "SALIERI_PERSONALITY_STYLE",
    "SALIERI_RESPONSE_LENGTH",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def store(tmp_path):
    return SettingsStore(tmp_path / "settings.json")


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

def test_defaults_without_file(store):
    assert store.get("provider") == "ollama"
    assert store.get("tts_enabled") is True
    assert store.get("tts_voice") == "en-US-AriaNeural"
    assert store.get("tts_rate") == "+10%"
    assert store.get("response_length") == "normal"
    assert store.get("personality_name") == ""


def test_model_default_follows_provider(store):
    assert store.get("model") == "llama3.2:3b"  # ollama default
    store.update({"provider": "openai"})
    assert store.get("model") == "gpt-4o-mini"
    # An explicitly chosen model always wins.
    store.update({"model": "gpt-4o"})
    assert store.get("model") == "gpt-4o"


def test_effective_contains_all_fields(store):
    eff = store.effective()
    for key in ("provider", "model", "base_url", "ollama_host", "tts_enabled",
                "tts_voice", "tts_rate", "personality_name",
                "personality_style", "response_length"):
        assert key in eff
    assert isinstance(eff["tts_enabled"], bool)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def test_update_persists_to_disk(store):
    store.update({"tts_voice": "en-GB-SoniaNeural", "personality_name": "Mozart"})
    on_disk = json.loads(store.path.read_text(encoding="utf-8"))
    assert on_disk["tts_voice"] == "en-GB-SoniaNeural"
    assert on_disk["personality_name"] == "Mozart"


def test_reload_picks_up_saved_values(tmp_path):
    path = tmp_path / "settings.json"
    SettingsStore(path).update({"tts_rate": "-5%"})
    reloaded = SettingsStore(path)
    assert reloaded.get("tts_rate") == "-5%"


def test_unknown_keys_dropped(store):
    store.update({"bogus_key": "value", "tts_rate": "+0%"})
    on_disk = json.loads(store.path.read_text(encoding="utf-8"))
    assert "bogus_key" not in on_disk
    assert on_disk["tts_rate"] == "+0%"


def test_values_are_stripped(store):
    store.update({"personality_name": "  Mozart  "})
    assert store.get("personality_name") == "Mozart"


# ---------------------------------------------------------------------------
# API key handling (never leaked to the UI)
# ---------------------------------------------------------------------------

def test_api_key_set_keep_and_clear(store):
    store.update({"api_key": "sk-abcdef1234"})
    assert store.get("api_key") == "sk-abcdef1234"

    # Empty string = "leave the existing key alone" (form submitted without it).
    store.update({"api_key": ""})
    assert store.get("api_key") == "sk-abcdef1234"

    # Explicit None clears it.
    store.update({"api_key": None})
    assert store.get("api_key") == ""


def test_public_masks_api_key(store):
    store.update({"api_key": "sk-test-987654321"})
    pub = store.public()
    assert "api_key" not in pub
    assert pub["api_key_set"] is True
    assert pub["api_key_hint"] == "...4321"
    assert "model_defaults" in pub
    assert "settings_path" in pub


def test_public_without_key(store):
    pub = store.public()
    assert pub["api_key_set"] is False
    assert pub["api_key_hint"] == ""


# ---------------------------------------------------------------------------
# Coercion + validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("false", False), ("0", False), ("no", False),
    ("true", True), ("1", True), ("on", True), (True, True), (False, False),
])
def test_tts_enabled_coercion(store, raw, expected):
    store.update({"tts_enabled": raw})
    assert store.get("tts_enabled") is expected


def test_response_length_enum_validated(store):
    store.update({"response_length": "essay"})
    assert store.get("response_length") == "normal"  # invalid -> default
    store.update({"response_length": "DETAILED"})
    assert store.get("response_length") == "detailed"  # normalized


# ---------------------------------------------------------------------------
# Precedence: file > env > defaults
# ---------------------------------------------------------------------------

def test_env_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("SALIERI_TTS_VOICE", "en-AU-NatashaNeural")
    store = SettingsStore(tmp_path / "settings.json")
    assert store.get("tts_voice") == "en-AU-NatashaNeural"


def test_file_beats_env(monkeypatch, tmp_path):
    monkeypatch.setenv("SALIERI_TTS_VOICE", "en-AU-NatashaNeural")
    store = SettingsStore(tmp_path / "settings.json")
    store.update({"tts_voice": "en-US-GuyNeural"})
    assert store.get("tts_voice") == "en-US-GuyNeural"


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("garbage", ["[1, 2, 3", "[]", "{not json"])
def test_corrupt_settings_file_ignored(tmp_path, garbage):
    path = tmp_path / "settings.json"
    path.write_text(garbage, encoding="utf-8")
    store = SettingsStore(path)
    assert store.get("provider") == "ollama"  # falls back to defaults
