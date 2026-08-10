# Salieri AI

[![CI](https://github.com/maarzs/salieri/actions/workflows/ci.yml/badge.svg)](https://github.com/maarzs/salieri/actions/workflows/ci.yml)

<div align="center">

**Desktop AI Companion — Inspired by the Amadeus System from Steins;Gate 0**

*"Memory data is possible." — Makise Kurisu*

</div>

---

## What is Salieri AI?

Salieri AI is a **desktop AI companion** that lives on your screen — always available, always listening. The name is a double Steins;Gate reference: it nods to Antonio Salieri, the composer famously portrayed as Mozart's rival, and to **Salieri, another AI in the Steins;Gate 0 universe** — a tribute to the Amadeus AI system from the visual novel *Steins;Gate 0*.

Unlike browser-based chatbots, Salieri is **always on your desktop**: an always-on-top window with a character avatar, voice conversation, persistent memory, and a distinct personality. It's your AI companion — not a tool, but a presence.

## Features

### Core (MVP)
- **💬 LLM-Powered Chat** — Natural conversation with personality and memory
- **🎤 Voice Input** — Speak to Salieri using local speech recognition (faster-whisper)
- **🔊 Voice Output** — Salieri speaks back with natural TTS (Edge TTS, free)
- **🧠 Persistent Memory** — Remembers past conversations and facts about you
- **🎭 Emotion System** — Detects and expresses emotions through text and avatar
- **📞 Voice Calls** — Full-screen voice call mode for immersive conversation
- **🖥️ Desktop Integration** — Always-on-top, transparent window, system tray
- **⚙️ In-App Settings Panel** — Pick the LLM provider, TTS voice, and personality without editing files

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

| Layer | Technology | Why |
|-------|-----------|-----|
| **Desktop Shell** | Electron + TypeScript | Cross-platform, always-on-top, system tray, battle-tested |
| **UI** | React + Vite + CSS | Fast, component-based, easy to style |
| **AI Backend** | Python (asyncio) | Direct ML library access (whisper, TTS, embeddings) |
| **LLM** | Ollama (local) / OpenAI (cloud) | FREE local inference, cloud fallback |
| **Speech-to-Text** | faster-whisper | Local, free, accurate, real-time |
| **Text-to-Speech** | Edge TTS (Microsoft) | Free, natural voices, 30+ languages |
| **Memory** | SQLite + sentence-transformers | Persistent, semantic search, zero config |
| **Communication** | WebSocket (ws) | Real-time bidirectional, low latency |

## Getting Started

### Prerequisites

- **Node.js** 18+ and **npm**
- **Python** 3.10+
- **Ollama** ([install](https://ollama.com)) with a model pulled:
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

### Running

The app will appear as a floating window on your desktop. Use `Alt+Shift+S` to toggle visibility.

- **Type** in the chat box to talk to Salieri
- **Click 🎤** to use voice input
- **Click 📞** to start a voice call
- **Minimize** with the yellow button, **hide** with the X

## Configuration

### In-App Settings Panel

Open the ⚙️ gear button in the title bar. The panel covers:

- **LLM** — provider (Ollama local / OpenAI-compatible cloud), model, host/API key
- **Voice output** — enable/disable TTS, pick an Edge TTS voice, adjust speaking rate
- **Personality** — companion name, free-text style notes, response length
  (concise / normal / detailed)

Settings are persisted to `settings.json` next to the memory database, so they
survive updates. API keys are never sent back to the UI — the panel only sees
whether a key is set (plus a last-4-char hint).

### Environment Variables

Everything the Settings panel controls can also be set via environment
variables (or `backend/.env`). The in-app setting always wins when present.

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
| `SALIERI_STT_MODEL` | `small` | Whisper model size |

### Character Customization

The default character lives in `backend/personality.py`. Most customization
is available through the Settings panel; edit the file only to change the core
personality text, greeting, or emotion keywords.

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
│   └── tests/          # pytest suite (memory, personality, settings, server)
├── .github/workflows/  # CI: frontend builds + backend pytest
├── assets/             # App icons, sprites
└── package.json
```

## Development

### Tests

The backend has a pytest suite (71 tests) covering memory extraction/search,
personality prompt building, the settings store, and the WebSocket server
handlers (chat pipeline with stubbed STT/LLM/TTS — no network or model
downloads needed):

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

### CI

GitHub Actions runs on every push and PR:

- **Frontend** — `npm run build:main` and `npm run build:renderer`
  (TypeScript type-check + Vite bundle, Node 22)
- **Backend** — `pytest -v` (Python 3.11)

See `.github/workflows/ci.yml`.

## Inspiration

Salieri AI draws from the **Amadeus system** in *Steins;Gate 0* — an AI that digitizes human memory and personality to create a fully interactive digital consciousness. While we can't (yet) upload human memories, we can create AI companions that remember, learn, and grow with you.

The name is a deliberate in-universe callback: in *Steins;Gate 0*, **Salieri** is another AI system that exists alongside Amadeus — a reminder that Amadeus is not the only consciousness in the story. Naming this project Salieri honors that parallel: an AI companion that isn't a rival to Amadeus, but a distinct presence standing beside it.

> "Amadeus" means "beloved by God" in Latin.  
> "Salieri" was the composer who stood in Amadeus Mozart's shadow —  
> but history remembers both. This AI carries that spirit:  
> not a rival, but a companion in its own right.

## License

MIT — feel free to use, modify, and share.

---

*El Psy Kongroo.*