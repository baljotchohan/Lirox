# 📖 How to Use Lirox — Complete Guide

> The definitive guide for getting the most out of Lirox, your autonomous AI agent.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Basic Queries](#basic-queries)
3. [Advanced Features](#advanced-features)
4. [Agent Creation](#agent-creation)
5. [Skill Creation](#skill-creation)
6. [Desktop Control](#desktop-control)
7. [Memory & Learning](#memory--learning)
8. [Tips & Tricks](#tips--tricks)
9. [FAQ](#faq)

---

## Getting Started

### Prerequisites

Before using Lirox, make sure you have:
- Python 3.8 or higher
- At least one API key (Groq is free and recommended)
- pip package manager

### Installation

```bash
# Step 1: Clone the repository
git clone https://github.com/baljotchohan/Lirox.git
cd Lirox

# Step 2: Install dependencies
pip install -r requirements.txt

# Step 3: Set up API keys
echo "GROQ_API_KEY=your_key_here" > .env
# Edit .env and add your preferred API key

# Step 4: Launch Lirox
lirox
```

### First-Time Setup

On first launch, Lirox runs a setup wizard:

```
Welcome to Lirox v1.0.0!

Let me learn about you:
1. What is your name? → John
2. What do you do for work? → Software Engineer
3. What are your main goals? → Build AI applications
4. Preferred communication style? → Technical
5. Response length preference? → Balanced

✅ Profile created! Lirox is now personalized for you.
```

### API Key Setup

Get a **free** Groq API key (recommended):
1. Go to https://console.groq.com
2. Sign up for free
3. Create an API key
4. Add to `.env`: `GROQ_API_KEY=your_key_here`

---

## Basic Queries

### Simple Questions

Just type your question naturally:

```
lirox> What is machine learning?
lirox> How do I reverse a string in Python?
lirox> What's the capital of France?
lirox> Explain quantum entanglement simply
```

### Tasks

Ask Lirox to do things:

```
lirox> Write a Python function to sort a list
lirox> Create a summary of my last 5 sessions
lirox> Help me debug this code: [paste code]
lirox> Translate this to Spanish: Hello World
```

### Multi-line Input

For longer inputs, use the multi-line mode:

```
lirox> """
Here is my code that has a bug:

def calculate_average(numbers):
    return sum(numbers) / len(numbers)

# It crashes on empty lists
"""
```

### Referencing Files

```
lirox> Read file: /path/to/my/code.py and explain what it does
lirox> Analyze /home/user/data.csv and find trends
```

---

## Advanced Features

### Deep Thinking Mode

Use `/think` for complex problems that require careful reasoning:

```
lirox> /think Should I use microservices or monolith for my startup?

Lirox applies 8-phase reasoning:
Phase 1: UNDERSTAND - Clarifying the question
Phase 2: DECOMPOSE  - Breaking into components
Phase 3: ANALYZE    - Researching each component
Phase 4: EVALUATE   - Scoring approaches
Phase 5: SIMULATE   - Testing scenarios
Phase 6: REFINE     - Improving reasoning
Phase 7: PLAN       - Structuring the answer
Phase 8: VERIFY     - Validating completeness

[Detailed, nuanced response follows]
```

Best used for:
- Architecture decisions
- Strategy planning
- Complex debugging
- Research synthesis
- Risk analysis

### Task Mode

Use `/task` for multi-step tasks that require planning:

```
lirox> /task Build me a web scraper for job listings

Lirox will:
1. Ask clarifying questions
2. Plan the implementation
3. Write the code step by step
4. Test each component
5. Provide complete, working solution
```

### Conversation Context

Lirox remembers the current conversation:

```
lirox> I'm building a REST API in Python
lirox> What framework should I use?  [Lirox knows it's Python]
lirox> How do I handle authentication?  [Lirox knows context]
lirox> Show me an example endpoint  [Lirox maintains context]
```

### Quick Commands

Single-line commands for common operations:

```
lirox> /history          - Show recent sessions
lirox> /history 10       - Show last 10 sessions
lirox> /profile          - View your profile
lirox> /models           - List available AI models
lirox> /help             - Show all commands
```

---

## Agent Creation

### Why Create Custom Agents?

Custom agents are specialized AI personas optimized for specific tasks. They have:
- Custom instructions and knowledge
- Specific response formats
- Specialized capabilities
- Custom personalities

### Creating Your First Agent

```
lirox> /add-agent

Starting Agent Creation Wizard...

Step 1/6: What should we call this agent?
→ ResearchBot

Step 2/6: What does this agent specialize in?
→ Deep web research and academic paper analysis

Step 3/6: What APIs or tools does it need?
→ Google Search, Wikipedia, arXiv

Step 4/6: How should it format responses?
→ Structured reports with citations and confidence scores

Step 5/6: What's its communication style?
→ Academic, thorough, cite sources

Step 6/6: Any additional instructions?
→ Always verify information from multiple sources

✅ Agent "ResearchBot" created successfully!

You can now use it with: @ResearchBot [your query]
```

### Using Custom Agents

```
lirox> @ResearchBot What are the latest advances in transformer architectures?

[ResearchBot provides academic-style response with citations]

lirox> @ResearchBot Compare BERT vs GPT architectures

[ResearchBot provides structured comparison with sources]
```

### Managing Agents

```
lirox> /agents              - List all agents
lirox> /agent ResearchBot   - Switch to ResearchBot
lirox> /remove-agent ResearchBot  - Delete agent
```

### Built-in Agent Types

Lirox comes with several pre-configured agent templates:

| Template | Best For |
|----------|----------|
| `CodeReviewer` | Code analysis and review |
| `DataAnalyst` | Data analysis and visualization |
| `ContentWriter` | Writing and editing |
| `DebugHelper` | Debugging and error analysis |
| `ProjectManager` | Project planning and tracking |

---

## Skill Creation

### What Are Skills?

Skills are Python functions that Lirox can execute. They extend Lirox's capabilities beyond language tasks to real actions like:
- Web scraping
- API calls
- File operations
- Data processing
- System interactions

### Creating a Skill

```
lirox> /add-skill

Starting Skill Creation Wizard...

Step 1/5: What should we call this skill?
→ WeatherFetcher

Step 2/5: What does this skill do?
→ Fetches current weather for any city

Step 3/5: What are the input parameters?
→ city (string): The city name
→ units (string, optional): celsius or fahrenheit

Step 4/5: What does it return?
→ JSON with temperature, conditions, humidity, forecast

Step 5/5: Any dependencies needed?
→ requests

Generating skill code...

✅ Skill "WeatherFetcher" created at lirox/skills/weather_fetcher.py

You can now use it: Use WeatherFetcher to get weather in Paris
```

### Using Skills

```
lirox> Use WeatherFetcher to get weather in Tokyo
→ Weather in Tokyo: 22°C, Partly cloudy, 65% humidity

lirox> Use WeatherFetcher for Paris in celsius
→ Weather in Paris: 18°C, Rainy, 80% humidity
```

### Viewing Skills

```
lirox> /skills

Available Skills:
1. WeatherFetcher  - Fetches weather for any city
2. PriceChecker   - Compares prices across stores
3. FileOrganizer  - Organizes files by type/date
4. EmailSender    - Sends emails via SMTP
5. CalendarSync   - Syncs with Google Calendar

Type: Use [SkillName] to [task] to use any skill
```

---

## Desktop Control

### Overview

Lirox can control your desktop to:
- Open and interact with applications
- Fill forms and navigate websites
- Automate repetitive GUI tasks
- Take and analyze screenshots

### Setup

```bash
# Install required packages
pip install pyautogui pillow pytesseract

# macOS: Grant permissions
System Settings → Privacy & Security → Accessibility → Terminal ✓
System Settings → Privacy & Security → Screen Recording → Terminal ✓

# Linux: Install dependencies
sudo apt install scrot xdotool tesseract-ocr

# Windows: No additional setup needed
```

### Enable Desktop Control

```bash
# Add to .env file
DESKTOP_ENABLED=true
```

### Using Desktop Control

#### Screen Mirroring

```
lirox> /screen
→ Screen mirroring enabled
→ Your desktop is now visible in Lirox
→ Agent can see and interact with your screen
```

#### Giving Desktop Tasks

```
lirox> Open Firefox and navigate to github.com
→ Opening Firefox...
→ Navigating to github.com...
→ Done ✅

lirox> Click on the "Sign In" button
→ Locating "Sign In" button...
→ Clicking...
→ Done ✅

lirox> Fill in the form with my name "John Smith"
→ Finding name field...
→ Typing "John Smith"...
→ Done ✅
```

#### Automating Complex Tasks

```
lirox> /task Automate my daily standup report

Lirox will:
1. Open your project management tool
2. Find tasks completed yesterday
3. Find tasks for today
4. Open Slack
5. Post standup update
6. Confirm posted

Type 'approve' to proceed with each step
```

### Safety Features

- **ESC key**: Emergency stop at any time
- **Confirmation prompts**: Lirox asks before destructive actions
- **Action log**: Every action is logged to `data/desktop.log`
- **Undo capability**: Recent actions can be undone

---

## Memory & Learning

### How Memory Works

Lirox has multiple memory layers:

```
Short-term Memory  → Current conversation context
Session Memory     → Current session facts and decisions
Long-term Memory   → Your profile, preferences, patterns
Skill Memory       → Learned procedures and workflows
```

### Training Lirox

```
lirox> /train

Starting training from recent sessions...

Extracting learnings:
✅ Your name: John Smith
✅ Profession: Software Engineer at TechCorp
✅ Main language: Python (preferred)
✅ Working hours: 9am-6pm PST
✅ Communication style: Direct, technical
✅ Current projects: API redesign, ML pipeline
✅ Tools you use: VS Code, Docker, Kubernetes
✅ Learning goals: Improve ML skills

Training complete! 8 new facts learned.
Lirox is now more personalized to you.
```

### Viewing Memory

```
lirox> /memory

Memory Statistics:
- Total facts: 127
- Facts this week: 8
- Session count: 45
- Memory size: 12KB

lirox> /learnings

What Lirox knows about you:
1. You are a Software Engineer
2. You prefer Python over JavaScript
3. You work on ML projects
4. You like concise, technical answers
5. Your timezone is PST
[...]
```

### Managing Memory

```
lirox> /forget "I work at TechCorp"
→ Fact removed from memory

lirox> /reset
→ ⚠️  This will clear ALL memory. Are you sure? (yes/no)
→ yes
→ Memory cleared. Starting fresh.
```

---

## Tips & Tricks

### 1. Be Specific in Requests

```
# Less effective:
lirox> Help with Python

# More effective:
lirox> I have a Python list of dictionaries and need to sort by a nested key. Show me 3 different approaches with performance comparison.
```

### 2. Use Context Stacking

```
lirox> I'm building a FastAPI application
lirox> It needs JWT authentication
lirox> The users table has: id, email, password_hash, created_at
lirox> Now generate the auth endpoints

[Lirox uses all context to generate perfect code]
```

### 3. Iterate with Lirox

```
lirox> Generate a regex for email validation
[Lirox provides regex]

lirox> That doesn't handle internationalized domains. Fix it.
[Lirox refines]

lirox> Now add support for subdomains
[Lirox iterates again]
```

### 4. Use Deep Thinking for Important Decisions

```
lirox> /think What database should I use for a high-traffic social media app?
[Lirox thinks through: PostgreSQL vs MongoDB vs Cassandra vs Redis combinations]
```

### 5. Create Reusable Skills for Repetitive Tasks

```
# Instead of asking the same thing repeatedly:
lirox> /add-skill  → "DailyReport" skill that compiles daily metrics

# Then just run:
lirox> Run DailyReport
```

### 6. Leverage Agent Specialization

```
# Create agents for your specific workflow:
lirox> /add-agent  → "PRReviewer" for code review
lirox> /add-agent  → "DocWriter" for documentation
lirox> /add-agent  → "TestWriter" for unit tests

# Use them in sequence:
lirox> @PRReviewer review this PR: [paste diff]
lirox> @TestWriter write tests for the approved changes
lirox> @DocWriter document the new feature
```

### 7. Export and Backup Your Configuration

```
lirox> Export my profile, agents, and skills to backup.zip
→ Exporting...
→ Saved to backup.zip ✅
```

---

## FAQ

### Q: Does Lirox require internet?
**A:** Only if you use cloud LLM providers (Groq, OpenAI, etc.). With Ollama, Lirox works completely offline.

### Q: Is my data private?
**A:** All memory and profile data is stored locally on your machine. Data is only sent to LLM providers for generating responses.

### Q: Can Lirox break my computer?
**A:** Lirox has safety checks and confirmation prompts for potentially dangerous actions. However, always review desktop automation tasks before approving them.

### Q: How do I update Lirox?
**A:** Run `lirox> /update` or `git pull && pip install -e .`

### Q: Can I use multiple AI providers?
**A:** Yes! Lirox supports Groq, OpenAI, Anthropic, Google Gemini, and Ollama simultaneously. Use `/models` to switch.

### Q: How much does it cost?
**A:** Lirox itself is free. You pay for API usage to your chosen LLM provider. Groq has a generous free tier.

### Q: Can I contribute to Lirox?
**A:** Yes! See [CONTRIBUTING.md](CONTRIBUTING.md) for how to get involved.

### Q: The agent seems slow. How do I speed it up?
**A:** Try using Groq (fastest), or enable fast-path mode for simple queries. See [ADVANCED.md](ADVANCED.md) for performance optimization.

### Q: How do I backup my data?
**A:** Your data is in the `data/` directory. Back it up with: `cp -r data/ data_backup_$(date +%Y%m%d)/`

### Q: Can Lirox learn from my code repositories?
**A:** Yes! Point Lirox to your repos with `/train --repo /path/to/repo` and it will learn your coding style.

---

*For more details, see [ADVANCED.md](ADVANCED.md) and [COMMANDS.md](COMMANDS.md)*

**Made with ❤️ by [Baljot Singh](https://github.com/baljotchohan)**
