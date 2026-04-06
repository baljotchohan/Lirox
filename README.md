# LIROX

```
  ██╗     ██╗██████╗  ██████╗ ██╗  ██╗
  ██║     ██║██╔══██╗██╔═══██╗╚██╗██╔╝
  ██║     ██║██████╔╝██║   ██║ ╚███╔╝
  ██║     ██║██╔══██╗██║   ██║ ██╔██╗
  ███████╗██║██║  ██║╚██████╔╝██╔╝ ██╗
  ╚══════╝╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝
```

**Autonomous Multi-Agent AI OS — Terminal First**

Lirox is a terminal-native AI agent platform built around a master orchestrator and four specialist agents — Finance, Code, Browser, and Research. Every agent runs its own dedicated multi-stage sub-agent pipeline, with always-on complex thinking enabled across the board.

---

## Agents

| Agent | Pipeline | Capability |
|---|---|---|
| 📊 **Finance** | 5-stage | Markets, stocks, technical/fundamental analysis, valuation, risk |
| 💻 **Code** | 11-stage | Write, debug, review, execute code · Desktop control |
| 🌐 **Browser** | Direct | Web navigation, content extraction, live data |
| 🔬 **Research** | 5-stage | Perplexity-style multi-source research with cited answers |

### Finance Agent — 5-Stage Pipeline
1. **Data Collector** — Pulls live prices, history, financials, balance sheets, cashflow via `yfinance`
2. **Technical Analyst** — RSI, MACD, MA50/MA200, trend direction
3. **Fundamental Analyst** — P/E, P/B, P/S, EV/EBITDA, ROE, debt/equity, FCF yield
4. **Risk Manager** — Beta, volatility, 52-week range position, RSI risk signal
5. **Synthesizer** — Produces Buffett + quant-style recommendation with price target

### Code Agent — 11-Stage Pipeline
1. 🎯 **Intent Analyst** — Identifies goal, scope, and constraints
2. 🧩 **Concept Analyzer** — Maps all technical concepts and dependencies
3. 📋 **Project Planner** — Creates file structure and execution plan
4. 📌 **Task Creator** — Breaks plan into atomic ordered tasks
5. ✍️ **Code Writer** — Produces complete production-quality code
6. 🧪 **Test Engineer** — Writes pytest test suites
7. ✅ **Code Verifier** — Logic, null handling, algorithm verification
8. 📁 **File Verifier** — Import correctness, circular dependency check
9. 🔒 **Security Auditor** — SQL/command injection, path traversal, secrets
10. 🐛 **Debugger** — Runtime errors, resource leaks, race conditions
11. 🚀 **Build Master** — Finalizes all fixes and writes files to disk

Also supports: direct execution (read/write/bash/desktop) for non-build tasks.

### Research Agent — 5-Stage Pipeline
1. **Research Planner** — Maps search strategy
2. **Multi-Source Searcher** — DuckDuckGo + Tavily + direct URL fetch
3. **Live Data Fetcher** — GitHub Trending, Hacker News, Product Hunt, news
4. **Fact Extractor** — Pulls key data points with source attribution
5. **Cross-Validator + Synthesizer** — Checks consistency, produces cited answer

### Browser Agent
Direct browser automation via CDP. Fetches, parses, and extracts content from the web.

---

## Installation

**Requirements: Python 3.9+**

```bash
git clone https://github.com/baljotchohan/Lirox.git
cd Lirox
pip install -e .
```

Or install dependencies manually:

```bash
pip install -r requirements.txt
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

### Required (at least one LLM provider)

```env
GROQ_API_KEY=your_key          # Recommended — fast and free tier
GEMINI_API_KEY=your_key        # Google Gemini
OPENAI_API_KEY=your_key        # GPT-4o
ANTHROPIC_API_KEY=your_key     # Claude
OPENROUTER_API_KEY=your_key    # Multi-model gateway
DEEPSEEK_API_KEY=your_key      # DeepSeek
NVIDIA_API_KEY=your_key        # NVIDIA NIM
```

### Local LLM (Ollama)

```env
LOCAL_LLM_ENABLED=true
OLLAMA_ENDPOINT=http://localhost:11434
OLLAMA_MODEL=gemma4
```

### Optional — Enriches agents

```env
TAVILY_API_KEY=your_key                 # Premium research search (Research + Finance)
FINANCIAL_DATASETS_API_KEY=your_key    # SEC filings and fundamentals (Finance)
DESKTOP_ENABLED=true                    # Enable desktop control (Code Agent)
```

---

## Running

```bash
lirox
```

Or via Python:

```bash
python -m lirox
```

With verbose thinking traces:

```bash
lirox --verbose
```

---

## Commands

| Command | Description |
|---|---|
| `/help` | Show all commands |
| `/agent <name>` | Switch agent — `finance` · `code` · `browser` · `research` · `chat` |
| `/agents` | List all agents with pipelines |
| `/history [n]` | Show last N conversation sessions |
| `/session` | Current session info |
| `/models` | Show configured LLM providers |
| `/memory` | Memory stats per agent |
| `/think <query>` | Run the thinking engine standalone |
| `/profile` | Show your profile |
| `/reset` | Clear session memory, start new session |
| `/desktop` | Desktop control status and test |
| `/test` | Run full system diagnostics |
| `/import-memory` | Import memory from ChatGPT / Claude / Gemini |
| `/export-profile` | Export your profile as JSON |
| `/update` | Pull latest changes from GitHub and reinstall |
| `/uninstall` | Remove all Lirox data from this device |
| `/exit` | Shutdown |

---

## Desktop Control

The Code Agent can control your computer — take screenshots, click, type, launch apps, open URLs — using an autonomous vision loop.

**Setup (macOS):**

```bash
pip install pyautogui pillow pytesseract
```

Then in System Settings → Privacy & Security → Accessibility — grant access to your terminal.

**Enable in `.env`:**

```env
DESKTOP_ENABLED=true
```

**Check status:**

```
/desktop
```

**Use it:**

```
open settings and check for updates
navigate to github.com and search for python projects
```

The Code Agent auto-detects desktop intent and activates the vision loop (screenshot → think → act → verify, up to 20 steps).

> macOS note: The yellow screen border overlay is skipped on macOS (AppKit requires main-thread GUI). All desktop control functionality works normally.

---

## Optional Desktop Dependencies

| Package | Purpose |
|---|---|
| `pyautogui` | Mouse, keyboard, window control |
| `pillow` | Screenshots |
| `pytesseract` + Tesseract | OCR screen reading |
| `pygetwindow` | Window management (Windows only) |

---

## LLM Provider Priority

Lirox auto-selects the best available provider in this order:

1. Groq (fastest)
2. OpenRouter
3. Gemini
4. OpenAI
5. Anthropic
6. DeepSeek
7. NVIDIA NIM
8. Ollama (local)

Set `DEFAULT_MODEL` in `.env` to override.

---

## Project Layout

```
lirox/
├── agents/          # Finance, Code, Browser, Research, Chat agents
├── orchestrator/    # Master orchestrator + session management
├── thinking/        # Always-on chain-of-thought engine
├── memory/          # Per-agent and global memory
├── tools/           # Desktop, file I/O, terminal, browser, search
├── skills/          # Reusable skill modules
├── ui/              # Terminal display + setup wizard
├── utils/           # LLM provider abstraction, structured logger
└── config.py        # Central configuration
```

---

## Security

- **Terminal sandboxing** — Only an allowlist of commands can be executed (no `rm -rf /`, no `shutdown`, etc.)
- **Path traversal protection** — All file writes validated with `Path.is_relative_to()` against project root
- **API keys** — Loaded from `.env`, never hardcoded
- **Security Auditor stage** — Code Agent scans all generated code before writing to disk

---

## License

MIT — see [LICENSE](LICENSE)

---

*Built by Baljot Singh*
