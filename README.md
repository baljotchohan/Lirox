# Lirox — Personal AI Agent OS

> Your own AI that knows you, works for you, and never forgets.

Lirox is not a chatbot. It is a local AI agent that learns who you are,
understands your goals, and works like a personal employee — running in
your terminal, remembering everything, executing tasks autonomously.

## What's New in v0.3 — Autonomous Agent

| Feature | v0.2 | v0.3 |
|---|---|---|
| Multi-step task planning | Basic | Structured JSON plans with tools & dependencies |
| Task execution | Simple | Retry logic, error recovery, context chaining |
| Reasoning & reflection | ✗ | ✓ Think → Act → Reflect loop |
| Web browsing | ✗ | ✓ Search & fetch web pages |
| File operations | ✗ | ✓ Safe read/write with sandboxing |
| Task scheduling | ✗ | ✓ Background task scheduling |
| Execution trace | ✗ | ✓ Full debug trace |

## What makes Lirox different

| Feature | Lirox | ChatGPT / Claude |
|---|---|---|
| Remembers you across sessions | ✓ | ✗ |
| Learns your name, goals, tone | ✓ | ✗ |
| Executes terminal commands | ✓ | ✗ |
| Plans & executes multi-step tasks | ✓ | ✗ |
| Browses the web for research | ✓ | ✗ |
| Reads/writes files safely | ✓ | ✗ |
| Reflects on its own actions | ✓ | ✗ |
| Runs locally, your data stays local | ✓ | ✗ |
| Named, personalised agent identity | ✓ | ✗ |

## Setup (3 minutes)

### 1. Clone and install

    git clone https://github.com/baljotchohan/Lirox
    cd Lirox
    pip install -r requirements.txt

### 2. Run Lirox

    python3 -m lirox.main

On first run, Lirox walks you through:
- Naming your agent (call it whatever you want)
- Entering your name, niche, and top goals
- Adding at least one API key (Gemini is free and recommended)

That's it. Your agent is online.

### 3. Updating Lirox

    git pull
    pip install -r requirements.txt

Then restart the agent.

### 4. Get a free API key (takes 2 minutes)

**Gemini (recommended)**
1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Click "Get API key"
3. Paste it when Lirox asks during setup

**Groq (also free, very fast)**
1. Go to [console.groq.com](https://console.groq.com)
2. Create account → API Keys → Create key
3. Paste it when Lirox asks

## Commands

### Agent Commands (v0.3)

    /plan "goal"      Show plan for a goal (don't execute)
    /execute-plan     Execute the last generated plan
    /reasoning        Show agent's reasoning for last action
    /trace            Show full execution trace (debug)
    /tasks            List all scheduled tasks
    /schedule "goal"  Schedule task for later

### Profile & Settings

    /profile          View your agent profile
    /setup            Re-run setup wizard
    /set-goal "..."   Add a goal
    /set-name Name    Rename your agent
    /set-tone direct  Change agent tone (direct/friendly/formal/casual)
    /provider auto    Switch LLM provider

### Memory & System

    /memory           View conversation memory
    /memory-search q  Search memory for keyword
    /clear            Clear memory (keep profile)
    /status           System status
    /add-api          Open API key setup
    /exit             Quit

## Example: Autonomous Task Execution

```
You › research AI trends and write a 500-word summary

┌ 📋 PLAN: research AI trends and write a 500-word summary ┐
│  Tools: 🌐 browser  🧠 llm  📁 file_io  •  Est. time: 6 minutes  │
│                                                                     │
│  1 ○ Search for latest AI trends                                    │
│    🌐 browser                                                       │
│  2 ○ Analyze findings into key categories                           │
│    🧠 llm (after step 1)                                            │
│  3 ○ Write 500-word summary                                         │
│    🧠 llm (after step 2)                                            │
│  4 ○ Save to outputs/ai_summary.md                                  │
│    📁 file_io (after step 3)                                        │
└─────────────────────────────────────────────────────────────────────┘

Execute plan? [y/n]: y

  1 ✓ Search for latest AI trends
  2 ✓ Analyze findings into key categories
  3 ✓ Write 500-word summary
  4 ✓ Save to outputs/ai_summary.md

📊 EXECUTION SUMMARY

Goal: research AI trends and write a 500-word summary
Result: 4/4 steps completed
```

## How Lirox learns you

Every session, Lirox:
1. Loads your profile (name, goals, niche, tone, background context)
2. Injects this into every LLM call — so it always speaks as YOUR agent
3. Extracts new facts from each conversation and updates your profile
4. Remembers the last 20 conversation exchanges for context

The longer you use it, the better it knows you.

## Supported LLM providers

| Provider | Model | Best for |
|---|---|---|
| Gemini | gemini-1.5-flash | General tasks, free |
| Groq | llama-3.3-70b | Fast responses, coding |
| OpenAI | gpt-4o | Complex reasoning |
| OpenRouter | Various | Flexibility |
| DeepSeek | deepseek-chat | Research, analysis |

Set `DEFAULT_MODEL=gemini` in `.env` to change the default.
Use `/provider auto` to let Lirox pick per request.

## Architecture (v0.3)

    lirox/
    ├── agent/
    │   ├── core.py          Agent orchestrator (brain)
    │   ├── planner.py       Goal → structured plan
    │   ├── executor.py      Plan execution with retry
    │   ├── reasoner.py      Think → Act → Reflect loop
    │   ├── memory.py        Conversation memory + search
    │   ├── profile.py       User identity & learning
    │   └── scheduler.py     Background task scheduling
    ├── tools/
    │   ├── terminal.py      Safe terminal execution
    │   ├── browser.py       Web scraping & search
    │   └── file_io.py       Safe file operations
    ├── ui/
    │   ├── display.py       Rich terminal rendering
    │   └── wizard.py        Setup wizard
    ├── utils/
    │   ├── llm.py           Multi-LLM router
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