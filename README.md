# Lirox — Personal AI Agent OS

> Your own AI that knows you, works for you, and never forgets.

Lirox is not a chatbot. It is a local AI agent that learns who you are,
understands your goals, and works like a personal employee — running in
your terminal, remembering everything, executing tasks autonomously.

## What makes Lirox different

| Feature | Lirox | ChatGPT / Claude |
|---|---|---|
| Remembers you across sessions | ✓ | ✗ |
| Learns your name, goals, tone | ✓ | ✗ |
| Executes terminal commands | ✓ | ✗ |
| Plans multi-step tasks | ✓ | ✗ |
| Runs locally, your data stays local | ✓ | ✗ |
| Named, personalised agent identity | ✓ | ✗ |

## Setup (3 minutes)

### 1. Clone and install

    git clone https://github.com/yourname/lirox
    cd lirox
    pip install -r requirements.txt

### 2. Run Lirox

    python3 -m lirox.main

On first run, Lirox walks you through:
- Naming your agent (call it whatever you want)
- Entering your name, niche, and top goals
- Adding at least one API key (Gemini is free and recommended)

That's it. Your agent is online.

### 3. Get a free API key (takes 2 minutes)

**Gemini (recommended)**
1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Click "Get API key"
3. Paste it when Lirox asks during setup

**Groq (also free, very fast)**
1. Go to [console.groq.com](https://console.groq.com)
2. Create account → API Keys → Create key
3. Paste it when Lirox asks

## Commands

    /help             Show all commands
    /profile          View your agent profile
    /setup            Re-run setup wizard
    /set-goal "..."   Add a goal
    /set-tone direct  Change agent tone (direct/friendly/formal/casual)
    /provider auto    Switch LLM provider
    /memory           View conversation memory
    /clear            Clear memory (keep profile)
    /status           System status
    /exit             Quit

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

## File structure

    lirox/
    ├── agent/
    │   ├── core.py          Main agent brain
    │   ├── memory.py        Conversation memory
    │   ├── profile.py       User identity & learning
    │   ├── planner.py       Goal → step breakdown
    │   └── executor.py      Task + terminal execution
    ├── tools/
    │   └── terminal.py      Safe terminal execution
    ├── ui/
    │   ├── display.py       Rich terminal rendering
    │   └── wizard.py        Setup wizard
    ├── utils/
    │   ├── llm.py           Multi-LLM router
    │   └── config_helper.py API key manager
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