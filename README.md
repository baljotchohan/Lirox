<div align="center">

```
  ██╗     ██╗██████╗  ██████╗ ██╗  ██╗
  ██║     ██║██╔══██╗██╔═══██╗╚██╗██╔╝
  ██║     ██║██████╔╝██║   ██║ ╚███╔╝
  ██║     ██║██╔══██╗██║   ██║ ██╔██╗
  ███████╗██║██║  ██║╚██████╔╝██╔╝ ██╗
  ╚══════╝╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝
```

**Intelligence as an Operating System**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![Runs Locally](https://img.shields.io/badge/runs-100%25%20locally-green.svg)](#local-first)
[![Terminal First](https://img.shields.io/badge/interface-terminal--first-black.svg)](#)

</div>

---

Lirox is a personal AI agent that lives in your terminal. It reads and writes your files, runs commands, searches the web, writes complete code, and — unlike every other AI tool — **it actually learns who you are and gets better the longer you use it.**

Your data never leaves your machine.

---

## What makes Lirox different

Every other agent forgets you after the session. Lirox builds a **persistent model of you** — your name, your projects, your preferences, your working style — learned from every conversation, stored permanently, used in every response.

The longer you use it, the more it feels like your own agent. Not a generic AI. Yours.

---

## Install

> **Requirements:** Python 3.9+ · macOS · Linux · Windows · Docker

---

### 🍎 macOS

```bash
# Option 1 — From source (recommended)
git clone https://github.com/baljotchohan/lirox.git
cd lirox
pip install -e .
lirox

# Option 2 — Using pipx (isolated environment, no conflicts)
pipx install git+https://github.com/baljotchohan/lirox.git
lirox

# Option 3 — With Homebrew Python
brew install python
pip3 install git+https://github.com/baljotchohan/lirox.git
lirox
```

---

### 🐧 Linux (Ubuntu / Debian / Fedora / Arch)

```bash
# Option 1 — From source
git clone https://github.com/baljotchohan/lirox.git
cd lirox
pip install -e .
lirox

# Option 2 — Using pipx
sudo apt install pipx        # Ubuntu/Debian
# sudo dnf install pipx      # Fedora
# sudo pacman -S python-pipx # Arch
pipx install git+https://github.com/baljotchohan/lirox.git
lirox

# Option 3 — Virtual environment (cleanest)
python3 -m venv ~/.lirox-env
source ~/.lirox-env/bin/activate
pip install -e /path/to/lirox
lirox
```

---

### 🪟 Windows (PowerShell / CMD / WSL)

```powershell
# Option 1 — From source (PowerShell)
git clone https://github.com/baljotchohan/lirox.git
cd lirox
pip install -e .
lirox

# Option 2 — Virtual environment (recommended on Windows)
python -m venv %USERPROFILE%\lirox-env
%USERPROFILE%\lirox-env\Scripts\activate
pip install -e .
lirox

# Option 3 — WSL2 (Ubuntu on Windows) — treat like Linux above
wsl
git clone https://github.com/baljotchohan/lirox.git
cd lirox && pip install -e . && lirox
```

---

### 🐳 Docker

```bash
# Build and run in an isolated container
git clone https://github.com/baljotchohan/lirox.git
cd lirox
docker build -t lirox .
docker run -it --rm \
  -v "$HOME/.lirox:/root/.lirox" \
  -e GEMINI_API_KEY=your_key \
  lirox
```

---

### 🔁 Full install (all optional providers)

```bash
pip install -e ".[full]"
# Includes: openai, anthropic, groq, websockets
```

---

### ⚡ Zero cost to start — works out of the box with:

| Provider | Cost | Setup |
|---|---|---|
| **Ollama** (fully local) | Free & private | `ollama pull llama3` |
| **Groq** (fastest cloud) | Free tier | [groq.com](https://groq.com) |
| **Gemini** | Free tier | [aistudio.google.com](https://aistudio.google.com) |
| **OpenAI** | Paid | [platform.openai.com](https://platform.openai.com) |
| **Anthropic** | Paid | [console.anthropic.com](https://console.anthropic.com) |
| **DeepSeek** | Low cost | [platform.deepseek.com](https://platform.deepseek.com) |

---

### 🛠 Troubleshooting install

```bash
# Python version check
python --version    # Must be 3.9+

# If `lirox` command not found after pip install:
python -m lirox     # Run as module

# Permission errors on macOS/Linux:
pip install --user -e .

# Upgrade pip first if install fails:
pip install --upgrade pip setuptools wheel
pip install -e .
```

---

## What it can do

### Files — direct access, no excuses
```
create a pdf about machine learning in my Documents folder
read my project README
list all Python files in ~/Projects/myapp
write a config.json with these settings...
```
Lirox executes the operation. Not describes it. Does it.

### Code — complete implementations, never truncated
```
write a FastAPI server with user authentication
create a Python script that monitors CPU usage
build a CLI tool that renames files in bulk
test all my LLM API keys
```
Full code, all imports, error handling, usage example. Never cut off.

### Shell — direct execution
```
run my tests
git status
check what's using port 3000
pip install requirements
```

### Web — search and retrieve
```
latest version of Node.js
research LangGraph vs CrewAI
FastAPI background tasks documentation
```

### Self-awareness — understands its own code
```
how do you handle memory?
explain your architecture
read your personal_agent.py
```

---

## Learning and memory

Every conversation is analyzed silently. Run `/train` to crystallize learnings permanently:

```
/train      → extracts facts, preferences, projects from recent sessions
/learnings  → view everything learned about you
```

From the next session onward, every response uses this knowledge.

---

## Custom skills

Create reusable tools in plain English:

```
/add-skill summarize any URL in 3 bullet points
/add-skill monitor a folder and list changed files
/skills                          → list all skills
/use-skill summarize_url url=https://example.com
```

---

## Custom agents

Create specialized sub-agents with their own personality:

```
/add-agent create an agent named Max who is a senior code reviewer
/add-agent create an agent named Nova who specializes in research
/agents                          → list all agents
@Max review this function: def add(a,b): return a+b
@Nova find recent papers on transformer efficiency
```

---

## Self-improvement

```
/improve    → audit all source files, stage patches for review
/pending    → see what patches are waiting
/apply      → commit patches (backups created automatically)
```

Core files are never auto-modified. You always review first.

---

## Commands

| Command | Description |
|---|---|
| `/help` | All commands |
| `/train` | Extract permanent learnings |
| `/learnings` | View learned knowledge |
| `/add-skill <desc>` | Create a new skill |
| `/skills` | List skills |
| `/use-skill <n>` | Run a skill |
| `/add-agent <desc>` | Create a new agent |
| `/agents` | List agents |
| `@name <query>` | Talk to an agent |
| `/improve` | Audit and stage improvements |
| `/pending` | List staged patches |
| `/apply` | Commit staged patches |
| `/soul` | Agent identity |
| `/mind` | Full Mind Agent state |
| `/memory` | Memory stats |
| `/think <q>` | Run reasoning engine |
| `/profile` | Your profile |
| `/backup` | Backup to `~/.lirox_backup/` |
| `/import-memory` | Import ChatGPT/Claude/Gemini export |
| `/update` | Update Lirox |
| `/exit` | Shutdown |

---

## Configuration — `.env`

```env
# Local (fully private, free)
LOCAL_LLM_ENABLED=true
OLLAMA_ENDPOINT=http://localhost:11434
OLLAMA_MODEL=llama3

# Cloud (any combination, all optional)
GROQ_API_KEY=your_key
GEMINI_API_KEY=your_key
OPENROUTER_API_KEY=your_key
OPENAI_API_KEY=your_key
ANTHROPIC_API_KEY=your_key
DEEPSEEK_API_KEY=your_key
```

Automatic fallback: if one provider fails, next available is tried.

---

## Run fully local

```bash
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3
# In .env: LOCAL_LLM_ENABLED=true, OLLAMA_MODEL=llama3
lirox
```

---

## Data layout

```
data/
  mind/
    soul.json          — agent identity and personality
    learnings.json     — everything learned about you
    skills/            — custom skills (.py modules)
    agents/            — custom sub-agents (.py modules)
  memory/              — conversation history
  sessions/            — session logs
  pending_patches/     — staged code improvements
```

---

## Architecture

```
lirox/
  orchestrator/  — routes queries: simple→MindAgent, tool→PersonalAgent
  agents/        — PersonalAgent (files, shell, web, code, self-awareness)
  mind/          — MindAgent (advisor, learning, skills, sub-agents)
    soul.py      — living identity that evolves over time
    learnings.py — permanent knowledge store
    trainer.py   — extracts facts from sessions
    self_improver.py — audits and stages code patches
    skills/      — dynamic skill registry (.py modules)
    sub_agents/  — dynamic sub-agent registry (.py modules)
  memory/        — 3-tier memory (buffer + daily + long-term facts)
  thinking/      — chain-of-thought reasoning engine
  tools/         — file, shell, web, search tools
  utils/         — LLM routing, streaming, rate limiting
```

---

## Roadmap

- [ ] Persistent daemon — always-on background agent
- [ ] Web UI — same memory and learning, browser interface
- [ ] MCP server — use Lirox as a tool from other AI tools
- [ ] Team mode — shared memory across a team

---

## Contributing

```bash
git clone https://github.com/your-org/lirox
cd lirox
pip install -e ".[full]"
lirox --setup
```

PRs welcome. Good starting points:
- New skills in `data/mind/skills/`
- New LLM providers in `lirox/utils/llm.py`
- Memory improvements in `lirox/memory/`

---

## License

MIT

---

<div align="center">
<strong>Built for developers who want an AI that actually knows them.</strong><br>
<em>Terminal-first. Local-first. Yours.</em>
</div>
