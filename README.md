# 🌌 Lirox Agent OS (v0.3.1)

Lirox is a powerful, local-first autonomous agent designed to be your personal AI operating system. It handles complex, multi-step tasks natively on your machine with a focus on privacy, speed, and a premium user experience.

![Lirox Web UI](/Users/baljotchohan/.gemini/antigravity/brain/b5c13d21-051a-4110-9a82-586f7df6614c/lirox_web_ui_chat_page_1774893087514.png)

---

## ✨ Features

- **🚀 Dual Interface**: Use the high-performance **CLI** or the new, classy **Web UI**.
- **🧠 Autonomous Planning**: Breaks down complex goals into executable steps.
- **🛡️ Local-First & Private**: Your keys, memory, and profile stay on **your** machine.
- **🔌 Multi-LLM Router**: Smart routing between Gemini, Groq, OpenAI, and OpenRouter.
- **📂 File System Mastery**: Read, write, and manage files autonomously.
- **🎛️ Personalized**: Adapts to your niche, agent name, and preferred goals.

---

## 🚀 Quick Start

### 1. Installation
Clone the repo and install dependencies:
```bash
git clone https://github.com/baljotchohan/Lirox.git
cd Lirox
pip install -r requirements.txt
```

### 2. Configuration
Run the setup wizard to configure your identity and API keys:
```bash
python3 -m lirox.main --setup
```

---

## 🖥️ Usage

### 🌐 Web UI (Recommended for Desktop)
Experience Lirox in a beautiful, light-themed dashboard:
```bash
python3 -m lirox.web
```
- Open **http://127.0.0.1:8000** in your browser.
- **Chat**: Fluid conversation with your agent.
- **Tasks**: Visual planning and execution tracing.
- **Settings**: Toggle terminal tools and manage memory.

### 🐚 CLI (Power Users)
Classic terminal interface with real-time spinners:
```bash
python3 -m lirox.main
```
- `/plan`: Create a multi-step execution plan.
- `/clear`: Wipe session memory.
- `/add-api`: Manage your provider keys.

---

## 🏗️ Architecture

```text
Lirox/
├── lirox/               Core Agent Logic
│   ├── agent/           Planner & Executor
│   ├── server/          FastAPI Web Backend
│   ├── ui/              CLI Display logic
│   └── web.py           Web Server Entry Point
├── frontend/            React + Vite Dashboard
└── scripts/             Maintenance & Verification
```

---

## 🔒 Privacy & Safety
- **Terminal Isolation**: The agent only operates within the project root by default.
- **No Cloud Required**: No third-party servers between you and your LLM provider.
- **Encrypted Keys**: Keys are stored locally in your `.env` file.

---

Built with ❤️ by **Baljot Chohan & Antigravity**.
