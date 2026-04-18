# 🦁 Lirox v2.0 — Your Personal AI Operating System

> **Intelligence as an Operating System.**
> An agent that lives in your terminal, learns who you are, and grows with you.

---

## What Makes Lirox Different

- **Learns you** — extracts permanent facts, preferences, and patterns from every conversation
- **Grows with you** — personality, tone, and knowledge evolve through `/train`
- **Knows its own code** — can audit and improve itself via `/improve` → `/apply`
- **Works with any LLM** — Ollama (local), Groq, Gemini, OpenAI, Anthropic, and more
- **Skills + Sub-agents** — extend with custom capabilities in seconds

---

## Install

```bash
git clone https://github.com/baljotchohan/Lirox.git
cd Lirox
pip install -e .
lirox
```

First run launches the setup wizard. Takes 2 minutes.

---

## Core Commands

| Command | Description |
|---|---|
| `/train` | **The main learning command.** Reads all conversations and extracts permanent knowledge. Run daily. |
| `/recall` | See everything the agent knows about you |
| `/learnings` | Full knowledge dump with stats |
| `/setup` | Re-run setup — change name, API keys, preferences |
| `/add-skill <desc>` | Create a custom skill (e.g. `/add-skill summarize any URL`) |
| `/add-agent <desc>` | Create a custom sub-agent (e.g. `/add-agent named stockbot that tracks prices`) |
| `@agentname <query>` | Talk to a custom sub-agent directly |
| `/improve` | Audit codebase for issues |
| `/apply` | Apply staged improvements (always review diffs first) |
| `/soul` | View agent personality and growth log |
| `/backup` | Backup all data to `~/.lirox_backup/` |
| `/import-memory` | Import conversation history from ChatGPT / Claude / Gemini |
| `/models` | List configured LLM providers |
| `/use-model <name>` | Pin a specific provider for this session |
| `/think <question>` | Deep-thinking mode with explicit reasoning chain |
| `/help` | Full command reference |

---

## How Learning Works

1. **Chat normally** — every message is stored in the session log
2. **Run `/train`** — the agent reads all sessions and extracts facts, topics, preferences, and projects
3. **Run `/recall`** — see everything it learned
4. Over time, the agent builds a rich model of who you are and what you care about
5. Every response is personalized using this knowledge

---

## LLM Setup

Lirox uses a fallback chain. Configure in `.env` at the repo root:

```env
# At least one required — Groq is free and fast
GROQ_API_KEY=your_key_here

# Optional — adds more providers to the fallback chain
GEMINI_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here

# Local LLM via Ollama (free, private)
LOCAL_LLM_ENABLED=true
OLLAMA_MODEL=llama3
```

---

## Skills & Sub-Agents

**Skills** — run when a query matches. Created with `/add-skill`:
```
/add-skill summarize any webpage I give you
/add-skill format my code in Python black style
/add-skill translate text to Hindi
```

**Sub-agents** — named entities you talk to directly. Created with `/add-agent`:
```
/add-agent named stockbot that checks live stock prices
/add-agent named coach that gives me workout advice
```

Then use: `@stockbot what's AAPL doing today?`

---

## Self-Improvement

Lirox can audit and improve its own code:

1. `/improve` — scans `lirox/` for real issues (syntax errors, bare excepts, TODOs)
2. Review the list of found issues
3. `/pending` — see the generated diffs
4. `/apply` — apply after you review (always creates a backup first)

**Safety**: patches that shrink a file to <40% of its original size are automatically
rejected to prevent the LLM from accidentally deleting code.

---

## Data & Privacy

All data lives locally:
- `data/memory/` — conversation logs
- `data/sessions/` — chat sessions
- `data/mind/` — learnings, skills, sub-agents
- `~/.lirox_backup/` — backups from `/backup`

Nothing is sent to the cloud except LLM API calls (which you control via `.env`).

---

## Architecture

```
lirox/
├── main.py              # CLI entry point + command router
├── agents/
│   ├── personal_agent.py    # File/shell/web tasks
│   └── agent_builder.py     # Skill + sub-agent generator
├── mind/
│   ├── agent.py         # MindAgent — personal advisor
│   ├── soul.py          # LivingSoul — personality engine
│   ├── trainer.py       # Learning extractor (the brain)
│   ├── learnings.py     # Persistent knowledge store
│   ├── skills/          # User-created skill modules
│   └── sub_agents/      # User-created sub-agent modules
├── orchestrator/
│   └── master.py        # Routes queries to agents
├── memory/
│   ├── manager.py       # Conversation buffer
│   └── session_store.py # Session persistence
├── autonomy/
│   ├── self_improver.py # Code audit engine
│   └── code_executor.py # Safe code runner
└── ui/
    ├── display.py       # Terminal rendering
    └── wizard.py        # Setup wizard
```
