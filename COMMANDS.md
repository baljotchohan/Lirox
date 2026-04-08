# 📋 Lirox Commands Reference

> Complete reference for all Lirox commands, syntax, and examples.

---

## Table of Contents

1. [Query Commands](#query-commands)
2. [Agent Commands](#agent-commands)
3. [Skill Commands](#skill-commands)
4. [Desktop Commands](#desktop-commands)
5. [Memory Commands](#memory-commands)
6. [Configuration Commands](#configuration-commands)
7. [System Commands](#system-commands)
8. [Advanced Usage](#advanced-usage)

---

## Query Commands

### Direct Query

Type any question or request directly.

**Syntax:** `<your question or request>`

**Examples:**
```
lirox> What is recursion?
lirox> Write me a haiku about coding
lirox> Summarize the SOLID principles
lirox> Explain Big O notation with examples
```

---

### `/think`

Activates 8-phase deep reasoning for complex problems.

**Syntax:** `/think <query>`

**Examples:**
```
lirox> /think What's the best architecture for a real-time chat app?
lirox> /think How do I scale my PostgreSQL database to handle 1M users?
lirox> /think Should I use REST or GraphQL for my new API?
```

**When to use:**
- Architecture decisions
- Technical tradeoffs
- Complex problem solving
- Research synthesis
- Strategic planning

**What happens:**
```
Activating deep reasoning...

Phase 1: UNDERSTAND  ✓ Clarifying the core question
Phase 2: DECOMPOSE   ✓ Breaking into sub-problems
Phase 3: ANALYZE     ✓ Researching each component
Phase 4: EVALUATE    ✓ Scoring each approach
Phase 5: SIMULATE    ✓ Running mental models
Phase 6: REFINE      ✓ Improving the analysis
Phase 7: PLAN        ✓ Structuring the response
Phase 8: VERIFY      ✓ Checking completeness

[Comprehensive, well-reasoned response]
```

---

### `/task`

Executes a multi-step task with planning and validation.

**Syntax:** `/task <description>`

**Examples:**
```
lirox> /task Build a Python web scraper for Amazon product prices
lirox> /task Create a REST API with authentication using FastAPI
lirox> /task Set up a CI/CD pipeline for my GitHub repository
```

**What happens:**
```
Planning task: "Build a Python web scraper..."

Task Plan:
1. Understand requirements
2. Design architecture
3. Install dependencies
4. Implement core scraper
5. Add error handling
6. Test with sample URLs
7. Document the code

Proceed? (yes/no) → yes
Executing...
```

---

## Agent Commands

### `/add-agent`

Interactive wizard to create a custom AI agent.

**Syntax:** `/add-agent`

**Process:**
```
lirox> /add-agent

Agent Creation Wizard
─────────────────────
Name: ResearchBot
Specialization: Academic research and literature review
Tools needed: Google Scholar, arXiv, Wikipedia
Response format: Structured with citations
Communication style: Academic, formal

Creating agent...
✅ Agent "ResearchBot" created!
```

---

### `/agents`

Lists all available agents (built-in and custom).

**Syntax:** `/agents`

**Output:**
```
Available Agents
────────────────
Built-in:
  • default      - General purpose assistant (active)
  • coder        - Code generation and review
  • analyst      - Data analysis and insights

Custom:
  • ResearchBot  - Academic research
  • EmailHelper  - Email drafting
  • DocWriter    - Documentation

Total: 6 agents
Use: /agent <name> to switch
```

---

### `/agent`

Switches to a specific agent.

**Syntax:** `/agent <name>`

**Examples:**
```
lirox> /agent ResearchBot
✅ Switched to ResearchBot

lirox> /agent default
✅ Switched to default agent
```

---

### `/remove-agent`

Permanently deletes a custom agent.

**Syntax:** `/remove-agent <name>`

**Examples:**
```
lirox> /remove-agent ResearchBot
⚠️  Delete agent "ResearchBot"? (yes/no) → yes
✅ Agent "ResearchBot" removed.
```

---

## Skill Commands

### `/add-skill`

Interactive wizard to create a custom skill (Python function).

**Syntax:** `/add-skill`

**Process:**
```
lirox> /add-skill

Skill Creation Wizard
─────────────────────
Name: PriceChecker
Description: Check product prices on Amazon and eBay
Parameters: product_name (str), max_price (float)
Returns: JSON with prices and links
Dependencies: requests, beautifulsoup4

Generating skill code...
✅ Skill "PriceChecker" created at lirox/skills/price_checker.py
```

---

### `/skills`

Lists all available skills.

**Syntax:** `/skills`

**Output:**
```
Available Skills
─────────────────
Built-in:
  • file_reader     - Read and analyze files
  • web_search      - Search the internet
  • code_executor   - Run Python code safely
  • system_info     - Get system information

Custom:
  • PriceChecker    - Compare prices
  • WeatherFetcher  - Get weather data
  • EmailSender     - Send emails

Total: 7 skills
Use: "Use [SkillName] to [task]" to run
```

---

### `/remove-skill`

Permanently deletes a custom skill.

**Syntax:** `/remove-skill <name>`

**Examples:**
```
lirox> /remove-skill PriceChecker
⚠️  Delete skill "PriceChecker"? (yes/no) → yes
✅ Skill "PriceChecker" removed.
```

---

## Desktop Commands

### `/screen`

Enables screen mirroring and desktop control.

**Syntax:** `/screen`

**Effect:**
```
lirox> /screen

Screen mirroring enabled ✅
• Your desktop is now visible to Lirox
• Lirox can see and interact with windows
• Glowing border indicates agent control mode
• Press ESC to stop at any time
```

**Requirements:**
- `DESKTOP_ENABLED=true` in `.env`
- pyautogui and pillow installed
- Accessibility permissions granted (macOS)

---

### `/freeze`

Freezes the desktop to prevent user interference during automation.

**Syntax:** `/freeze`

**Effect:**
```
lirox> /freeze
⚠️  Desktop frozen - agent has exclusive control
Press ESC to emergency stop
```

---

### `/unfreeze`

Restores normal desktop control to the user.

**Syntax:** `/unfreeze`

**Effect:**
```
lirox> /unfreeze
✅ Desktop control returned to you
```

---

### `/desktop`

Shows desktop control status and configuration.

**Syntax:** `/desktop`

**Output:**
```
Desktop Control Status
──────────────────────
Status: Enabled ✅
Screen mirroring: Active
Resolution: 2560 x 1440
FPS: 60
Last screenshot: 0.2s ago
Pending actions: 0

Capabilities:
  ✅ Screenshot capture
  ✅ Mouse control
  ✅ Keyboard input
  ✅ Window management
  ✅ Text recognition (OCR)
```

---

## Memory Commands

### `/train`

Analyzes recent sessions and extracts learnings about you.

**Syntax:** `/train`

**Effect:**
```
lirox> /train

Analyzing recent sessions...

Sessions analyzed: 12
New facts learned:
  ✅ You use Docker for development
  ✅ You prefer type hints in Python
  ✅ You work on a Mac with M2 chip
  ✅ Your main project is a FastAPI backend
  
Updated preferences:
  ✅ Response format → code examples preferred
  ✅ Explanation depth → technical details

Training complete! Lirox is now more personalized.
```

---

### `/memory`

Shows memory statistics and storage information.

**Syntax:** `/memory`

**Output:**
```
Memory Overview
───────────────
Total facts: 127
Facts added this week: 12
Sessions remembered: 45
Memory file size: 14KB

Memory breakdown:
  Profile facts:      23
  Project facts:      34
  Preference facts:   28
  Technical facts:    42
```

---

### `/learnings`

Displays all facts Lirox has learned about you.

**Syntax:** `/learnings`

**Output:**
```
What Lirox knows about you
───────────────────────────
Identity:
  • Name: John Smith
  • Role: Senior Software Engineer
  • Company: TechCorp (optional)

Technical Profile:
  • Primary language: Python
  • Secondary: JavaScript, Go
  • Tools: VS Code, Docker, k8s
  • OS: macOS (Apple Silicon)

Projects:
  • API Gateway redesign (active)
  • ML pipeline for recommendations (planning)

Preferences:
  • Communication: Direct, technical
  • Code style: PEP8, type hints
  • Response length: Detailed for complex, concise for simple
```

---

### `/forget`

Removes a specific fact from memory.

**Syntax:** `/forget <fact>`

**Examples:**
```
lirox> /forget "I work at TechCorp"
✅ Fact removed: "I work at TechCorp"

lirox> /forget my email address
✅ Email address removed from memory
```

---

### `/reset`

Clears all memory. Use with caution!

**Syntax:** `/reset`

**Effect:**
```
lirox> /reset

⚠️  WARNING: This will permanently delete ALL memory including:
  - Your profile
  - All learned facts
  - Session history
  - Custom preferences

This cannot be undone. Are you sure? (type "yes I am sure") →
```

---

## Configuration Commands

### `/profile`

Displays your current user profile.

**Syntax:** `/profile`

**Output:**
```
Your Lirox Profile
──────────────────
Name: John Smith
Role: Software Engineer
Created: 2024-01-15
Sessions: 45
Last active: Today

Preferences:
  Communication style: Technical
  Response length: Balanced
  Response format: Code-first
  Learning: Enabled
  Desktop control: Enabled

API providers configured: 2
  ✅ Groq (active)
  ✅ OpenAI (fallback)
```

---

### `/settings`

Opens the interactive settings editor.

**Syntax:** `/settings`

**Options:**
```
lirox> /settings

Settings
─────────
1. Communication style  [technical]
2. Response length      [balanced]
3. Response format      [code-first]
4. Learning mode        [enabled]
5. Desktop control      [enabled]
6. Auto-save sessions   [yes]
7. Language             [English]
8. API provider         [groq]

Enter number to change, or 'q' to quit:
```

---

### `/models`

Shows available LLM providers and their status.

**Syntax:** `/models`

**Output:**
```
Available LLM Providers
────────────────────────
✅ Groq          (active)  - llama-3.3-70b-versatile
✅ OpenAI        (ready)   - gpt-4o
❌ Anthropic     (no key)  - claude-3-5-sonnet
❌ Gemini        (no key)  - gemini-1.5-pro
❌ Ollama        (offline) - local model

Switch with: /model <provider>
```

---

### `/help`

Displays all available commands.

**Syntax:** `/help`

**Options:**
```
lirox> /help
lirox> /help agents     - Show agent commands
lirox> /help skills     - Show skill commands
lirox> /help desktop    - Show desktop commands
lirox> /help memory     - Show memory commands
```

---

### `/history`

Shows session history.

**Syntax:** `/history [n]`

**Examples:**
```
lirox> /history         - Show last 5 sessions
lirox> /history 10      - Show last 10 sessions
lirox> /history today   - Show today's sessions
lirox> /history week    - Show this week's sessions
```

**Output:**
```
Recent Sessions
───────────────
Today:
  14:32 - "Help me debug my FastAPI middleware"   [45min]
  11:15 - "Generate unit tests for auth module"   [22min]

Yesterday:
  16:45 - "Design database schema for social app" [1h 10min]
  09:30 - "Code review: PR #127"                  [15min]
```

---

## System Commands

### `/restart`

Cleanly restarts Lirox, reloading all configuration.

**Syntax:** `/restart`

**Effect:**
```
lirox> /restart
Saving session...
Restarting Lirox...
[Lirox restarts with fresh state, memory preserved]
```

---

### `/update`

Updates Lirox to the latest version.

**Syntax:** `/update`

**Effect:**
```
lirox> /update
Checking for updates...
Current version: 1.0.0
Latest version: 1.1.0

Changes in v1.1.0:
  - Multi-agent coordination
  - Improved memory system
  - Faster response times

Update now? (yes/no) → yes
Updating...
✅ Updated to v1.1.0. Restart to apply changes.
```

---

### `/exit` / `quit`

Gracefully shuts down Lirox.

**Syntax:** `/exit` or `quit`

**Effect:**
```
lirox> /exit
Saving session...
Saving memory...
Goodbye, John! See you next time. 👋
```

---

## Advanced Usage

### Command Chaining

Run multiple commands in sequence:

```
lirox> /screen && /freeze && Fill out the form && /unfreeze
```

### Piping Output

Send command output to files:

```
lirox> /history > my_sessions.txt
lirox> /learnings > my_profile.txt
```

### Agent Targeting

Direct a message to a specific agent:

```
lirox> @ResearchBot What are the latest papers on diffusion models?
lirox> @CodeReviewer Review this function: [paste code]
lirox> @DocWriter Write docstrings for: [paste code]
```

### Conditional Commands

```
lirox> If Python, use FastAPI. If JavaScript, use Express. Build a REST API.
```

### Batch Processing

```
lirox> Process all .py files in /my/project and generate docstrings
lirox> Review all PRs in my GitHub repo from last week
```

---

*For more information, see [USE_LIROX.md](USE_LIROX.md) and [ADVANCED.md](ADVANCED.md)*

**Made with ❤️ by [Baljot Singh](https://github.com/baljotchohan)**
