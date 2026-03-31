# 🌌 Lirox Agent OS (v0.4.1)

**Lirox** is a local-first autonomous AI agent OS with multi-step planning, tool execution, passive memory, and a rich Web UI — all running on your own machine.

---

## ✨ Features

- **🚀 Dual Interface** — Run in the terminal or the Web dashboard
- **🧠 Autonomous Planning** — Breaks complex goals into executable steps
- **🛡️ Local-First & Private** — Keys, memory, and profile stay on **your** machine
- **🔌 Multi-LLM Router** — Smart routing between Groq, Gemini, OpenAI, OpenRouter, NVIDIA NIM
- **📂 File System** — Read, write, and manage files autonomously
- **🎛️ Personalized** — Adapts to your niche, agent name, and goals over time

---

## 🚀 Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/baljotchohan/Lirox.git
cd Lirox
pip install -r requirements.txt
```

### 2. Add an API Key
Copy the example env file and fill in at least **one** key (Groq and Gemini both have free tiers):
```bash
cp .env.example .env
# Then edit .env and add your key
```

Or configure interactively on first launch — the setup wizard will prompt you.

### 3. Launch
```bash
# Terminal CLI
python3 -m lirox.main

# Web UI (recommended)
python3 -m lirox.web
# → Open http://127.0.0.1:8000
```

---

## 🔄 Updating Lirox

To pull the latest version and reinstall dependencies:

### Option A — Inside the CLI (easiest)
```
/update
```
Run this command from the Lirox terminal prompt. It will:
- Pull the latest code from GitHub (`git pull origin main`)
- Reinstall any new dependencies (`pip install -r requirements.txt`)
- Prompt you to restart

### Option B — Manual (from your shell)
```bash
cd /path/to/Lirox
git pull origin main
pip install -r requirements.txt
```
Then restart:
```bash
python3 -m lirox.main
# or
python3 -m lirox.web
```

---

## 🖥️ Usage

### 🌐 Web UI (Recommended)
```bash
python3 -m lirox.web
```
Open **http://127.0.0.1:8000** in your browser.

| Page | What it does |
|------|-------------|
| Chat | Fluid conversation with your agent |
| Autonomous Tasks | Visual planning and execution tracing |
| Agent Profile | Set your name, goals, and tone |
| System Settings | Manage API keys, autonomy threshold, memory |

### 🐚 CLI (Power Users)
```bash
python3 -m lirox.main
```

| Command | Description |
|---------|-------------|
| `/plan "goal"` | Create a multi-step execution plan |
| `/execute-plan` | Run the last generated plan |
| `/reasoning` | Show agent's reasoning for last action |
| `/trace` | Full execution trace (debug) |
| `/tasks` | List all scheduled tasks |
| `/schedule "goal"` | Schedule a task for later |
| `/profile` | View your current agent profile |
| `/setup` | Re-run the full setup wizard |
| `/set-goal "..."` | Add a goal to your profile |
| `/set-name Name` | Rename your agent |
| `/set-tone tone` | Change tone: direct / casual / formal / friendly |
| `/provider model` | Switch provider: groq / gemini / openai / openrouter / auto |
| `/memory` | View recent conversation memory |
| `/memory-search q` | Search memory for a keyword |
| `/clear` | Clear conversation memory (keeps profile) |
| `/add-api` | Open API key setup |
| `/update` | **Pull latest version from GitHub + reinstall deps** |
| `/status` | Show system status |
| `/exit` | Quit Lirox |

---

## 🏗️ Architecture

```text
Lirox/
├── lirox/               Core Agent Logic
│   ├── agent/           Planner, Executor, Memory, Reasoner, Profile
│   ├── server/          FastAPI Web Backend (routes, state, models)
│   ├── tools/           Browser, File I/O, Terminal tools
│   ├── ui/              CLI Display & Setup Wizard
│   └── web.py           Web Server Entry Point
├── frontend/            React + Vite Dashboard
├── scripts/             Maintenance & Verification
├── .env.example         API key template
└── requirements.txt     Python dependencies
```

---

## 🔑 Supported Providers

| Provider | Free Tier | Env Variable |
|----------|-----------|--------------|
| **Groq** | ✅ Yes (fast) | `GROQ_API_KEY` |
| **Gemini** | ✅ Yes | `GEMINI_API_KEY` |
| **OpenRouter** | ✅ Free models | `OPENROUTER_API_KEY` |
| **NVIDIA NIM** | ✅ Yes | `NVIDIA_API_KEY` |
| **OpenAI** | ❌ Paid | `OPENAI_API_KEY` |
| **DeepSeek** | ❌ Very cheap | `DEEPSEEK_API_KEY` |

---

## 🔒 Privacy & Safety

- **Local-First** — No cloud sync, no third-party storage
- **Terminal Shield** — Agent sandboxed to project root by default
- **Keys in `.env`** — Never committed to git (`.gitignore` covers this)
- **Append-only Memory** — Memory is compressed and local

---

Built with ❤️ by **Baljot Chohan & Antigravity**.
