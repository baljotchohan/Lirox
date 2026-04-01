# 🌌 Lirox Agent OS (v0.6.0 Research Engine)

**Lirox** is a local-first autonomous AI agent OS designed for professional terminal environments. It features multi-step reasoning, planning, secure tool execution (terminal, file_io, browser), and persistent memory — all running on your own machine.

---

## ✨ Features

- **🐚 Professional CLI** — Hardened hacker-oriented interface with `rich`, dynamic task progress bars, and `prompt_toolkit`.
- **🎯 Smart Intent Routing** — Natural language command detection (auto-routes to chat, research, mapping, memory, or task execution).
- **🧠 Phase-Based Reasoning** — Uses strategy traces (Analysis, Logic, Risk) to architect multi-step plans before execution.
- **🛡️ Hardened Security** — Agent is sandboxed by default with a strict CLI-only risk policy, RPM rate limiters, and system performance monitoring.
- **🔌 Multi-LLM Protocol** — Native support for Groq (Fastest), Gemini (Logic), Anthropic (Coding), OpenAI, OpenRouter, and DeepSeek.
- **📁 Advanced File Control** — Efficiently manages codebases and data within authorized local paths.
- **🕵️ Deep Research Engine** — Perplexity-grade parallel search with auto-deduplication, source quality scoring, and cited markdown reporting.
- **🦁 Personal Learning** — Adapts to your niche, goals, and operator context over time, safely persisting your profile.

---

## 🚀 Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/baljotchohan/Lirox.git
cd Lirox
# Use python -m to ensure environment reliability
python -m pip install -r requirements.txt
```

### 2. Configure Keys
Create a `.env` file or run the setup wizard on first launch.
```bash
cp .env.example .env
# Edit .env and add at least one key (e.g. GEMINI_API_KEY)
```

### 3. Launch the Kernel
```bash
python -m lirox.main
```

---

## 🖥️ Command Protocol

### Research & Insight
| Command | Description |
|---------|-------------|
| `/research "Q"` | Multi-source deep research sequence |
| `/research "Q" --depth deep` | Extended 12-source research (requires Tier 1+) |
| `/think "goal"` | Brainstorm a strategy without tool execution |
| `/sources` | View domains and quality scores of the last research |
| `/tier` | Inspect research tier (DuckDuckGo, Standard, Premium) |

### System & Memory
| Command | Description |
|---------|-------------|
| `/profile` | Inspect learned identity and operator context |
| `/memory` | Neural core statistics and history audit |
| `/schedule "goal"` | Queue a mission for future execution |
| `/reset` | **FACTORY RESET**: Purge all profile, memory, and scheduled data |
| `/clear` | Flush ephemeral conversation history |
| `/test` | Run kernel performance and tool diagnostics |
| `/update` | Synchronize kernel with latest stable remote |
| `/exit` | Safely shutdown the autonomous kernel |

---

## 🏗️ Architecture

```text
Lirox/
├── lirox/               Core Logic (Agent, Tools, UI, Utils)
├── outputs/             Authorized Agent Output Store
├── scripts/             Maintenance & Audit Utilities
├── data/                Persistent Vector/JSON Storage
├── .env.example         API Configuration Template
└── requirements.txt     System Dependencies
```

---

## 🔒 Security & Privacy

- **Local-First**: All state is anchored strictly to your machine.
- **Zero-Cloud Memory**: Your profile and learned facts never leave your system.
- **Risk Policy**: No `sudo`, `rm -rf /`, or system-destabilizing edits permitted.
- **Privacy Core**: Data ingestion is strictly outbound-only for research queries.

Built with ❤️ by **Baljot Chohan & Antigravity**.
