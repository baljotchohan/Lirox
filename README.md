# Lirox v3.0

> **Intelligence as an Operating System.**
> Single unified agent. Full desktop control. Native file system access. Terminal integration.

Lirox transforms your computer into a responsive, memory-augmented AI extension of yourself. It controls your mouse, runs your scripts, searches the web, and learns the way you work.

## 🚀 Features
- **One Unified Agent:** A single `PersonalAgent` that dynamically routes queries between chat, shell execution, web search, and OS control.
- **Desktop Control (Vision-Action Engine):** Lirox can see your screen, find UI elements, click, type, and navigate applications entirely autonomously.
- **Native OS Execution:** Deep integration with bash/zsh, git, node, and python right from the orchestrator.
- **Persistent Local Memory:** Session-based contextual thinking that remembers who you are across reboots.
- **Safe & Sandboxed:** Hardened path protection — system paths are blocked, input locks when Lirox drives the mouse, and you can intervene with `/pause`.

## 📦 Installation
```bash
git clone https://github.com/BaljotChohan/Lirox.git
cd Lirox
pip install -e .
cp .env.example .env
```
*(Add your API keys to `.env` : `GEMINI_API_KEY` or `GROQ_API_KEY` etc.)*

### Enable Desktop Control
If you want Lirox to drive your UI:
1. Set `DESKTOP_ENABLED=true` in `.env`
2. `pip install pyautogui pillow pytesseract`
3. **macOS:** System Settings → Privacy & Security → Accessibility → grant your terminal access.

## ⌨️ Usage
Launch Lirox directly from your terminal:
```bash
lirox
```

### Try These Commands:
- *"Search the web for the latest deepseek model specs"*
- *"Create a python script on my desktop that scrapes news"*
- *"Open Spotify and play something lofi"* *(Requires DESKTOP_ENABLED)*
- *"Read my code from ./src and explain the architecture"*

### System Commands:
- `/desktop` : View desktop capabilities and screenshot status
- `/think <query>` : Force Lirox to chain-of-thought before answering
- `/pause` / `/resume` : Stop/Start the agent when it's controlling your mouse
- `/help` : View all tools

## 🧠 Architecture
Lirox v3.0 uses a completely rewritten **Single Agent Architecture**.
- **Master Orchestrator:** Manages the active session and intercepts tool usage.
- **Task Classifier:** Routes user intent between `desktop`, `file`, `shell`, `web`, and `chat` paths at runtime.
- **Vision Loop:** Uses LLMs (vision-capable) to cross-reference screen pixels bounding boxes with pyautogui events.

---

*(Developed by Baljot Chohan)*
