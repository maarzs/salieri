# Salieri AI

[![CI](https://github.com/maarzs/salieri/actions/workflows/ci.yml/badge.svg)](https://github.com/maarzs/salieri/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/maarzs/salieri?label=release&style=flat-square)](https://github.com/maarzs/salieri/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/maarzs/salieri/total?style=flat-square)](https://github.com/maarzs/salieri/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](#license)

<div align="center">

**A desktop AI companion — inspired by the Amadeus system from *Steins;Gate 0***

*"Memory data is possible." — Makise Kurisu*

</div>

---

## Overview

Salieri AI is a desktop AI companion that lives on your screen — always available, always present. Unlike browser-based chatbots, Salieri runs as an always-on-top desktop window with a character avatar, voice conversation, persistent memory, and a distinct personality.

The name is a double reference: Antonio Salieri, the composer portrayed as Mozart's rival, and Salieri, an AI system in the *Steins;Gate 0* universe — a tribute to the Amadeus AI from the visual novel.

## Features

### Core

| Feature | Description |
|---|---|
| LLM-powered chat | Natural conversation with personality and long-term memory |
| Voice input | Local speech recognition via faster-whisper |
| Voice output | Natural TTS via Edge TTS (free), with a SAPI fallback |
| Persistent memory | Remembers past conversations and facts about you (SQLite + semantic search) |
| Emotion system | Detects and expresses emotions through text and avatar |
| Voice calls | Full-screen voice call mode for immersive conversation |
| Reminders | Ask Salieri to remind you about things — parsed from natural language, stored in SQLite, fired as desktop toasts |
| Settings panel | Pick the LLM provider and model (with a live model browser), TTS voice, personality, and character without editing files |
| Desktop integration | Always-on-top transparent window, system tray, `Alt+Shift+S` visibility toggle |

### Chibi Mascot Mode

- **Selectable characters** — two chibi mascots with distinct personas: a gloomy scientist girl (default) and a silver-haired gentleman, switchable in Settings → Character.
- **Compact desktop mode** — the mascot floats transparently on your desktop with idle animations (gentle bob, breathing pulse, blinking) and passes clicks through to windows behind it except where the mascot itself is. Drag it anywhere.
- **Speech balloon** — replies appear in a speech bubble with streaming text (or animated thinking dots), auto-hiding after 8 s or on click.
- **Hover-to-type input** — a slim input bar fades in near the bottom of the mascot for quick messages or mic toggle.
- **Expandable chat panel** — click the mascot to expand into the full scrollable chat history and controls; click again to collapse.

### Architecture

```
┌─────────────────────────────────────────────────┐
│                 Electron Shell                    │
│  ┌──────────────┐  ┌───────────────────────────┐ │
│  │  Main Process │  │    Renderer (React)        │ │
│  │  - System tray│  │  ┌─────────────────────┐  │ │
│  │  - Window mgmt│  │  │  Avatar (sprites)   │  │ │
│  │  - IPC bridge │  │  │  Chat panel         │  │ │
│  └──────┬───────┘  │  │  Voice call UI      │  │ │
│         │          │  └─────────────────────┘  │ │
│         │          └───────────────────────────┘ │
│         │ WebSocket (ws://localhost:9876)         │
│         ▼                                         │
│  ┌──────────────────────────────────────────┐    │
│  │         Python Backend (subprocess)        │    │
│  │  ┌─────────┐ ┌────────┐ ┌─────────────┐  │    │
│  │  │ LLM     │ │ Memory │ │ Voice Pipeline│  │    │
│  │  │ (Ollama │ │(SQLite │ │ STT→LLM→TTS  │  │    │
│  │  │ /Cloud) │ │+Vector)│ │              │  │    │
│  │  └─────────┘ └────────┘ └─────────────┘  │    │
│  └──────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Desktop shell | Electron + TypeScript | Cross-platform, always-on-top, system tray |
| UI | React + Vite + CSS | Component-based, fast to iterate |
| AI backend | Python (asyncio) | Direct ML library access (whisper, TTS, embeddings) |
| LLM | Ollama (local) / OpenAI-compatible (cloud) | Free local inference, cloud fallback |
| Speech-to-text | faster-whisper | Local, free, accurate |
| Text-to-speech | Edge TTS (Microsoft) | Free, natural voices, 30+ languages |
| Memory | SQLite + sentence-transformers | Persistent, semantic search, zero config |
| Transport | WebSocket | Real-time bidirectional, low latency |

## Download (Windows)

Pre-built releases are on the [GitHub Releases page](https://github.com/maarzs/salieri/releases).

| Asset | What it is |
|-------|------------|
| `Salieri.AI-<version>-x64.zip` | Extract-and-run folder — unzip anywhere, launch `Salieri AI.exe`. No installer. |

The release is a **plain extract-and-run zip**, not an installer: extract it anywhere and double-click `Salieri AI.exe`. No setup wizard, no per-launch self-extraction — startup is fast and you can run it from any folder (or a USB drive).

The release is modular: inside the extracted folder, the Electron shell sits next to a backend sidecar at `resources/backend/` — an embedded CPython runtime plus the backend source and its core dependencies, as loose files (never baked into the exe or the asar). That means:

- **The backend is independently updatable** — replace the `resources/backend/` folder (or any `.py` file in it) without touching the app.
- **Heavy AI modules install on demand** — local speech-to-text (faster-whisper) and semantic memory (sentence-transformers/torch, ~2 GB) are *not* in the zip. Enable them from **Settings → Modules**; the app pip-installs them into the app folder and restarts the backend. Chat + cloud LLM + Edge TTS work out of the box without them.
- **Your data is separate from the app** — settings and the memory database live in `%APPDATA%\Salieri`, so you can delete or replace the app folder without losing anything.

> [!NOTE]
> Local LLM inference needs **Ollama** ([install](https://ollama.com), then `ollama pull llama3.2:3b`). Alternatively, plug any OpenAI-compatible API endpoint and key into the in-app Settings panel and skip local models entirely — the settings panel includes a model browser that lists models available at the endpoint.

## Getting Started (from source)

### Prerequisites

- **Node.js** 18+ and **npm**
- **Python** 3.10+
- **Ollama** ([install](https://ollama.com)) with a model pulled (if using local inference):
  ```bash
  ollama pull llama3.2:3b
  ```
- **FFmpeg** (for audio processing)

### Installation

```bash
# 1. Clone the repository
cd salieri-app

# 2. Install frontend dependencies
npm install

# 3. Install Python backend dependencies
pip install -r backend/requirements.txt

# 4. Pull the LLM model (if using Ollama)
ollama pull llama3.2:3b

# 5. Start development
npm run dev
```

### Usage

The app appears as a small floating mascot on your desktop (compact mode). Use `Alt+Shift+S` to toggle visibility.

- **Drag the mascot** to move it anywhere on screen.
- **Hover near its bottom** to reveal the quick input bar — type or tap the mic for voice.
- **Click the mascot** to expand the full chat panel (history, voice call, settings); click again to collapse.
- **Replies** pop up in a speech balloon that auto-hides after 8 seconds.
- **Reminders** — ask in chat (e.g. "remind me to stretch in 20 minutes"); Salieri confirms and fires a toast when the time comes.

## Configuration

### In-app settings

Open the gear button in the title bar (or from the expanded chat panel). The panel covers:

- **LLM** — provider (Ollama local / OpenAI-compatible cloud), model — with a live model browser pulled from the endpoint — and host/API key.
- **Voice output** — enable/disable TTS, pick an Edge TTS voice, adjust speaking rate.
- **Personality** — companion name, free-text style notes, response length (concise / normal / detailed).
- **Character** — pick the chibi mascot: gloomy scientist girl (default) or silver-haired gentleman; each carries its own persona. Applies instantly and persists across launches.
- **Modules** — install the optional heavy modules (faster-whisper, sentence-transformers) on demand.

Settings persist to `settings.json` next to the memory database and survive updates. API keys are never sent back to the UI — the panel only sees whether a key is set, plus a last-4-character hint.

### Environment variables

Everything the Settings panel controls can also be set via environment variables (or `backend/.env`). The in-app setting always wins when present.

| Variable | Default | Description |
|----------|---------|-------------|
| `SALIERI_LLM_PROVIDER` | `ollama` | `ollama` or `openai` |
| `SALIERI_LLM_MODEL` | `llama3.2:3b` / `gpt-4o-mini` | Model name (default depends on provider) |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API URL |
| `OPENAI_BASE_URL` | — | Custom endpoint for OpenAI-compatible providers |
| `OPENAI_API_KEY` | — | Required if using OpenAI |
| `SALIERI_TTS_ENABLED` | `true` | Enable voice output |
| `SALIERI_TTS_VOICE` | `en-US-AriaNeural` | Edge TTS voice |
| `SALIERI_TTS_RATE` | `+10%` | Speaking rate adjustment |
| `SALIERI_PERSONALITY_NAME` | — | Override the companion's name |
| `SALIERI_PERSONALITY_STYLE` | — | Free-text style notes for the system prompt |
| `SALIERI_RESPONSE_LENGTH` | `normal` | `concise`, `normal`, or `detailed` |
| `SALIERI_MASCOT_CHARACTER` | `female` | `female` or `male` chibi mascot |
| `SALIERI_STT_MODEL` | `small` | Whisper model size |

### Character customization

The default character lives in `backend/personality.py`. Most customization is available through the Settings panel; edit the file only to change the core personality text, greeting, or emotion keywords.

## Project Structure

```
salieri-app/
├── src/
│   ├── main/           # Electron main process
│   │   ├── main.ts     # Window, tray, backend lifecycle
│   │   └── preload.ts  # Context bridge for renderer
│   └── renderer/       # React frontend
│       ├── App.tsx     # Main app component
│       ├── components/ # Avatar, Chat, VoiceCall, SettingsPanel, ...
│       ├── hooks/      # WebSocket hook
│       └── styles/     # CSS
├── backend/            # Python AI backend
│   ├── server.py       # WebSocket server, orchestrator
│   ├── llm.py          # Ollama/OpenAI LLM integration
│   ├── memory.py       # SQLite + vector memory store
│   ├── personality.py  # Character system & emotions
│   ├── settings.py     # Settings store (JSON + env precedence)
│   ├── tts.py          # Edge TTS + SAPI fallback
│   ├── stt.py          # faster-whisper speech recognition
│   ├── tools/          # Feature modules (reminders store & scheduler)
│   └── tests/          # pytest suite
├── .github/workflows/  # CI: frontend builds + backend pytest
├── assets/             # App icons, sprites
└── package.json
```

## Development

### Tests

The backend has a pytest suite (82 tests) covering memory extraction/search, personality prompt building, the settings store, reminders, and the WebSocket server handlers (chat pipeline with stubbed STT/LLM/TTS — no network or model downloads needed):

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

### CI

GitHub Actions runs on every push and PR:

- **Frontend** — `npm run build:main` and `npm run build:renderer` (TypeScript type-check + Vite bundle, Node 22)
- **Backend** — `pytest -v` (Python 3.11)

See `.github/workflows/ci.yml`.

## Inspiration

Salieri AI draws from the **Amadeus system** in *Steins;Gate 0* — an AI that digitizes human memory and personality to create an interactive digital consciousness. We can't (yet) upload human memories, but we can create AI companions that remember, learn, and grow with you.

The name is a deliberate in-universe callback: in *Steins;Gate 0*, Salieri is another AI system that exists alongside Amadeus. Naming this project Salieri honors that parallel — not a rival to Amadeus, but a distinct presence standing beside it.

## License

MIT — see [LICENSE](LICENSE) for details.

---

*El Psy Kongroo.*
