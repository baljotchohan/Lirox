# 🌌 Lirox Agent OS (v0.5.0 CLI-First)

![Lirox Logo](lirox/assets/logo.png)

**Lirox** is a local-first autonomous AI agent OS designed for professional terminal environments. It features multi-step reasoning, planning, secure tool execution (terminal, file_io, browser), and persistent memory — all running on your own machine.

---

## ✨ Features

- **🐚 Professional CLI** — Hardened hacker-oriented interface with `rich` and `prompt_toolkit`.
- **🧠 Autonomous Strategy** — Uses reasoning traces to architectural multi-step plans before execution.
- **🛡️ Hardened Security** — Agent is sandboxed by default with a strict CLI-only risk policy.
- **🔌 Multi-LLM Protocol** — Native support for Groq, Gemini, Anthropic, OpenAI, OpenRouter, and NVIDIA NIM.
- **📂 Full File Control** — Read, write, and manage codebases within authorized paths.
- **🦁 Personal Identity** — Adapts to your specific niche, goals, and operator context over time.

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

## 🖥️ Professional COMMANDS

| Command | Protocol |
|---------|----------|
| `/profile`   | Inspect operator identity and learned facts |
| `/memory`    | Check neural core statistics |
| `/clear`     | Flush ephemeral conversation history |
| `/trace`     | Review raw tool execution logs |
| `/reasoning` | Inspect the last thought trace / strategy |
| `/think goal`| Brainstorm a mission without execution |
| `/models`    | Map available LLM provider channels |
| `/schedule`  | Queue a task for future execution |
| `/add-api`   | Securely configure API keys |
| `/exit`      | Safely shut down the Lirox kernel |

---

## 🏗️ Architecture (v0.5.0 Single-Channel)

```text
Lirox/
├── lirox/               Core Domain Logic
│   ├── agent/           Planner, Executor, Memory, Reasoner, Profile
│   ├── tools/           Hardened Browser, File I/O, Terminal toolsets
│   ├── ui/              Rich CLI Display & Setup Wizard
│   └── assets/          Official Branding & Visuals
├── outputs/             Authorized Agent Output Directory
├── .env.example         API Key Template
└── requirements.txt     Lean CLI Dependencies
```

---

## 🔑 Supported Provider Matrix

| Provider | Efficiency | Signal Variable |
|----------|------------|-----------------|
| **Groq** | ✅ Fastest | `GROQ_API_KEY` |
| **Gemini** | ✅ Logic Leader | `GEMINI_API_KEY` |
| **Anthropic** | ✅ Coding Pro | `ANTHROPIC_API_KEY` |
| **OpenRouter** | ✅ Scalable | `OPENROUTER_API_KEY` |
| **NVIDIA NIM** | ✅ Specialized | `NVIDIA_API_KEY` |
| **DeepSeek** | ✅ Cheap/Sharp | `DEEPSEEK_API_KEY` |

---

## 🔒 Security Protocol

- **Local Persistence** — All state is anchored strictly to `PROJECT_ROOT`.
- **Memory Compression** — Passive fact learning ensures clean context windows.
- **Sandboxed Execution** — No sudo, rm, or system edits permitted by agent by default.
- **Privacy First** — Your data never leaves your machine unless you explicitly target a URL.

Built with ❤️ by **Baljot Chohan & Antigravity**.
