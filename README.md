# 🌌 LIROX v3.0 — The Sovereign Agentic OS (Beta 1)

[![Version](https://img.shields.io/badge/Lirox-v3.0--Beta--1-blueviolet?style=for-the-badge)](https://github.com/baljotchohan/Lirox)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.9+-blue?style=for-the-badge&logo=python)](https://python.org)

**Lirox** is a premium, terminal-first autonomous AI operating system designed for high-performance research, full-stack development, and system-level execution. It leverages a sophisticated multi-agent architecture and a custom local model optimization engine to provide a state-of-the-art AI experience directly on your machine.

---

## 🚀 Key Features in v3.0 Beta

### 🧠 Intelligence Engine
- **Mode-Aware Thinking**: Dynamically switch between `⚡ Fast`, `🧠 Think` (Reasoning), and `🔮 Complex` (Research-grade) logic.
- **Multi-Agent Orchestration**: A central `MasterOrchestrator` routes your intent to specialized agents (Code, Finance, Research, Browser).
- **Intelligent Fallback Chain**: Automatically cycles through 7+ top-tier providers (Groq, Anthropic, Gemini, OpenAI, etc.) to ensure 100% uptime.

### 💻 Full-Stack Code Agent
- **Autonomous Execution**: Reads, writes, and debugs code with root-cause analysis.
- **Sandboxed Terminal**: Executes system commands safely within the project root.
- **Desktop Control**: Take screenshots, launch apps (Safari, VS Code), and simulate UI interactions (macOS/Linux/Windows).

### ⚡ Performance & Optimization (Lirox Compressor)
- **Stage 1 (GGUF Quantization)**: Native INT4 block quantization for Ollama models.
- **Stage 2 (Inference Patching)**: Injects memory-optimized KV cache and thread capping into the LLM logic.
- **Stage 4 (HF BitsAndBytes)**: Dynamically serves any large Hugging Face model in 4-bit precision via a standalone local API server.

---

## 🛠️ Installation

### 1. Clone & Dependencies
```bash
git clone https://github.com/baljotchohan/Lirox.git
cd Lirox
pip install -r requirements.txt
```

### 2. Environment Setup
```bash
cp .env.example .env
# Open .env and add your API keys (Groq, Gemini, Anthropic, etc.)
```

### 3. Desktop Control (Optional)
```bash
# macOS
pip install pyobjc-framework-Quartz pyautogui
# Linux
sudo apt-get install scrot xdotool
pip install pyautogui
```

---

## 🤖 Specialized Agents

| Agent | Icon | Core Mission |
| :--- | :---: | :--- |
| **Code** | 💻 | Full-stack dev, desktop control, terminal execution, bug fixing. |
| **Research** | 🔬 | Deep-dive synthesis, GitHub trending, news, and complex web crawling. |
| **Finance** | 📊 | Live market data, portfolio analysis, and proactive investment alerts. |
| **Browser** | 🌐 | Visual web navigation and structured data extraction. |
| **Chat** | 💬 | High-speed conversational assistance and general reasoning. |

---

## 🧬 Lirox Model Compressor
Lirox includes a dedicated utility to make high-performance models run on consumer hardware.

```bash
# Check your current system RAM and model status
python3 scripts/compress_model.py --check

# Optimise an Ollama model (llama3) for low RAM
python3 scripts/compress_model.py --stage 1-3 --model llama3

# Run a large Hugging Face model in 4-bit precision via BitsAndBytes
python3 scripts/compress_model.py --stage 4 --hf-model meta-llama/Llama-2-7b-hf
python3 run_hf_bnb.py
```

---

## ⌨️ Professional Commands

| Command | Action |
| :--- | :--- |
| `/mode <mode>` | Switch between `fast`, `think`, or `complex`. |
| `/agent <name>` | Force switch to `code`, `finance`, `research`, etc. |
| `/history` | View persistent session history with auto-generated titles. |
| `/update` | Pull the latest Lirox Beta updates from the repository. |
| `/memory` | Inspect the per-agent memory usage and context window. |
| `/setup` | Re-run the interactive onboarding and provider setup. |
| `/test` | Run a full system diagnostic of logic and tools. |

---

## 🏗️ Architecture
```text
lirox/
├── main.py              # OS Entry & UI Loop
├── orchestrator/        # Master intent routing & logic
├── agents/              # The "Brains" (Code, Finance, Research)
├── thinking/            # Chain-of-Thought & Reflection logic
├── tools/               # System interface (Terminal, Desktop, Search)
├── memory/              # Agent isolation & session persistence
└── utils/               # LLM Provider Layer & Rate Limiting
```

---

## ⚖️ License
Distributed under the **MIT License**. Created by the Lirox Core Team for the next generation of autonomous computing.

---

<p align="center">
  <b>Built for the Elite. Run by the Future.</b><br>
  <i>Lirox — Intelligence as an Operating System.</i>
</p>
