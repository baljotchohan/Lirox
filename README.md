# Lirox v0.1: Your Local AI Terminal Agent

Lirox is a modular, CLI-based AI agent system designed for multi-LLM support, task planning, and safe terminal execution.

## 🚀 Features

- **Multi-LLM Router**: Unified interface for OpenAI, Gemini, Groq, NVIDIA, DeepSeek, and OpenRouter.
- **Task Planning**: Automatically decomposes complex goals into executable steps.
- **Terminal Execution**: Safely executes commands with a whitelist-based safety layer.
- **Contextual Memory**: Remembers the last 10 rounds of conversation for robust multi-turn chat.
- **Customizable**: Built with a modular architecture for easy extension.

## 🛠️ Setup

1.  **Clone the Repository**:
    ```bash
    git clone [your-repo-url]
    cd Lirox
    ```

2.  **Install Dependencies**:
    ```bash
    pip install requests python-dotenv google-generativeai openai
    ```

3.  **Configure API Keys**:
    You can now configure keys directly in the CLI using the interactive setup:
    ```bash
    python3 -m lirox.main
    # Inside Lirox prompt:
    /add-api
    ```
    Alternatively, copy `.env.example` to `.env` and fill in your keys manually.

4.  **Run Lirox**:
    ```bash
    python3 -m lirox.main
    ```

## 🎮 Commands

- `/add-api`: Launch the interactive API setup wizard (highly recommended for first-time use).
- `/set model [provider]`: Switch between providers (e.g., `openai`, `gemini`, `nvidia`, `openrouter`).
- `/clear`: Reset the current conversation memory.
- `/exit`: Close the Lirox session.

## 🛡️ Safety

Lirox includes a built-in safety filter for terminal commands. Destructive commands like `rm -rf` are blocked by default.

---
*Built with ❤️ by Baljot Chohan & Antigravity.*