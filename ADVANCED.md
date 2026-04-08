# 🚀 Advanced Features — Lirox

> Deep dive into Lirox's most powerful capabilities.

---

## Table of Contents

1. [Deep Thinking Mode](#deep-thinking-mode)
2. [Multi-Agent Coordination](#multi-agent-coordination)
3. [Custom Skill Development](#custom-skill-development)
4. [Advanced Desktop Control](#advanced-desktop-control)
5. [Performance Optimization](#performance-optimization)
6. [Custom Configuration](#custom-configuration)
7. [LLM Provider Configuration](#llm-provider-configuration)
8. [Security & Privacy](#security--privacy)

---

## Deep Thinking Mode

### Overview

The deep thinking engine applies structured reasoning to complex problems using an 8-phase pipeline.

### The 8 Phases

#### Phase 1: UNDERSTAND
Lirox first clarifies exactly what's being asked:
- Identifies the core question
- Notes ambiguities
- Determines what a complete answer looks like
- Identifies success criteria

#### Phase 2: DECOMPOSE
Breaks the problem into manageable components:
- Identifies sub-problems
- Finds dependencies between components
- Determines which components are most critical
- Creates a problem tree

#### Phase 3: ANALYZE
Deep analysis of each component:
- Researches relevant knowledge
- Applies domain expertise
- Considers edge cases
- Gathers supporting evidence

#### Phase 4: EVALUATE
Scores and compares different approaches:
- Creates evaluation criteria
- Scores each approach (1-10)
- Identifies pros and cons
- Considers context and constraints

#### Phase 5: SIMULATE
Mental model testing:
- Simulates each approach
- Identifies potential failures
- Tests edge cases mentally
- Projects long-term consequences

#### Phase 6: REFINE
Improves the analysis based on simulation:
- Fixes identified weaknesses
- Incorporates simulation insights
- Strengthens the reasoning
- Resolves contradictions

#### Phase 7: PLAN
Structures the final response:
- Organizes information logically
- Creates actionable steps
- Prioritizes key insights
- Formats for clarity

#### Phase 8: VERIFY
Final validation:
- Checks completeness
- Verifies accuracy
- Confirms actionability
- Reviews for gaps

### Using Deep Thinking

```bash
# Basic deep thinking
lirox> /think <query>

# Examples:
lirox> /think What database should I use for a social media app with 10M users?
lirox> /think How do I migrate a monolith to microservices without downtime?
lirox> /think What's the best way to handle state in a React application?
```

### Performance Impact

Deep thinking is slower than standard queries (5-30 seconds vs <1 second) but produces significantly higher quality responses for complex problems.

**Use deep thinking when:**
- Making important technical decisions
- Analyzing complex tradeoffs
- Solving novel problems
- Planning major changes

**Use standard queries when:**
- Simple factual questions
- Code snippets
- Quick lookups
- Conversational exchanges

---

## Multi-Agent Coordination

### Architecture

Lirox can spin up multiple specialized agents and coordinate them to complete complex tasks:

```
Orchestrator Agent
├── Research Agent    → Gathers information
├── Analysis Agent   → Processes information
├── Planning Agent   → Creates action plan
├── Execution Agent  → Implements plan
└── Review Agent     → Validates output
```

### Creating Agent Pipelines

```bash
# Define a workflow
lirox> Create an agent pipeline for writing blog posts:
  1. Research agent: Find latest info on the topic
  2. Outline agent: Create detailed outline
  3. Writing agent: Write each section
  4. Review agent: Edit and improve
  5. SEO agent: Optimize for search

# Run the pipeline
lirox> /pipeline write-blog "The Future of AI in Healthcare"
```

### Agent Communication

Agents can communicate through:
- **Message passing**: Direct messages between agents
- **Shared memory**: Common knowledge base
- **Task delegation**: Parent agents delegate to children
- **Result aggregation**: Combining outputs

### Best Practices

1. **Specialize agents** for specific domains
2. **Define clear interfaces** between agents
3. **Use validation agents** to catch errors
4. **Monitor agent progress** with `/agents status`

---

## Custom Skill Development

### Skill Architecture

Skills are Python modules that Lirox can execute:

```python
# Example skill structure
class MySkill:
    name = "MySkill"
    description = "What this skill does"
    
    def __init__(self, config):
        self.config = config
    
    def execute(self, params: dict) -> dict:
        # Your implementation here
        return {"result": "..."}
```

### Creating Skills Manually

For advanced use cases, create skills directly:

```python
# lirox/skills/my_custom_skill.py

import requests
from typing import Dict, Any

class PriceTrackerSkill:
    """Tracks product prices across multiple retailers."""
    
    name = "PriceTracker"
    description = "Tracks and compares product prices"
    parameters = {
        "product": "str - Product name to search",
        "max_price": "float - Maximum acceptable price"
    }
    
    def execute(self, product: str, max_price: float = None) -> Dict[str, Any]:
        results = {}
        
        # Amazon search
        amazon_price = self._search_amazon(product)
        if amazon_price:
            results["amazon"] = {
                "price": amazon_price,
                "url": f"https://amazon.com/search?q={product}"
            }
        
        # Filter by max price
        if max_price:
            results = {k: v for k, v in results.items() 
                      if v["price"] <= max_price}
        
        return results
    
    def _search_amazon(self, product: str) -> float:
        # Implementation here
        pass
```

### Skill Testing

```bash
# Test your skill
lirox> Use PriceTracker to find iPhone 15 under $800

# Debug mode
lirox> /skill-debug PriceTracker "iPhone 15"
```

### Advanced Skill Features

#### Async Skills

```python
import asyncio

class AsyncWebScraperSkill:
    async def execute(self, urls: list) -> dict:
        tasks = [self._fetch(url) for url in urls]
        results = await asyncio.gather(*tasks)
        return dict(zip(urls, results))
    
    async def _fetch(self, url: str) -> str:
        # Async HTTP request
        pass
```

#### Skills with Memory

```python
class LearningSkill:
    def __init__(self, memory_manager):
        self.memory = memory_manager
    
    def execute(self, query: str) -> dict:
        # Check if we've seen this before
        cached = self.memory.get(f"skill_cache_{query}")
        if cached:
            return cached
        
        # Execute and cache
        result = self._compute(query)
        self.memory.set(f"skill_cache_{query}", result)
        return result
```

---

## Advanced Desktop Control

### Screen Analysis

Lirox can analyze screen content intelligently:

```bash
# Analyze current screen
lirox> What's on my screen right now?
→ I see a browser with Gmail open. You have 3 unread emails.

# Find specific elements
lirox> Find the "Submit" button on this page
→ Found "Submit" button at coordinates (450, 320)

# Read text from screen
lirox> What does the error message say?
→ Error: "Connection refused: localhost:5432"
```

### Window Management

```bash
# List open windows
lirox> /desktop windows
→ 1. VS Code - main.py
→ 2. Terminal - ~/Projects/myapp
→ 3. Chrome - GitHub

# Focus a window
lirox> Focus VS Code
→ VS Code is now in focus

# Arrange windows
lirox> Arrange VS Code and Terminal side by side
```

### Recording Automation

Create reusable automation scripts:

```bash
# Record a workflow
lirox> /record start "daily-standup"
[Perform actions manually]
lirox> /record stop
→ Workflow "daily-standup" saved (12 steps)

# Play back workflow
lirox> /play daily-standup
```

### Computer Vision Features

Lirox uses OCR and vision to:
- Read text in any application
- Identify buttons and form elements
- Navigate complex UIs
- Handle dynamic content

---

## Performance Optimization

### Response Speed

Lirox has a fast-path optimization for simple queries:

```
Query complexity levels:
1. TRIVIAL   → Direct response (<100ms)
2. SIMPLE    → Single LLM call (<500ms)
3. MODERATE  → Brief analysis (<2s)
4. COMPLEX   → Deep thinking (5-30s)
5. TASK      → Multi-step execution (30s-5min)
```

### Configuring Speed

```env
# .env configuration
FAST_PATH_ENABLED=true      # Skip LLM for trivial queries
CACHE_RESPONSES=true        # Cache common responses
PARALLEL_AGENTS=true        # Run agents in parallel
MAX_THINKING_DEPTH=3        # Limit thinking phases (1-8)
```

### Caching

Enable response caching for repeated queries:

```bash
lirox> /settings caching on
→ Response caching enabled. Similar queries will use cached results.
```

### Model Selection for Speed

Different models for different needs:

```
Speed:    Groq Llama-3.3-70b  (fastest, free)
Balance:  GPT-4o-mini          (fast, cheap)
Quality:  GPT-4o / Claude-3.5  (best quality, slower)
Local:    Ollama               (offline, variable speed)
```

---

## Custom Configuration

### Environment Variables

Complete list of configuration options:

```env
# === LLM PROVIDERS ===
GROQ_API_KEY=gsk_...
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...

# === DEFAULT PROVIDER ===
DEFAULT_LLM=groq
DEFAULT_MODEL=llama-3.3-70b-versatile

# === PERFORMANCE ===
FAST_PATH_ENABLED=true
CACHE_RESPONSES=true
RESPONSE_TIMEOUT=30
MAX_RETRIES=3

# === DESKTOP CONTROL ===
DESKTOP_ENABLED=true
SCREEN_FPS=60
SCREENSHOT_QUALITY=85

# === MEMORY ===
MEMORY_ENABLED=true
AUTO_TRAIN=true
TRAIN_AFTER_N_SESSIONS=5
MAX_MEMORY_SIZE_MB=100

# === SECURITY ===
REQUIRE_CONFIRMATION=true
SANDBOX_CODE=true
AUDIT_LOG=true

# === UI ===
THEME=dark
SHOW_THINKING=false
VERBOSE=false
```

### Profile Configuration

The user profile is stored at `data/profile.json`:

```json
{
  "name": "John Smith",
  "role": "Software Engineer",
  "expertise": ["Python", "FastAPI", "PostgreSQL"],
  "communication_style": "technical",
  "response_length": "balanced",
  "timezone": "PST",
  "projects": [
    {
      "name": "API Gateway",
      "status": "active",
      "tech_stack": ["FastAPI", "PostgreSQL", "Redis"]
    }
  ]
}
```

### Custom System Prompts

Create custom system prompts for specialized use:

```json
// data/custom_prompts.json
{
  "code_review": "You are a senior software engineer. Review code for: correctness, performance, security, readability. Always provide specific improvement suggestions.",
  
  "teaching": "You are a patient teacher. Explain concepts with analogies. Check understanding with questions. Build from simple to complex.",
  
  "business": "You are a business analyst. Focus on ROI, timelines, and risk. Use business language. Provide executive summaries."
}
```

---

## LLM Provider Configuration

### Groq (Recommended - Free)

```env
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile
# Available: llama-3.3-70b-versatile, llama-3.1-70b-versatile, mixtral-8x7b-32768
```

### OpenAI

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
# Available: gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo
```

### Anthropic Claude

```env
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
# Available: claude-3-5-sonnet, claude-3-opus, claude-3-haiku
```

### Google Gemini

```env
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-1.5-pro
# Available: gemini-1.5-pro, gemini-1.5-flash, gemini-1.0-pro
```

### Ollama (Local)

```env
LOCAL_LLM_ENABLED=true
OLLAMA_ENDPOINT=http://localhost:11434
OLLAMA_MODEL=llama3.2
# Any model you've pulled with: ollama pull <model>
```

### Provider Fallback

Configure automatic fallback:

```env
LLM_PROVIDERS=groq,openai,ollama
# If Groq fails → try OpenAI → try Ollama
```

---

## Security & Privacy

### Data Privacy

All data stays local by default:

```
Local storage:
  data/profile.json     - Your profile
  data/memory.json      - Learned facts
  data/sessions/        - Session history
  data/skills/          - Custom skills
  data/agents/          - Custom agents

Data sent to providers:
  - Your queries (to LLM API)
  - Context from your profile (configurable)
  
NEVER sent:
  - File contents (unless you paste them)
  - Screen content (unless /screen is active)
  - Passwords or secrets
```

### Audit Logging

Enable detailed audit logging:

```env
AUDIT_LOG=true
AUDIT_LOG_PATH=data/audit.log
```

Log contents:
```
2024-01-15 14:32:01 QUERY      "What is recursion?"
2024-01-15 14:32:02 LLM_CALL   provider=groq, tokens=1234
2024-01-15 14:32:03 RESPONSE   length=456 chars
2024-01-15 14:35:00 DESKTOP    action=screenshot
2024-01-15 14:35:01 DESKTOP    action=click x=450 y=320
```

### Code Sandboxing

Lirox runs generated code in a sandbox:

```env
SANDBOX_CODE=true
SANDBOX_TIMEOUT=30
SANDBOX_MAX_MEMORY_MB=512
SANDBOX_ALLOW_NETWORK=false  # Restrict network in sandbox
SANDBOX_ALLOW_FILES=true
```

### Confirmation Required

For sensitive operations, Lirox asks for confirmation:

```env
REQUIRE_CONFIRMATION=true
CONFIRM_FILE_WRITE=true
CONFIRM_DESKTOP_CONTROL=true
CONFIRM_CODE_EXECUTION=true
```

---

*For getting started, see [USE_LIROX.md](USE_LIROX.md). For command reference, see [COMMANDS.md](COMMANDS.md).*

**Made with ❤️ by [Baljot Singh](https://github.com/baljotchohan)**
