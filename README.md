# 🌌 Lirox Agent OS (v0.6.0 Research Engine)

**Lirox** is a local-first autonomous AI agent OS designed for professional terminal environments. It features multi-step reasoning, planning, secure tool execution (terminal, file_io, browser), and persistent memory — all running on your own machine.

---

## ✨ Features

- **🐚 Professional CLI** — Hardened hacker-oriented interface with `rich`, dynamic task progress bars, and `prompt_toolkit`.
- **🎯 Smart Intent Routing** *(New in v0.6)* — Natural language command detection (auto-routes to chat, research, mapping, memory, or task execution).
- **🧠 Autonomous Strategy** — Uses phase-based reasoning traces (Analysis, Logic, Risk) to architect multi-step plans before execution.
- **🛡️ Hardened Security & Resource Limits** *(New in v0.6)* — Agent is sandboxed by default with a strict CLI-only risk policy, featuring RPM API rate limiters and host CPU/RAM monitors.
- **🔌 Multi-LLM Protocol** — Native support for Groq, Gemini, Anthropic, OpenAI, OpenRouter, and DeepSeek.
- **📁 Full File Control** — Read, write, and manage codebases within authorized paths.
- **🕵️ Deep Research Engine** *(New in v0.6)* — Perplexity-grade parallel search with auto-deduplication, source quality scoring, LLM synthesis, and cited markdown reporting.
- **🦁 Personal Identity & Learning** *(New in v0.6)* — Adapts to your specific niche, goals, and operator context over time safely into your profile, while tracking task success metrics.

---

## 🚀 Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/baljotchohan/Lirox.git
cd Lirox
pip install -r requirements.txt
```

### 2. Configure Keys
Create a `.env` file or run the setup wizard on first launch.
```bash
cp .env.example .env
# Edit .env and add at least one key (e.g. GROQ_API_KEY)
```

### 3. Launch the Kernel
```bash
python3 -m lirox.main
```

---

## 🔄 Updating Lirox

To pull the latest stability features and fixes, you have two options:

### Option A — Inside the CLI
Lirox now supports seamless self-updating natively inside the terminal:
```text
/update
```

### Option B — Manual `git pull` (Recommended)
Exit the Lirox kernel if running, then run:

```bash
cd Lirox
git pull origin main
pip install -r requirements.txt
python3 -m lirox.main
```

---

## 🖥️ Professional COMMANDS

### Research (v0.6)
| Command | Protocol |
|---------|----------|
| `/research "Q"`   | Launch a deep, multi-source research sequence |
| `/research "Q" --depth deep` | Extended 12-source research (standard is 6) |
| `/sources`        | View URLs, domains, and quality scores of your last research |
| `/tier`           | Check active API Tier (0=DuckDuckGo, 1=Standard, 2=Premium) |
| `/add-search-api` | Securely configure Tavily, Serper, or Exa API keys |

### General AI OS

| Command | Protocol |
|---------|----------|
| `/profile`   | Inspect operator identity and learned facts |
| `/memory`    | Check neural core statistics |
| `/clear`     | Flush ephemeral conversation history |
| `/trace`     | Review raw tool execution logs |
| `/reasoning` | Inspect the last thought trace / strategy |
| `/think goal`| Brainstorm a mission without execution |
| `/models`    | Map available LLM provider channels |
| `/test`      | Run internal kernel diagnostics suite |
| `/schedule`  | Queue a task for future execution |
| `/add-api`   | Securely configure API keys |
| `/exit`      | Safely shut down the Lirox kernel |

---

## 🏗️ Architecture (v0.6.0 Autonomous Intent Router)

```text
Lirox/
├── lirox/               Core Domain Logic
│   ├── agent/           Planner, Executor, Memory, Reasoner, Profile
│   ├── tools/           Hardened Browser, File I/O, Terminal toolsets
│   └── ui/              Rich CLI Display & Setup Wizard
├── outputs/             Authorized Agent Output Directory
├── scripts/             Maintenance & Audit (e.g., professional_audit.py)
├── .env.example         API Key Template
└── requirements.txt     Lean CLI Dependencies
```

---

## 🔑 Supported Provider Matrix

### Core LLMs
| Provider | Efficiency | Signal Variable |
|----------|------------|-----------------|
| **Groq** | ✅ Fastest | `GROQ_API_KEY` |
| **Gemini** | ✅ Logic Leader | `GEMINI_API_KEY` |
| **Anthropic** | ✅ Coding Pro | `ANTHROPIC_API_KEY` |
| **OpenRouter** | ✅ Scalable | `OPENROUTER_API_KEY` |
| **NVIDIA NIM** | ✅ Specialized | `NVIDIA_API_KEY` |
| **DeepSeek** | ✅ Cheap/Sharp | `DEEPSEEK_API_KEY` |
| **OpenAI** | ✅ Reliable | `OPENAI_API_KEY` |

### Search APIs (v0.6)
| Provider | Strength | Signal Variable |
|----------|----------|-----------------|
| **Tavily** | Best for Deep Research | `TAVILY_API_KEY` |
| **Serper** | Google Scale Search | `SERPER_API_KEY` |
| **Exa** | Neural / Tech Target | `EXA_API_KEY` |
| **DuckDuckGo** | Free Fallback (Tier 0) | *No key needed* |

---

## 🔒 Security Protocol

- **Local Persistence** — All state is anchored strictly to `PROJECT_ROOT`.
- **Memory Compression** — Passive fact learning ensures clean context windows.
- **Sandboxed Execution** — No sudo, rm, or system edits permitted by agent by default.
- **Privacy First** — Your data never leaves your machine unless you explicitly target a URL.

Built with ❤️ by **Baljot Chohan & Antigravity**.
