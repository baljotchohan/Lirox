# 🦁 Lirox Agent OS (v0.8)
### *The Autonomous Professional Research Engine*

[![Status](https://img.shields.io/badge/Status-Autonomous-FFC107?style=flat-square)](https://github.com/baljotchohan/Lirox)
[![Version](https://img.shields.io/badge/Version-v0.8-white?style=flat-square)](https://github.com/baljotchohan/Lirox)
[![Platform](https://img.shields.io/badge/Platform-macOS-black?style=flat-square)](https://github.com/baljotchohan/Lirox)

**Lirox** is a local-first autonomous AI agent OS designed for high-fidelity research and secure system orchestration. Powered by a modular kernel architecture, it transforms standard LLMs into professional operators capable of deep web research, real-time data verification, and sophisticated multi-step task execution.

---

## 🏛️ Autonomous Architecture

```mermaid
graph TD
    User([Operator Input]) --> Intent[Intent Router]
    Intent --> Planner[Planner: Strategic Wave Decomposition]
    Planner --> Executor[Executor: Hardened Orchestration]
    Executor --> Tools{Security Sandbox}
    
    Tools --> Browser[Browser: Headless CDP / Requests]
    Tools --> Terminal[Terminal: Safe System Access]
    Tools --> FileIO[FileIO: Local Data Control]
    
    Browser --> Researcher[Researcher: Verify-and-Retry]
    Researcher --> Synthesis[Synthesis: Cited Fact Reporting]
    Synthesis --> Executor
    
    Executor --> Loop{Goal Achieved?}
    Loop -- No --> Planner
    Loop -- Yes --> Result([Mission Complete])

    subgraph "Persistent Core"
        Memory[(Neural Memory)]
        Profile[(Operator Context)]
    end
    
    Planner -.-> Memory
    Executor -.-> Memory
```

---

## 🧠 Unified Executor & Smart Routing (v0.8)
Lirox v0.8 replaces static command processing with a **Unified Executor** powered by a **Smart Router**. It seamlessly categorizes queries and selects the optimal execution path.

```mermaid
flowchart TD
    Input([User Query]) --> Router{Smart Router}
    Router -- Chat --> LLM[Direct Response]
    Router -- Research --> RE[Deep Research Synthesis]
    Router -- Browser --> BE[Headless Page Scraping]
    Router -- Hybrid --> HB[Research + Verification]

    RE --> DE[Data Enrichment Engine]
    HB --> DE
    
    DE --> RF[Response Formatter]
    LLM --> RF
    BE --> RF
    RF --> Output([Structured Result])
```

## 🛡️ Professional-Grade Verification
Lirox v0.8 expands on "Verify-and-Retry" logic with the new **Data Enrichment Engine**, ensuring financial and real-time data is natively checked against actual web content. Unlike generic agents, Lirox does not just summarize; it **extracts and validates**.

### Data Verification Flow
```mermaid
sequenceDiagram
    participant E as Executor
    participant B as Browser Tool
    participant S as Search Engine
    participant P as Reliable Source (e.g. Yahoo Finance)

    E->>B: Lookup "current BTC price"
    B->>S: Search for "current BTC price"
    S-->>B: Return Top 5 Results
    B->>P: Fetch Raw HTML (Source #1)
    P-->>B: Return Data
    Note over B: SmartExtractor scans for numeric patterns
    alt Valid Data Found
        B-->>E: Return Verified Data Spot
    else Generic/Empty Snippet
        B->>B: Trigger Autonomous Retry
        B->>S: Search for "BTC real-time value"
        S-->>B: Return New Results
        B->>P: Re-scan Deep Content
        B-->>E: Return Best Verified Result
    end
```

---

## ✨ Premium Features

| **Feature** | **Description** |
| :--- | :--- |
| **🕵️ Deep Research** | Perplexity-grade parallel search with auto-deduplication and source quality scoring. |
| **🛡️ Hardened Sandbox** | Zero-trust execution environment with SSRF prevention and terminal safe-guards. |
| **🌐 Headless Browser** | Full JavaScript rendering via Lightpanda CDP bridge with session pooling. |
| **🧠 Phase Reasoning** | Analysis, Logic, and Risk strategy traces for every major mission. |
| **📁 Advanced FileIO** | High-efficiency codebase management and data persistence. |
| **🦁 Personal Logic** | Adapts to your niche and operator style over time using persistent profile storage. |

---

## 🚀 Quick Start

### 1. Clone & Prep
```bash
git clone https://github.com/baljotchohan/Lirox.git
cd Lirox
python -m pip install -r requirements.txt
```

### 2. Configure Your Arsenal
Prepare your `.env` with at least one LLM key (Gemini, Groq, Anthropic, or OpenAI):
```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY / ANTHROPIC_API_KEY
```

### 3. Launch the Kernel
```bash
python -m lirox.main
```

---

## 🖥️ Professional Toolset

| **Command** | **Action** |
| :--- | :--- |
| `/research "Q"` | Multi-source deep research with citation reporting. |
| `/fetch <url>` | Fetch page content using headless browser or requests fallback. |
| `/scrape <url>` | Extract structured tables and links from a live page. |
| `/profile` | Inspect the agent's learned identity and your operator context. |
| `/test` | Run kernel performance and hardware diagnostics. |
| `/update` | Synchronize your local kernel with the latest stable branch. |

---

## 🌐 Browser & Real-Time Data

Lirox v0.7.1 features a high-performance, secure browser engine that operates in two distinct modes. This hybrid architecture ensures that the agent can scrape data from simple static pages and complex interactive web apps alike.

### Hybrid Engine Comparison

| Feature | **HTTP Logic (Requests)** | **Headless CDP (Lightpanda)** |
| :--- | :--- | :--- |
| **Speed** | ⚡ Ultra Fast (< 500ms) | 🐢 Moderate (2s - 5s) |
| **JS Rendering** | ❌ No | ✅ Yes (Full Engine) |
| **Bypass Blocks** | ✅ Excellent (Native SSL) | ⚠️ Moderate (Can be detected) |
| **Portability** | ✅ Runs Everywhere | 🛠️ Requires Binary |
| **Security** | 🛡️ SSRF Blocklist | 🛡️ CDP Isolation |

### Professional Data Extraction
Lirox doesn't just read text; it **understands data structures**. The `RealTimeDataExtractor` engine is optimized for:
- **Financial Metrics**: BTC/ETH prices, Stock tickers (AAPL, TSLA), and Forex rates.
- **News Aggregation**: Harvesting titles, points, and timestamps from sources like **Hacker News** and **Wikipedia**.
- **Market Sentiment**: Detecting percentage changes and volatility indicators directly from the source HTML.

---

## 🏛️ Local-First Reliability
- **Local Memory**: Your conversation history and profiles never leave your machine.
- **Zero-Cloud Logic**: Strategy and planning are executed locally.
- **Privacy Design**: Built strictly for outbound-only ingestion; Lirox never broadcasts your local data.

---

Built with ❤️ by **Baljot Chohan & Antigravity**.  
*Lirox — Empowering the next generation of autonomous operators.*
