<p align="center">
  <img src="https://img.shields.io/badge/version-0.8.5-gold?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCI+PHRleHQgeD0iNCIgeT0iMTgiIGZvbnQtc2l6ZT0iMTgiPvCfpqA8L3RleHQ+PC9zdmc+" alt="version" />
  <img src="https://img.shields.io/badge/python-3.9%2B-blue?style=for-the-badge&logo=python" alt="python" />
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="license" />
  <img src="https://img.shields.io/badge/providers-7%20LLMs-purple?style=for-the-badge" alt="providers" />
</p>

<h1 align="center">
  🦁 LIROX
</h1>

<h3 align="center">
  Autonomous AI Agent OS — Your Terminal, Supercharged
</h3>

<p align="center">
  Research anything. Automate tasks. Browse the web. Learn from every interaction.<br/>
  One command. Zero complexity. Runs locally in your terminal.
</p>

---

## What is Lirox?

Lirox is an autonomous AI agent that lives in your terminal. It connects to LLM providers (Gemini, Groq, OpenAI, Claude, DeepSeek, NVIDIA, OpenRouter), researches the web with real data, executes tasks, reads/writes files, and **learns your preferences** over time.

Unlike chatbots that just answer questions, Lirox:
- **Plans** complex tasks by breaking them into steps
- **Executes** those steps using terminal, browser, and file tools
- **Researches** topics across multiple sources with citations
- **Learns** your patterns, interests, and technical level autonomously
- **Remembers** everything across sessions

```
┌──────────────────────────────────────────────┐
│  You type naturally → Lirox figures out       │
│  whether to chat, research, browse, or        │
│  execute — automatically.                     │
└──────────────────────────────────────────────┘
```

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/baljotsingh/lirox.git
cd lirox
pip install -e .
```

### 2. Launch

```bash
lirox
```

That's it. The lion roars, the setup wizard guides you through:
- Naming your agent
- Choosing your niche (developer, creator, trader, researcher, etc.)
- Connecting an LLM provider (free tiers available)

### 3. Start Talking

```
[Lirox] ✦ What's the current price of Bitcoin?
[Lirox] ✦ Research the latest developments in autonomous AI agents
[Lirox] ✦ Create a Python script that converts CSV to JSON
[Lirox] ✦ What's the weather in Tokyo?
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         USER INPUT                          │
└──────────────────────────┬──────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │ Smart Router │  ← Intent classification
                    │  (v0.8.5)   │    Keyword + LLM hybrid
                    └──────┬──────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
     ┌──────▼──────┐ ┌────▼────┐  ┌──────▼──────┐
     │    CHAT     │ │RESEARCH │  │   BROWSER   │
     │  Direct LLM │ │Multi-src│  │ Page fetch  │
     └──────┬──────┘ └────┬────┘  └──────┬──────┘
            │              │              │
            │         ┌────▼────┐         │
            │         │ HYBRID  │         │
            │         │Research │         │
            │         │+Verify  │         │
            │         └────┬────┘         │
            └──────────────┼──────────────┘
                           │
                    ┌──────▼──────┐
                    │  Response   │  ← Clean formatting
                    │  Formatter  │    No JSON leaks
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Learning   │  ← Pattern tracking
                    │   Engine    │    Autonomous improvement
                    └─────────────┘
```

---

## Features

### Intelligent Routing
Every message is automatically classified — you never need to tell Lirox what mode to use.

| You type | Lirox routes to | What happens |
|----------|----------------|--------------|
| "Explain quantum computing" | **Chat** | Direct LLM response |
| "Research latest AI frameworks 2026" | **Research** | Multi-source search, synthesis, citations |
| "Fetch https://example.com" | **Browser** | Headless browser extraction |
| "What's Bitcoin price right now?" | **Hybrid** | Research + live browser verification |

### 7 LLM Providers with Auto-Fallback

```
Primary Request → Groq (fast)
       ↓ fails
Fallback #1 → OpenRouter (free models)
       ↓ fails
Fallback #2 → Gemini (free tier)
       ↓ fails
Fallback #3 → Anthropic / NVIDIA / OpenAI / DeepSeek
```

| Provider | Free Tier | Best For | Model |
|----------|-----------|----------|-------|
| Gemini | Yes | General + Research | gemini-2.0-flash |
| Groq | Yes | Speed (fastest) | llama-3.3-70b |
| OpenRouter | Yes | Free model access | mistral-7b |
| OpenAI | No | GPT-4o quality | gpt-4o |
| DeepSeek | Very cheap | Coding tasks | deepseek-chat |
| Anthropic | No | Complex reasoning | claude-3-5-haiku |
| NVIDIA | Yes | Heavy compute | llama-3.1-405b |

### Tiered Research System

| Tier | APIs | Quality | How to Unlock |
|------|------|---------|---------------|
| **Tier 0** (Free) | DuckDuckGo + Wikipedia + CoinGecko + wttr.in | Good | Default — no keys needed |
| **Tier 1** (Standard) | + Tavily OR Serper OR Exa | Great | Add one search API key |
| **Tier 2** (Premium) | All APIs in parallel | Best | Add 2+ search API keys |

### Free Public Data (Always Available)

Even without any API keys for search, Lirox pulls real data from:

| API | Data | Rate Limit |
|-----|------|-----------|
| DuckDuckGo Instant | General answers | Unlimited |
| Wikipedia REST | Encyclopedic knowledge | Unlimited |
| CoinGecko | Crypto prices & market data | 10-30/min |
| wttr.in | Weather worldwide | Generous |
| GitHub Search | Repository discovery | 60/hour |

### Autonomous Learning Engine

Lirox learns from every interaction without you doing anything:

```
┌─ WHAT IT TRACKS ──────────────────────────┐
│                                            │
│  Intent Patterns → What you usually ask    │
│  Time Patterns   → When you're active      │
│  Topic Clusters  → Your interest graph     │
│  Vocabulary      → Your technical level    │
│  Satisfaction    → What worked vs didn't   │
│  Corrections     → Mistakes to avoid       │
│                                            │
└─ WHAT IT DOES WITH IT ────────────────────┘
│                                            │
│  Adjusts response complexity               │
│  Predicts your next question               │
│  Personalizes system prompts               │
│  Tracks your evolving interests            │
│                                            │
└────────────────────────────────────────────┘
```

### Task Planning & Execution

For complex tasks, Lirox automatically:
1. **Thinks** — Generates a 3-phase reasoning trace
2. **Plans** — Breaks goal into 3-7 executable steps
3. **Executes** — Runs steps (parallel when possible)
4. **Verifies** — Checks outputs for failures
5. **Summarizes** — Clean results, no JSON noise

```
[Lirox] ✦ Create a market analysis report on electric vehicles

  ⚙ PHASE 1: STRATEGIC ANALYSIS
  ├─ Identify key EV market segments
  ├─ Define data sources needed
  └─ Scope: Global market, top 5 manufacturers

  ⚙ PHASE 2: EXECUTION
  ├─ Step 1: Research EV market trends [browser]
  ├─ Step 2: Extract sales data [browser]
  ├─ Step 3: Analyze competitive landscape [llm]
  ├─ Step 4: Generate report [file_io]

  ✓ Report saved: outputs/ev_market_analysis_20260403.md
```

---

## Commands

Lirox understands natural language — you rarely need commands. But when you do:

| Command | Description |
|---------|-------------|
| `/research "topic"` | Deep multi-source research with citations |
| `/web <url>` | Fetch and extract content from any webpage |
| `/profile` | View identity, memory stats, learning insights |
| `/models` | List active LLM providers and configure new ones |
| `/test` | Run full system diagnostics |
| `/help` | Show all commands with descriptions |
| `/update` | Check and apply Lirox updates |
| `/reset` | Factory reset (purges all data) |

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+C` | Interrupt (press twice to force quit) |
| `exit` or `/exit` | Clean shutdown |

---

## Setup & Configuration

### API Keys

API keys are stored in `.env` at the repo root. Never committed to git.

**Option 1: Interactive Setup**
```bash
lirox --setup
```

**Option 2: Manual**
```bash
# Create .env file
cp .env.example .env

# Add your keys
GEMINI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
# ... etc
```

**Option 3: In-app**
```
[Lirox] ✦ /models
# Follow prompts to add keys
```

### Search API Keys (Optional — for Tier 1/2 Research)

| Service | Free Tier | Get Key |
|---------|-----------|---------|
| Tavily | 1000 req/mo | [app.tavily.com](https://app.tavily.com) |
| Serper | 2500 req/mo | [serper.dev](https://serper.dev) |
| Exa | 1000 req/mo | [exa.ai](https://exa.ai) |

```bash
# Add to .env
TAVILY_API_KEY=tvly-xxxxx
SERPER_API_KEY=xxxxx
EXA_API_KEY=xxxxx
```

### Headless Browser (Optional)

For JavaScript-heavy sites, install [Lightpanda](https://lightpanda.io):

```bash
# Download binary to repo root
curl -L https://github.com/nicochristiner/lightpanda/releases/latest/download/lightpanda-linux-x86_64 -o lightpanda
chmod +x lightpanda
```

If not installed, Lirox falls back to `requests` + BeautifulSoup (works for 90% of sites).

---

## Project Structure

```
lirox/
├── __init__.py              # Package init
├── __main__.py              # python -m lirox support
├── main.py                  # CLI entry point, command handler, main loop
├── config.py                # Central config, paths, API keys, safety lists
│
├── agent/
│   ├── core.py              # LiroxAgent orchestrator
│   ├── executor.py          # Plan execution engine (parallel + retry)
│   ├── unified_executor.py  # Smart routing bridge (chat/research/browser/hybrid)
│   ├── planner.py           # Goal → structured plan converter
│   ├── reasoner.py          # Thinking loop & evaluation
│   ├── researcher.py        # Multi-source research engine
│   ├── memory.py            # Conversation memory with search
│   ├── profile.py           # User profile & system prompt generation
│   ├── learning_engine.py   # Autonomous pattern learning
│   ├── policy.py            # Risk evaluation for auto-execution
│   ├── scheduler.py         # Background task scheduling
│   └── tier.py              # Research tier system (Free/Standard/Premium)
│
├── tools/
│   ├── browser.py           # HTTP-based web fetching (always available)
│   ├── browser_tool.py      # Headless browser API (Lightpanda CDP)
│   ├── browser_bridge.py    # CDP WebSocket bridge
│   ├── browser_manager.py   # Browser session pool manager
│   ├── browser_security.py  # URL validation & rate limiting
│   ├── file_io.py           # Sandboxed file read/write/list
│   ├── terminal.py          # Safe command execution (allowlist)
│   ├── free_data.py         # Free public APIs (DDG, Wikipedia, CoinGecko, wttr.in)
│   ├── real_time_data.py    # Financial data extraction from page text
│   └── network_diagnostics.py # Connectivity checks & error diagnosis
│
├── ui/
│   ├── display.py           # Rich terminal UI (panels, spinners, tables, animation)
│   └── wizard.py            # First-run setup wizard
│
├── utils/
│   ├── llm.py               # LLM provider layer (7 providers + fallback chain)
│   ├── smart_router.py      # Intent classification & mode selection
│   ├── intent_router.py     # Command intent detection with persistence
│   ├── data_enrichment.py   # Source verification & enrichment
│   ├── response_formatter.py # Clean output formatting
│   ├── meta_parser.py       # Strip LLM metadata artifacts
│   ├── rate_limiter.py      # API rate limiting & resource monitoring
│   ├── input_validator.py   # XSS/injection/path traversal protection
│   ├── startup_validator.py # Pre-flight system checks
│   ├── structured_logger.py # JSON-structured logging
│   ├── errors.py            # Exception hierarchy
│   └── config_helper.py     # Interactive API key setup
│
├── pyproject.toml           # Package config & entry point
├── requirements.txt         # Dependencies
├── .env                     # API keys (git-ignored)
└── README.md                # This file
```

---

## Data Flow

### Chat Flow
```
User Input → SmartRouter → CHAT mode → LLM → Response Formatter → Terminal
                                          ↓
                                    Memory.save()
                                    Learning.on_interaction()
```

### Research Flow
```
User Input → SmartRouter → RESEARCH mode → Decompose Query
                                              ↓
                                        Parallel Search
                                    (DDG + Tavily + Serper + Exa)
                                              ↓
                                        Deduplicate & Rank
                                              ↓
                                        Extract Content
                                    (Headless browser or requests)
                                              ↓
                                        LLM Synthesis
                                    (Citations + Confidence)
                                              ↓
                                        Report (terminal + .md file)
```

### Task Execution Flow
```
User Goal → Reasoner (3-phase thinking)
               ↓
          Planner (3-7 steps with tools)
               ↓
          Policy Engine (risk assessment)
               ↓
          Executor (parallel waves)
          ├── Terminal steps (safe commands)
          ├── Browser steps (search + fetch)
          ├── File I/O steps (read/write)
          └── LLM steps (reasoning)
               ↓
          Verify + Summarize + Save to Memory
```

---

## Safety & Security

| Layer | Protection |
|-------|------------|
| Terminal | Allowlist-only commands, injection detection, blocklist |
| File I/O | Sandboxed to project + user dirs, path traversal blocked |
| Browser | URL validation, blocklist (localhost/private IPs), rate limiting |
| Input | XSS/SQL injection/code injection patterns blocked |
| API Keys | Stored in `.env`, never exposed in prompts or logs |
| Execution | Risk-based policy engine, mandatory confirmation for high-risk |

---

## Requirements

| Dependency | Version | Required? | Purpose |
|------------|---------|-----------|---------|
| Python | 3.9+ | Yes | Runtime |
| rich | 13.0+ | Yes | Terminal UI |
| requests | 2.31+ | Yes | HTTP client |
| beautifulsoup4 | 4.12+ | Yes | HTML parsing |
| python-dotenv | 1.0+ | Yes | .env loading |
| psutil | 5.9+ | Yes | Resource monitoring |
| google-genai | 0.3+ | Yes | Gemini provider |
| lxml | 4.9+ | Yes | Fast HTML parser |
| schedule | 1.2+ | Yes | Task scheduling |
| prompt_toolkit | 3.0+ | Yes | Input handling |
| websockets | 12.0+ | Optional | Headless browser CDP |
| openai | 1.0+ | Optional | OpenAI provider |
| anthropic | 0.7+ | Optional | Claude provider |

Install everything:
```bash
pip install -e ".[full]"
```

---

## Troubleshooting

| Issue | Solution |
|-------|---------|
| "No API keys configured" | Run `lirox --setup` or manually add keys to `.env` |
| "Module not found" | Run `pip install -e .` from the repo root |
| Research returns no results | Check internet connection; DuckDuckGo may be rate-limited |
| Browser fetch fails | Normal if Lightpanda not installed; falls back to requests |
| Slow responses | Check provider (Groq is fastest); ensure good internet |
| "Rate limit exceeded" | Wait 60 seconds; Lirox has built-in rate limiting |

---

## Roadmap

- [x] v0.5 — Core agent with 7 LLM providers
- [x] v0.6 — Tiered research system
- [x] v0.7 — Headless browser integration
- [x] v0.8 — Unified intelligence engine
- [x] v0.8.5 — Production stabilization + learning engine
- [ ] v0.9 — Custom API plans (pay-per-use research APIs via Lirox)
- [ ] v1.0 — Plugin system + community tools

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>Built by <a href="https://github.com/baljotsingh">Baljot Singh</a></strong><br/>
  <em>Lirox — Because your terminal deserves an AI that actually does things.</em>
</p>
