"""
Settings store - user-editable LLM configuration persisted to disk.

Precedence (highest first):
  1. settings.json (written by the in-app Settings panel)
  2. environment variables / .env
  3. built-in defaults

The file lives next to the memory DB so it survives app updates. When frozen
that is %APPDATA%\\Salieri\\settings.json; in dev it's backend/settings.json.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("salieri.settings")

# Keys the UI is allowed to set, mapped to their env-var fallback.
_FIELDS = {
    "provider": "SALIERI_LLM_PROVIDER",
    "model": "SALIERI_LLM_MODEL",
    "base_url": "OPENAI_BASE_URL",
    "api_key": "OPENAI_API_KEY",
    "ollama_host": "OLLAMA_HOST",
    "tts_enabled": "SALIERI_TTS_ENABLED",
    "tts_voice": "SALIERI_TTS_VOICE",
    "tts_rate": "SALIERI_TTS_RATE",
    "personality_name": "SALIERI_PERSONALITY_NAME",
    "personality_style": "SALIERI_PERSONALITY_STYLE",
    "response_length": "SALIERI_RESPONSE_LENGTH",
    "mascot_character": "SALIERI_MASCOT_CHARACTER",
}

_DEFAULTS = {
    "provider": "ollama",
    "model": "",
    "base_url": "",
    "api_key": "",
    "ollama_host": "http://localhost:11434",
    "tts_enabled": True,
    "tts_voice": "en-US-AriaNeural",
    "tts_rate": "+10%",
    "personality_name": "",
    "personality_style": "",
    "response_length": "normal",
    "mascot_character": "female",
}

# Fields restricted to a fixed set of values: {key: (allowed, ...)}
_ENUM_FIELDS = {
    "response_length": ("concise", "normal", "detailed"),
    "mascot_character": ("male", "female"),
}

# Model name used when the user hasn't picked one, per provider.
_MODEL_DEFAULTS = {
    "openai": "gpt-4o-mini",
    "ollama": "llama3.2:3b",
}


def _as_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return fallback
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class SettingsStore:
    """Load, merge, and persist user LLM settings."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._data: dict = {}
        self.load()

    def load(self) -> dict:
        """Read settings.json if present. Corrupt files are ignored, not fatal."""
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(self._data, dict):
                    raise ValueError("settings.json is not an object")
                logger.info(f"Loaded settings from {self.path}")
            except Exception as e:
                logger.warning(f"Ignoring unreadable settings.json ({e})")
                self._data = {}
        return self._data

    def save(self) -> None:
        """Write settings atomically so a crash can't leave a truncated file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        os.replace(tmp, self.path)
        logger.info(f"Saved settings to {self.path}")

    def get(self, key: str) -> Any:
        """Resolve one key through the precedence chain."""
        if key in self._data and self._data[key] not in (None, ""):
            return self._data[key]

        env_val = os.getenv(_FIELDS.get(key, ""), "")
        if env_val != "":
            if key == "tts_enabled":
                return _as_bool(env_val, _DEFAULTS[key])
            return env_val

        if key == "model":
            return _MODEL_DEFAULTS.get(self.get("provider"), "")
        return _DEFAULTS.get(key)

    def effective(self) -> dict:
        """All resolved settings, for the LLM/TTS engines."""
        out = {k: self.get(k) for k in _FIELDS}
        out["tts_enabled"] = _as_bool(out.get("tts_enabled"), True)
        return out

    def public(self) -> dict:
        """Resolved settings safe to send to the UI (API key masked).

        `api_key_set` lets the UI show whether a key exists without ever
        receiving the secret itself.
        """
        eff = self.effective()
        key = eff.pop("api_key", "") or ""
        eff["api_key_set"] = bool(key)
        eff["api_key_hint"] = f"...{key[-4:]}" if len(key) >= 4 else ""
        eff["model_defaults"] = _MODEL_DEFAULTS
        eff["settings_path"] = str(self.path)
        return eff

    def update(self, patch: dict) -> dict:
        """Apply a partial update from the UI and persist it.

        Unknown keys are dropped. An empty api_key is treated as "leave the
        existing key alone" so the UI can submit the form without the secret;
        pass api_key=None explicitly to clear it.
        """
        for key, value in patch.items():
            if key not in _FIELDS:
                continue

            if key == "api_key":
                if value is None:
                    self._data.pop("api_key", None)
                elif str(value).strip() != "":
                    self._data["api_key"] = str(value).strip()
                continue

            if key == "tts_enabled":
                self._data[key] = _as_bool(value, True)
                continue

            if key in _ENUM_FIELDS:
                normalized = str(value).strip().lower()
                if normalized not in _ENUM_FIELDS[key]:
                    normalized = _DEFAULTS[key]
                self._data[key] = normalized
                continue

            self._data[key] = str(value).strip()

        self.save()
        return self.public()
