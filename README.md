<div align="center">

# 🦁 LIROX: Intelligence as an Operating System

__A Terminal-First, Autonomous Reasoning Engine & Personal AI Assistant__

[![Version](https://img.shields.io/badge/version-1.1.0-blue.svg?style=for-the-badge)](https://github.com/baljotchohan/Lirox)
[![Python](https://img.shields.io/badge/python-3.9+-yellow.svg?style=for-the-badge)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg?style=for-the-badge)](LICENSE)
[![Status](https://img.shields.io/badge/status-production--stable-success.svg?style=for-the-badge)]()

_Lirox is more than a chatbot. It is a local reasoning layer that connects multi-provider LLMs directly to your file system, shell, and internet. It learns who you are, remembers your preferences, and executes complex tasks autonomously._

[Features](#-key-capabilities) • [Installation](#-getting-started) • [Commands](#-command-encyclopedia) • [Architecture](#-core-architecture) • [Security](#-safety--security)

</div>

### Codebase Overview
This repository contains the core code for my AI advisor persona.

### Features
🔹 Strategic advice generator
🔹 Document generation engine
🔹 Tool usage guidance

### Installation Instructions
See the [Getting Started](#-getting-started) section below for installation steps.

---

## ⚡ The Lirox Manifesto

Lirox transforms your terminal into a powerful autonomous workstation. Unlike cloud-locked agents, Lirox is __Local-First__, __Identity-Driven__, and __Reasoning-Heavy__. It uses a sophisticated Multi-Agent Orchestration engine to break down complex requests, debate solutions, and verify results before presenting them to you.

---

## 🌟 Key Capabilities

### 🧠 Advanced Multi-Agent Thinking
Lirox doesn't just guess; it thinks. Every query triggers a "Thinking Phase" where agents brainstorm and validate plans. You can see the live reasoning trace or expand it with `/expand thinking` to see the full logic tree.

### 💾 Persistent Living Memory
Lirox features a "Living Soul" (MIND system) that continuously extracts:
🔹 __Facts__: What it knows about you and your environment.
🔹 __Preferences__: How you like your code formatted or your reports styled.
🔹 __Context__: Ongoing projects and goals.
_This data is stored in a production-grade SQLite backend with JSON fallback._

### 🐚 Secure Shell & File Autonomy
Lirox can read, write, move, and edit files across your system. It includes a __Hardened Sandbox__ with:
🔹 __Allow/Blocklists__: Prevents destructive commands (e.g., `rm -rf /`).
🔹 __Safe Dirs__: Only operates in approved directories (Desktop, Projects, etc.).
🔹 __Audit Trails__: Every action is logged and verifiable.

### 📄 Professional Document Pipeline
Lirox can generate high-fidelity files with genuine AI design:
🔹 📄 PDF/DOCX: Professional reports with thematic styling.
🔹 📊 PPTX: Multi-slide presentations with logical flow.
🔹 📈 XLSX: Structured data analysis and reporting.

---

## 🚀 Getting Started

### Quick Install (Cross-Platform)

```bash
# 1. Clone the repository
git clone https://github.com/baljotchohan/Lirox.git
cd Lirox

# 2. Run the platform-specific installer
# macOS
./install_macOS.sh
# Linux
./install_linux.sh
# Windows
install_windows.bat

# 3. Launch the engine
lirox
```

### Deep Uninstall (Full Cleanup)
If you need to completely remove Lirox and all its data from your device:
```bash
./install_macOS.sh --uninstall
```
*This removes API keys, user profiles, history, databases, caches, and uninstalls the pip package.*

---

## ⚙️ First Run & Setup

Upon first launch, Lirox will guide you through a __Setup Wizard__. You will need API keys for at least one provider.

### Supported Providers
🔹 __Groq/Gemini__: Best for speed and free-tier usage.
🔹 __OpenAI/Anthropic__: Best for high-complexity reasoning.
🔹 __Ollama__: 100% Local execution.
🔹 __DeepSeek/OpenRouter__: High-performance cost-effective alternatives.

---

## ⌨️ Command Encyclopedia

Lirox uses a rich set of slash-commands for system management.

### 🛠 System Operations
🔹 `/help`: The master directory of all available commands.
🔹 `/setup`: Re-run the onboarding wizard to change keys or profile settings.
🔹 `/restart`: Hot-reload the Lirox engine without exiting the terminal.
🔹 `/update`: Automatically pull latest changes from Git and re-bootstrap dependencies.
🔹 `/exit`: Gracefully shut down all agents and save the session.
🔹 `/test`: Run a quick diagnostic suite to verify API connectivity.
🔹 `/health`: A deep subsystem check (Config, DB, Execution, Docs, LLM connectivity).

### 🧠 Intelligence & Memory
🔹 `/expand thinking`: Visualizes the complete reasoning trace of the last query.
🔹 `/thinking-help`: Explains the icons and legend used in the thinking display.
🔹 `/memory`: Displays statistics on your learned facts and preference counts.
🔹 `/recall`: Lists everything Lirox has currently learned about you (Facts).
🔹 `/train`: Manually triggers the "Soul Engine" to process the recent chat into long-term memory.
🔹 `/history [n]`: Browse your past conversation sessions (last N).
🔹 `/reset`: Wipes the current "Short-term" session memory for a clean slate.

### 📂 Workspace & Data
🔹 `/workspace [path]`: Set or view the active operational directory. Lirox will prioritize this folder for all file operations.
🔹 `/backup`: Creates a timestamped ZIP of your entire Lirox data state.
🔹 `/export-memory`: Saves your "Soul" (Profile + Learnings) to a portable JSON file.
🔹 `/import-memory`: Import context from Claude/ChatGPT or other Lirox instances.
🔹 `/uninstall`: (In-App) Deep-cleans all data and removes Lirox from the system.

### 🤖 Model Management
- `/models`: Lists all active and configured LLM providers.
- `/use-model <provider>`: Pins Lirox to a specific provider (e.g., `/use-model groq`).

---

## 🏗 Core Architecture

Lirox is built on a modular "Pillar" architecture:

```text
lirox/
├── agent/        # Individual specialized agents (Identity, Profile)
├── agents/       # ReAct implementations (Coordinator, Researcher, Coder)
├── core/         # The "Heart" (Health, Diagnostics, Backup, Logger)
├── mind/         # The "Soul" (Learning Manager, Bridge, Identity)
├── orchestrator/ # The "Brain" (MasterOrchestrator, Event Handling)
├── thinking/     # The "Reasoning" (Live trace generator, expanded views)
├── ui/           # The "Face" (Rich terminal interface, Wizard)
└── tools/        # The "Hands" (Shell, Web, Document Creators)
```

### The 5 Pillars of Lirox
1. __Learning__: Context-aware personalization that improves with every chat.
2. __Security__: Cryptographic agent identities and hardened execution sandboxes.
3. __Multi-Agent__: Collaborative problem solving via specialized sub-agents.
4. __Testing__: Integrated health checks and red-team verification.
5. __Portability__: Seamless backup/export of your "Digital Twin."

---

## 🛡 Safety & Security

Lirox implements __Defense-in-Depth__:
🔹 __Identity System__: Every Lirox instance has a unique ED25519 cryptographic identity.
🔹 __Command Sanitization__: All shell commands are parsed and checked against a blocklist before execution.
🔹 __Path Isolation__: Agents cannot access system-critical paths like `/etc`, `/System`, or `C:\Windows`.
🔹 __Transparency__: Every file write or shell command is rendered clearly in the UI for user oversight.

---

## 💡 Pro Tips
🔹 Use `/workspace` to pin Lirox to your current coding project for better context.
🔹 Run `/health` if you notice slow responses to check if a provider is rate-limiting you.
🔹 Use `/expand thinking` after a complex request to learn _how_ Lirox solved the problem.

---

<div align="center">
  <i>"Lirox is not just an assistant; it is a partner in your digital autonomy."</i><br>
  <b>Crafted with ❤️ by Baljot Chohan</b>
</div>
