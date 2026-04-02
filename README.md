# 🌌 Lirox Agent OS (v0.7.0 — Headless Browser Engine)

**Lirox** is a local-first autonomous AI agent OS designed for professional terminal environments. It features multi-step reasoning, planning, secure tool execution (terminal, file_io, headless browser), and persistent memory — all running on your own machine.

---

## ✨ Features

- **🐚 Professional CLI** — Hardened hacker-oriented interface with `rich`, dynamic task progress bars, and `prompt_toolkit`.
- **🎯 Smart Intent Routing** — Natural language command detection (auto-routes to chat, research, browser, memory, or task execution).
- **🧠 Phase-Based Reasoning** — Uses strategy traces (Analysis, Logic, Risk) to architect multi-step plans before execution.
- **🛡️ Hardened Security** — Agent is sandboxed by default with a strict CLI-only risk policy, RPM rate limiters, and system performance monitoring.
- **🔌 Multi-LLM Protocol** — Native support for Groq (Fastest), Gemini (Logic), Anthropic (Coding), OpenAI, OpenRouter, and DeepSeek.
- **📁 Advanced File Control** — Efficiently manages codebases and data within authorized local paths.
- **🕵️ Deep Research Engine** — Perplexity-grade parallel search with auto-deduplication, source quality scoring, and cited markdown reporting.
- **📈 Numeric Data Extraction** — Proactive pattern-matching for real-time indices (Nifty 50, Bitcoin) and financial data.
- **🚫 Zero-Hallucination Logic** — Enhanced reflection engine that detects and flags "failed to extract" scenarios, preventing false success claims.
- **🦁 Personal Learning** — Adapts to your niche, goals, and operator context over time, safely persisting your profile.

### 🆕 v0.7.0 — Headless Browser Engine
- **🌐 Lightpanda Integration** — Full headless browser powered by the Lightpanda CDP engine for JavaScript-rendered content.
- **🔗 Chrome DevTools Protocol** — Direct CDP WebSocket bridge for navigation, DOM interaction, and JavaScript evaluation.
- **📊 Structured Data Extraction** — CSS selector-based scraping with table, link, and content extraction.
- **🛡️ Browser Security Layer** — SSRF prevention, URL/selector/JS validation, domain-level rate limiting, and injection pattern blocking.
- **🔄 Session Pooling** — Concurrent browser instances with automatic lifecycle management and graceful degradation.
- **📡 Real-Time Monitoring** — DOM change detection for live data tracking (stock prices, scores, etc).
- **⚡ Graceful Fallback** — Seamlessly falls back to `requests + BeautifulSoup` when Lightpanda is unavailable.

---

## 🚀 Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/baljotchohan/Lirox.git
cd Lirox
python -m pip install -r requirements.txt
```

### 2. Configure Keys
```bash
cp .env.example .env
# Edit .env and add at least one LLM key (e.g. GEMINI_API_KEY)
```

### 3. Install Lightpanda (Optional — for headless browser)
```bash
# macOS ARM64
curl -L -o lightpanda https://github.com/lightpanda-io/browser/releases/download/v0.10.4/lightpanda-aarch64-macos
chmod +x lightpanda
```

### 4. Launch the Kernel
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

### 🆕 Browser & Scraping (v0.7)
| Command | Description |
|---------|-------------|
| `/fetch <url>` | Fetch & extract page content using headless browser |
| `/scrape <url>` | Extract structured data (tables, links, text) from a page |
| `/browser` | View headless browser subsystem status & diagnostics |

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

## 🔑 Environment Configuration

Lirox uses a `.env` file to securely store your API keys. You can manage this in two ways:

### Option A — Automated Setup (Recommended)
Launch Lirox and use the built-in configuration commands:
- `/add-api` — Configure LLM providers (Gemini, Groq, OpenAI, etc.)
- `/add-search-api` — Configure Search APIs (Tavily, Serper, Exa)

### Option B — Manual Configuration
1.  Copy the template: `cp .env.example .env`
2.  Open `.env` in your preferred editor.
3.  Add your keys following the `KEY_NAME=value` format.

**Required Keys**: At least one LLM key is required (e.g., `GEMINI_API_KEY` or `GROQ_API_KEY`).

### Browser Configuration (Optional)
The headless browser works out of the box with defaults. Override via `.env`:
```bash
LIGHTPANDA_PATH=./lightpanda     # Binary location
BROWSER_PORT=9222                # CDP port
BROWSER_MAX_INSTANCES=5          # Max concurrent sessions
BROWSER_TIMEOUT=30               # Page load timeout (seconds)
```

---

## 🏛️ Core Subsystems & Connectivity
Lirox v0.7 is powered by a modular kernel architecture designed for high-fidelity autonomy.

- **[Researcher]**: Multi-source parallel search with 12+ factor verification + headless browser extraction.
- **[Planner]**: Strategic wave-based task decomposition with logical dependency mapping.
- **[Executor]**: Hardened tool orchestration (Terminal, Headless Browser, FileIO) with zero-trust validation.
- **[Browser Engine]**: Lightpanda CDP bridge with session pooling, security validation, and graceful degradation.
- **[Aesthetics]**: Rich terminal UI featuring real-time status cards and task progress indicators.

---

## 📘 Professional Documentation
For in-depth understanding and advanced configuration, refer to:

- **[Lirox Handbook](LIROX_HANDBOOK.md)**: Full architecture, workflows, and connectivity charts.
- **[Prompt Engineering Guide](PROMPT_ENGINEERING.md)**: Structured templates for professional AI assistance and fixing.

---

## 🏗️ Architecture Map
```text
Lirox/
├── lirox/                    Core Logic
│   ├── agent/                Agent Kernel (Core, Planner, Executor, Researcher)
│   ├── tools/                Tool Layer
│   │   ├── browser.py        Requests-based browser (fallback)
│   │   ├── browser_tool.py   🆕 High-level headless browser API
│   │   ├── browser_bridge.py 🆕 CDP WebSocket bridge (Lightpanda)
│   │   ├── browser_manager.py🆕 Session pooling & lifecycle
│   │   ├── browser_security.py🆕 URL/selector/JS validation
│   │   ├── terminal.py       Secure terminal executor
│   │   └── file_io.py        File system operations
│   ├── ui/                   Rich terminal display
│   └── utils/                LLM, errors, intent routing
├── tests/                    Test suite (30 tests)
├── outputs/                  Authorized Agent Output Store
├── data/                     Persistent Vector/JSON Storage
├── lightpanda               🆕 Headless browser binary
├── .env.example              API Configuration Template
└── requirements.txt          System Dependencies
```

---

## 🔒 Security & Privacy

- **Local-First**: All state is anchored strictly to your machine.
- **Zero-Cloud Memory**: Your profile and learned facts never leave your system.
- **Risk Policy**: No `sudo`, `rm -rf /`, or system-destabilizing edits permitted.
- **Privacy Core**: Data ingestion is strictly outbound-only for research queries.
- **Browser Sandbox**: SSRF prevention, private IP blocking, injection pattern detection, and domain rate limiting.

Built with ❤️ by **Baljot Chohan & Antigravity**.
