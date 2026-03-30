# Lirox — Personal AI Agent OS

> Your own AI that knows you, works for you, and never forgets.

Lirox is a local AI agent OS that learns who you are, understands your goals, and works like a personal employee. Now offering a **premium Web UI** along with the classic terminal interface.

## 🚀 NEW in v0.3.1 — Web UI & Hardening

| Feature | v0.3 | v0.3.1 (Latest) |
|---|---|---|
| **Interface** | Terminal Only | **Desktop Web UI (React)** |
| **Theme** | Dark (CLI) | **Clean & Classy Light Mode** |
| **Security** | Experimental | **Hardened (SAFE_DIRS Anchored)** |
| **Task View** | Text-based Trace | **Visual Task Timeline** |
| **Tool Control** | Always On | **Configurable (Settings Toggle)** |
| **Onboarding** | CLI Wizard | **Web Setup Wizard** |

## 🛠 Setup (3 minutes)

### 1. Clone and install

    git clone https://github.com/baljotchohan/Lirox
    cd Lirox
    pip install -r requirements.txt

### 2. Run the Web UI (Recommended)

    python3 -m lirox.web

Then visit: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

### 3. Run the CLI (Classic)

    python3 -m lirox.main

On first run, Lirox walks you through naming your agent, entering your profile details, and adding API keys (Gemini/Groq recommended).

## 💬 Features

- **Classy Light UI**: A modern dashboard designed for focus and ease of use.
- **Autonomous Task Planning**: Describe a goal (e.g., "research AI trends and write a summary"), and Lirox will build a multi-step plan.
- **Visual Execution**: Watch your agent work through steps in real-time with progress indicators.
- **Memory & Learning**: Lirox remembers your niche, goals, and past conversations to provide personalized assistance.
- **Smart Routing**: Automatically switches between LLM providers (Gemini, Groq, OpenRouter) based on availability.

## 🛡 Security & Privacy

- **Local First**: Your profile, memory, and keys stay on **your machine**.
- **Sandboxed Operations**: File operations are restricted to project-specific "Safe Directories" (`outputs/`, `data/`).
- **Terminal Safety**: The Terminal Tool (executing commands) is **disabled by default** in the Web UI and requires explicit activation in Settings.

## 🏗 Architecture (v0.3.1)

    lirox/
    ├── agent/           Orchestrator, Planner, Executor, Memory
    ├── server/          FastAPI Backend (API Routes & State)
    │   └── static/      Compiled React Frontend
    ├── tools/           Terminal, Browser, File IO
    ├── ui/              Classic CLI Rendering & Wizard
    ├── utils/           LLM Router, Config Helpers
    └── web.py           Web Server Entry Point
    frontend/            React + Vite Source Code

## Supported LLM providers

| Provider | Model | Best for |
|---|---|---|
| Gemini | gemini-1.5-flash | General tasks, high limit, free |
| Groq | llama-3.3-70b | Extreme speed, coding |
| OpenAI | gpt-4o | Complex reasoning |
| OpenRouter | Various | Ultimate flexibility |
| DeepSeek | deepseek-chat | Research & deep analysis |

---

Built by **Baljot Chohan & Antigravity**.
� llm.py           Multi-LLM router
    │   ├── config_helper.py API key manager
    │   └── errors.py        Error handling & recovery
    ├── config.py
    └── main.py

## Data & privacy

Everything stays on your machine.
- `profile.json` — your identity and goals
- `memory.json` — conversation history
- `.env` — your API keys

None of this is sent anywhere except to the LLM API you choose.

---

Built by Baljot Chohan & Antigravity.