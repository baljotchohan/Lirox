# LIROX

**Intelligence as an Operating System.**

A terminal-first, local-first autonomous personal AI agent that reads, writes, and controls your desktop. Lirox learns who you are, remembers your conversations, and gets better over time.

## Install

```bash
pip install -e .
lirox
```

## Setup

```bash
lirox --setup
```

Add at least one API key (Groq is free and fast):
- **Groq**: [console.groq.com](https://console.groq.com) (free)
- **Gemini**: [aistudio.google.com](https://aistudio.google.com) (free)
- **OpenRouter**: [openrouter.ai](https://openrouter.ai) (free tier)
- **Ollama**: Local models, no API key needed

## What It Does

- **Reads & writes files** on your desktop, documents, downloads — real operations, verified on disk
- **Runs shell commands** safely with allowlist protection
- **Searches the web** via DuckDuckGo
- **Learns about you** from every conversation — run `/train` to crystallize knowledge
- **Knows its own code** — ask it about its architecture
- **Multi-provider LLM** — Groq, Gemini, OpenAI, Anthropic, DeepSeek, Ollama, and more

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
├── tools/
│   ├── file_tools.py    # Verified file operations
│   ├── terminal.py      # Safe shell execution
│   └── search/          # Web search (DuckDuckGo, Tavily)
├── ui/
│   ├── display.py       # Terminal UI (Rich)
│   └── wizard.py        # Setup wizard
├── utils/
│   ├── llm.py           # Multi-provider LLM layer
│   ├── streaming.py     # Response streaming
│   └── rate_limiter.py  # API rate limiting
└── verify/
    ├── receipt.py        # Structured execution receipts
    └── disk.py           # Disk verification
```

## License

MIT
