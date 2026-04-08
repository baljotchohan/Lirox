# 📜 Changelog

All notable changes to Lirox will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2024-01-15

### Overview

Initial stable release of Lirox — the autonomous AI agent for your terminal.

### Added

#### Core Features
- Mind Agent architecture with persistent memory across sessions
- 8-phase deep reasoning engine (UNDERSTAND → DECOMPOSE → ANALYZE → EVALUATE → SIMULATE → REFINE → PLAN → VERIFY)
- Multi-provider LLM support: Groq, OpenAI, Anthropic, Google Gemini, Ollama
- Fast-path optimization for simple queries (<500ms response time)

#### Memory System
- Long-term memory with structured fact extraction
- Session-based short-term context
- Profile learning from user interactions
- `/train` command for manual learning from sessions
- `/memory`, `/learnings`, `/forget` management commands

#### Agent System
- `/add-agent` interactive wizard for creating custom agents
- `/agents` - list all available agents
- `/agent <name>` - switch between agents
- `/remove-agent <name>` - delete custom agents
- Built-in agent templates: CodeReviewer, DataAnalyst, ContentWriter

#### Skills System
- `/add-skill` interactive wizard for creating custom Python skills
- `/skills` - list all available skills
- `/remove-skill <name>` - delete custom skills
- Auto-generated skill code using LLMs
- Skill testing and validation

#### Desktop Control
- Real-time screen mirroring
- Mouse and keyboard automation via PyAutoGUI
- OCR text recognition with Tesseract
- `/screen`, `/freeze`, `/unfreeze` commands
- Emergency stop with ESC key
- Desktop audit logging

#### Terminal UI
- Rich terminal interface with color output
- Progress indicators for long-running operations
- Structured command parsing
- Session history with `/history`

#### Configuration
- `.env` based configuration
- `/settings` interactive configuration editor
- `/profile` user profile display
- `/models` LLM provider management

#### Security
- Code sandboxing for generated scripts
- Confirmation prompts for destructive operations
- Audit logging for all actions
- No shell=True in subprocess calls
- Input validation throughout

#### Documentation
- Comprehensive README.md
- USE_LIROX.md user guide
- COMMANDS.md command reference
- ADVANCED.md advanced features guide
- CONTRIBUTING.md contribution guide

### Technical Details

- Python 3.8+ support
- Structured logging via custom logger
- SQLite + JSON local storage
- Modular architecture with clean separation of concerns
- Type hints throughout codebase

---

## Roadmap

### [1.1.0] - Q2 2024 (Planned)
- Multi-agent swarms with parallel execution
- Agent marketplace for sharing custom agents
- Improved context window management
- Web search integration

### [1.2.0] - Q3 2024 (Planned)
- Advanced desktop control with computer vision
- Workflow recording and playback
- Application-specific automation plugins
- Mobile device control via ADB

### [2.0.0] - Q4 2024 (Planned)
- Self-modifying agent capabilities
- Meta-learning from cross-session patterns
- Distributed agent execution
- Plugin API for third-party extensions

### [2.1.0] - Q1 2025 (Planned)
- Web interface (browser-based UI)
- REST API for programmatic access
- Team collaboration features
- Cloud sync for memory and agents

### [3.0.0] - Q2 2025 (Planned)
- Distributed agent swarms across machines
- Real-time collaboration between users
- Agent versioning and rollback
- Enterprise features

---

[1.0.0]: https://github.com/baljotchohan/Lirox/releases/tag/v1.0.0
