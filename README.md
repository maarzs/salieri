# Salieri AI

<div align="center">

**Desktop AI Companion — Inspired by the Amadeus System from Steins;Gate 0**

*"Memory data is possible." — Makise Kurisu*

</div>

---

## What is Salieri AI?

Salieri AI is a **desktop AI companion** that lives on your screen — always available, always listening. Named after Antonio Salieri, the composer famously portrayed as Mozart's rival, Salieri is a tribute to the Amadeus AI system from the visual novel *Steins;Gate 0*.

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

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SALIERI_LLM_PROVIDER` | `ollama` | `ollama` or `openai` |
| `SALIERI_LLM_MODEL` | `llama3.2:3b` | Model name |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API URL |
| `OPENAI_API_KEY` | — | Required if using OpenAI |
| `SALIERI_TTS_VOICE` | `en-US-AriaNeural` | Edge TTS voice |
| `SALIERI_STT_MODEL` | `small` | Whisper model size |

### Character Customization

Edit `backend/personality.py` to customize Salieri's personality, voice style, and behavior. The character definition is a plain dictionary — modify the `personality` field to change how Salieri speaks and acts.

## Project Structure

```
salieri-app/
├── src/
│   ├── main/           # Electron main process
│   │   ├── main.ts     # Window, tray, backend lifecycle
│   │   └── preload.ts  # Context bridge for renderer
│   └── renderer/       # React frontend
│       ├── App.tsx     # Main app component
│       ├── components/ # UI components
│       ├── hooks/      # WebSocket hook
│       └── styles/     # CSS
├── backend/            # Python AI backend
│   ├── server.py       # WebSocket server, orchestrator
│   ├── llm.py          # Ollama/OpenAI LLM integration
│   ├── memory.py       # SQLite + vector memory store
│   ├── personality.py  # Character system & emotions
│   ├── tts.py          # Edge TTS + SAPI fallback
│   └── stt.py          # faster-whisper speech recognition
├── assets/             # App icons, sprites
└── package.json
```

## Inspiration

Salieri AI draws from the **Amadeus system** in *Steins;Gate 0* — an AI that digitizes human memory and personality to create a fully interactive digital consciousness. While we can't (yet) upload human memories, we can create AI companions that remember, learn, and grow with you.

> "Amadeus" means "beloved by God" in Latin.  
> "Salieri" was the composer who stood in Amadeus Mozart's shadow —  
> but history remembers both. This AI carries that spirit:  
> not a rival, but a companion in its own right.

## License

MIT — feel free to use, modify, and share.

---

*El Psy Kongroo.*