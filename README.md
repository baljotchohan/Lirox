# 🦁 Lirox

> **v1.1.0** · Intelligence as an Operating System

**Intelligence as an Operating System.**

A terminal-first, local-first autonomous personal AI agent that reads, writes, and controls your desktop. Lirox learns who you are, remembers your conversations, and gets better over time.

---

## Table of Contents

- [Requirements](#requirements)
- [Quick Install](#quick-install)
- [Platform-Specific Installation](#platform-specific-installation)
  - [Windows](#windows)
  - [Linux](#linux)
  - [macOS](#macos)
- [Virtual Environment Setup (Recommended)](#virtual-environment-setup-recommended)
- [First Run & Setup](#first-run--setup)
- [API Keys](#api-keys)
- [Commands](#commands)
- [What Lirox Can Do](#what-lirox-can-do)
- [Troubleshooting](#troubleshooting)
- [Architecture](#architecture)
- [License](#license)

---

## Requirements

- **Python 3.9 or newer** — [python.org/downloads](https://www.python.org/downloads/)
- **pip** (comes with Python; if missing run `python -m ensurepip --upgrade`)
- **Git** (optional, for cloning) — [git-scm.com](https://git-scm.com)
- At least one LLM API key — see [API Keys](#api-keys)

All Python library dependencies are installed automatically. If any library is missing when Lirox starts, it will detect and install it for you. You can also install them manually:

```bash
pip install -r requirements.txt
```

---

## Quick Install

```bash
# 1. Clone the repository
git clone https://github.com/baljotchohan/Lirox.git
cd Lirox

# 2. Install Lirox
pip install -e .

# 3. Run Lirox
lirox
```

> **Note:** If `pip install -e .` gives the error  
> `ERROR: file:///C:/Users/... does not appear to be a Python project`  
> make sure you are **inside the Lirox folder** before running the command (the folder must contain `pyproject.toml`).

---

## Platform-Specific Installation

### Windows

**Option A — Automated installer (recommended)**

```bat
git clone https://github.com/baljotchohan/Lirox.git
cd Lirox
install_windows.bat
```

**Option B — Manual steps**

```bat
:: 1. Verify Python is installed
python --version
:: If not found, try:
py --version

:: 2. Upgrade pip
python -m pip install --upgrade pip

:: 3. Install Lirox
python -m pip install -e .

:: 4. Run Lirox
lirox
```

**Option C — If `lirox` command is not found after install**

```bat
:: Run via Python module directly
python -m lirox

:: Or add Python's Scripts folder to PATH, e.g.:
:: C:\Users\YourName\AppData\Local\Programs\Python\Python3xx\Scripts
```

---

### Linux

**Option A — Automated installer (recommended)**

```bash
git clone https://github.com/baljotchohan/Lirox.git
cd Lirox
chmod +x install_linux.sh
./install_linux.sh
```

**Option B — Manual steps**

```bash
# 1. Install Python & pip (if not already installed)
# Ubuntu/Debian:
sudo apt update && sudo apt install -y python3 python3-pip

# Fedora/RHEL:
sudo dnf install -y python3 python3-pip

# Arch Linux:
sudo pacman -S python python-pip

# 2. Upgrade pip
python3 -m pip install --upgrade pip

# 3. Clone and install
git clone https://github.com/baljotchohan/Lirox.git
cd Lirox
python3 -m pip install -e .

# 4. Run Lirox
lirox
```

**Option C — If `lirox` command is not found**

```bash
# Add ~/.local/bin to PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Or run directly
python3 -m lirox
```

---

### macOS

**Option A — Automated installer (recommended)**

```bash
git clone https://github.com/baljotchohan/Lirox.git
cd Lirox
chmod +x install_macOS.sh
./install_macOS.sh
```

**Option B — Manual steps**

```bash
# 1. Install Python (via Homebrew is recommended)
brew install python
# Or download from https://www.python.org/downloads/macos/

# 2. Upgrade pip
python3 -m pip install --upgrade pip

# 3. Clone and install
git clone https://github.com/baljotchohan/Lirox.git
cd Lirox
python3 -m pip install -e .

# 4. Run Lirox
lirox
```

**Option C — macOS system Python restrictions (externally-managed-environment error)**

```bash
# Use a virtual environment (recommended):
python3 -m venv lirox-env
source lirox-env/bin/activate
pip install -e .
lirox

# Or allow system pip override (use with caution):
pip install --break-system-packages -e .
```

**Option D — If `lirox` command is not found**

```bash
# Add Python bin to PATH — detect your version first, then update PATH
python3 --version          # e.g. "Python 3.11.9" → version is 3.11
echo 'export PATH="$HOME/Library/Python/3.11/bin:$PATH"' >> ~/.zshrc   # replace 3.11 with your version
source ~/.zshrc

# Or run directly without changing PATH
python3 -m lirox
```

---

## Virtual Environment Setup (Recommended)

Using a virtual environment keeps Lirox isolated from your system Python and avoids permission issues:

```bash
# Create virtual environment
python3 -m venv lirox-env        # Linux/macOS
python  -m venv lirox-env        # Windows

# Activate it
source lirox-env/bin/activate    # Linux/macOS
lirox-env\Scripts\activate       # Windows (cmd)
lirox-env\Scripts\Activate.ps1   # Windows (PowerShell)

# Install inside the environment
pip install -e .

# Run Lirox
lirox

# Deactivate when done
deactivate
```

---

## First Run & Setup

```bash
# Start Lirox
lirox

# Run the setup wizard (add API keys, set your profile)
lirox --setup

# Check version
lirox --version
```

---

## API Keys

Lirox supports multiple LLM providers. Add at least one during `lirox --setup`:

| Provider | Cost | Link |
|----------|------|------|
| **Groq** | Free | [console.groq.com](https://console.groq.com) |
| **Gemini** | Free | [aistudio.google.com](https://aistudio.google.com) |
| **OpenRouter** | Free tier | [openrouter.ai](https://openrouter.ai) |
| **Ollama** | Local / Free | [ollama.com](https://ollama.com) |
| **OpenAI** | Paid | [platform.openai.com](https://platform.openai.com) |
| **Anthropic** | Paid | [console.anthropic.com](https://console.anthropic.com) |

---

## Commands

| Command | What it does |
|---------|-------------|
| `/help` | Show all commands |
| `/setup` | Configure API keys and profile |
| `/train` | Extract learnings from conversations |
| `/recall` | Show everything Lirox knows about you |
| `/workspace [path]` | Show or change workspace directory |
| `/models` | List available LLM providers |
| `/use-model <name>` | Pin a specific provider |
| `/history` | Show session history |
| `/memory` | Memory statistics |
| `/profile` | Your profile |
| `/backup` | Backup all data |
| `/export-memory` | Export as JSON |
| `/import-memory` | Import from ChatGPT/Claude/Gemini |
| `/exit` | Shutdown |

---

## What Lirox Can Do

- **Reads & writes files** on your desktop, documents, downloads — real operations, verified on disk
- **Runs shell commands** safely with allowlist protection
- **Searches the web** via DuckDuckGo
- **Learns about you** from every conversation — run `/train` to crystallize knowledge
- **Knows its own code** — ask it about its architecture
- **Multi-provider LLM** — Groq, Gemini, OpenAI, Anthropic, DeepSeek, Ollama, and more
- **Auto-installs missing dependencies** — Lirox detects and installs any missing Python libraries on startup

---

## Troubleshooting

### `ERROR: file:///C:/Users/... does not appear to be a Python project`

This error means pip cannot find `pyproject.toml` or `setup.py`. **Solution:** run `pip install -e .` from inside the cloned Lirox directory:

```bash
cd Lirox       # make sure you are in the project root
pip install -e .
```

---

### `lirox: command not found` (Linux/macOS)

Python user scripts may not be on your `PATH`. Fix:

```bash
# Linux
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc

# macOS (zsh) — detect your Python version first:
#   python3 --version   →  e.g. "Python 3.11.9"  →  use 3.11 below
echo 'export PATH="$HOME/Library/Python/3.11/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc

# Or use the module form:
python3 -m lirox
```

---

### `lirox` not recognized (Windows)

Python's `Scripts` directory is not on your `PATH`. Either:

1. Reinstall Python and check **"Add Python to PATH"** during setup.
2. Manually add the Scripts folder to your system PATH. Find the exact path by running `python -c "import sys; print(sys.executable)"` — the `Scripts` folder is in the same directory (e.g. `C:\Users\YourName\AppData\Local\Programs\Python\Python311\Scripts`).
3. Use the module form: `python -m lirox`

---

### `externally-managed-environment` error (macOS/Linux)

Your system Python is protected. Use a virtual environment or add the flag:

```bash
# Recommended: virtual environment
python3 -m venv lirox-env && source lirox-env/bin/activate && pip install -e .

# Quick override (not recommended for system Python)
pip install --break-system-packages -e .
```

---

### Missing dependency at runtime

Lirox will auto-detect and install missing packages when it starts. If that fails, install manually:

```bash
pip install -r requirements.txt
```

---

### `pip` not found

```bash
# Linux
sudo apt install python3-pip    # Ubuntu/Debian
sudo dnf install python3-pip    # Fedora

# macOS
brew install python

# All platforms
python3 -m ensurepip --upgrade
python3 -m pip install --upgrade pip
```

---

## Architecture

```
lirox/
├── main.py              # Entry point, REPL, command handler
├── config.py            # All configuration
├── agent/profile.py     # User profile system
├── agents/
│   ├── base_agent.py    # Abstract base
│   └── personal_agent.py # The one agent — chat, files, shell, web, self-aware
├── memory/
│   ├── manager.py       # 3-tier memory (buffer + daily logs + long-term)
│   └── session_store.py # Session persistence
├── mind/
│   ├── soul.py          # Agent identity (evolves over time)
│   ├── learnings.py     # Permanent knowledge store
│   └── trainer.py       # Extracts learnings from conversations
├── orchestrator/
│   └── master.py        # Master orchestrator
├── tools/
│   ├── file_tools.py    # Verified file operations
│   ├── terminal.py      # Safe shell execution
│   └── search/          # Web search (DuckDuckGo, Tavily)
├── ui/
│   ├── display.py       # Terminal UI (Rich)
│   └── wizard.py        # Setup wizard
├── utils/
│   ├── dependency_bootstrap.py  # Auto-install missing dependencies
│   ├── llm.py           # Multi-provider LLM layer
│   ├── streaming.py     # Response streaming
│   └── rate_limiter.py  # API rate limiting
└── verify/
    ├── receipt.py        # Structured execution receipts
    └── disk.py           # Disk verification
```

---

## License

MIT

