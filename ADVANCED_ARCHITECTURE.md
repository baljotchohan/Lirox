# LIROX v2.0 — Advanced Autonomous Agent System Architecture

## Overview

LIROX v2.0 is a multi-layer autonomous AI agent system designed for deep reasoning, bulletproof execution, continuous learning, and bank-grade security. The architecture is organized into 10 independent but interconnected layers.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    LIROX v2.0 ARCHITECTURE                     │
├──────────────────────┬──────────────────────────────────────────┤
│  LAYER 1             │  Advanced Reasoning Engine               │
│  lirox/thinking/     │  Multi-phase deep reasoning (8 phases)   │
├──────────────────────┼──────────────────────────────────────────┤
│  LAYER 2             │  Perfect Executor                        │
│  lirox/execution/    │  Pre-flight checks, sandboxed exec       │
├──────────────────────┼──────────────────────────────────────────┤
│  LAYER 3             │  Perfect File I/O                        │
│  lirox/io/           │  Atomic writes, backup, hash validation  │
├──────────────────────┼──────────────────────────────────────────┤
│  LAYER 4             │  Agent Factory + Specialized Agents      │
│  lirox/agents/       │  Dynamic agent creation, delegation      │
├──────────────────────┼──────────────────────────────────────────┤
│  LAYER 5             │  Self-Learning System                    │
│  lirox/learning/     │  Learns from every execution             │
├──────────────────────┼──────────────────────────────────────────┤
│  LAYER 6             │  Advanced Desktop Controller             │
│  lirox/desktop/      │  Screenshot, OCR, intelligent clicking   │
├──────────────────────┼──────────────────────────────────────────┤
│  LAYER 7             │  Advanced Security System                │
│  lirox/security/     │  5-level permission system, audit log    │
├──────────────────────┼──────────────────────────────────────────┤
│  LAYER 8             │  Task Planner                            │
│  lirox/planning/     │  8-phase autonomous task planning        │
├──────────────────────┼──────────────────────────────────────────┤
│  LAYER 9             │  Agent Swarm                             │
│  lirox/swarms/       │  Parallel agent coordination             │
├──────────────────────┼──────────────────────────────────────────┤
│  LAYER 10            │  Self-Modifying Agent                    │
│  lirox/meta/         │  Code analysis and self-improvement      │
└──────────────────────┴──────────────────────────────────────────┘
```

---

## Layer Details

### Layer 1 — Advanced Reasoning Engine
**Module:** `lirox/thinking/advanced_reasoning.py`

Performs multi-phase deep reasoning:

1. **UNDERSTAND** — Parse requirements, identify goals, constraints, unknowns, and risks
2. **DECOMPOSE** — Break task into atomic, independently-solvable subtasks
3. **ANALYZE** — Generate 3–5 distinct strategies
4. **EVALUATE** — Score strategies by feasibility, risk, time
5. **SIMULATE** — Predict failure modes via mental models
6. **REFINE** — Generate self-corrections for predicted failures
7. **PLAN** — Create concrete, executable step list
8. **VERIFY** — Validate plan confidence score (0.0–1.0)

**Key Classes:**
- `AdvancedReasoningEngine` — Orchestrates all 8 phases
- `ReasoningTrace` — Structured output: understanding, strategies, simulations, final plan

---

### Layer 2 — Perfect Executor
**Module:** `lirox/execution/perfect_executor.py`

Bulletproof code execution:

- **Pre-flight validation** — Block dangerous calls before execution
- **Sandboxed exec** — Isolated namespace, no shell access
- **Self-healing** — Auto-fix `NameError`, `AttributeError`, `ImportError`
- **Automatic retry** — Up to 2 retries on recoverable errors
- **Rollback** — Undo tracked changes on failure
- **Full audit trail** — Every execution logged with hash

**Key Classes:**
- `PerfectExecutor` — Main executor with `execute_safely(code, context)`
- `ExecutionResult` — Result with status, output, error, trace

---

### Layer 3 — Perfect File I/O
**Module:** `lirox/io/perfect_file_io.py`

Reliable file operations:

- **Atomic writes** — Write to `.tmp`, validate, then `os.replace()`
- **Auto-backup** — Creates `.bak` before overwriting
- **Content validation** — Re-reads file to confirm write succeeded
- **UTF-8 validation** — Falls back to `latin-1` on decode error
- **SHA-256 hashing** — Integrity check on every read
- **Path safety** — Blocks `..` traversal and system directories

**Key Classes:**
- `PerfectFileIO` — File I/O with `write_file(path, content)` and `read_file(path)`
- `WriteResult` / `ReadResult` — Structured results with success flag

---

### Layer 4 — Agent Factory & Specialized Agents
**Modules:** `lirox/agents/agent_factory.py`, `lirox/agents/specialized_agents.py`

Dynamic agent creation and delegation:

**Supported Agent Types:**
| Type | Specialization |
|------|---------------|
| `research` | Multi-source research & synthesis |
| `code` | Code generation, debugging, optimization |
| `security` | Vulnerability scanning & auditing |
| `testing` | Test generation & execution |
| `optimization` | Performance analysis |
| `documentation` | Documentation generation |
| `analysis` | Data & text analysis |
| `planning` | Multi-phase task planning |
| `execution` | Plan execution |
| `verification` | Result validation |

**Example:**
```python
from lirox.agents.agent_factory import AgentFactory

factory = AgentFactory()
agent = factory.create_agent("research", {"specialization": "AI papers"})
result = factory.delegate_task("Summarize latest LLM research", "research")
```

---

### Layer 5 — Self-Learning System
**Module:** `lirox/learning/self_learning.py`

Continuous improvement from every interaction:

- **Episodic learning** — Records every task execution with outcome
- **Success rate tracking** — Per-category success/failure metrics
- **Improvement planning** — Auto-generates fixes for failure patterns
- **User preference adaptation** — Learns tone, verbosity, format preferences
- **Persistent knowledge base** — JSON-backed storage

**Example:**
```python
from lirox.learning.self_learning import SelfLearningSystem

learner = SelfLearningSystem()
learner.learn_from_execution("Fetch GitHub data", {"status": "success"})
learner.adapt_to_user("I prefer concise responses")
print(learner.summarize())
```

---

### Layer 6 — Advanced Desktop Controller
**Module:** `lirox/desktop/advanced_control.py`

Full desktop automation (requires `pyautogui`, optionally `pytesseract`):

- **Screenshot + OCR** — Capture screen and extract all text
- **UI element detection** — Find buttons, inputs, menus
- **Intelligent clicking** — Find elements by name/text
- **Smooth mouse movement** — Human-like cursor arcs
- **Clipboard integration** — Read/write clipboard

**Example:**
```python
from lirox.desktop.advanced_control import AdvancedDesktopController

ctrl = AdvancedDesktopController()
analysis = ctrl.take_screenshot_with_analysis()
print(analysis.text)  # All text visible on screen
```

---

### Layer 7 — Advanced Security System
**Module:** `lirox/security/advanced_security.py`

5-level permission system:

1. **Action whitelisting** — Only pre-approved actions allowed
2. **Resource classification** — System/private/sensitive/public tiers
3. **User permissions** — Per-user action grants
4. **Rate limiting** — Sliding-window per-action throttle
5. **Anomaly detection** — Block unusual activity spikes

Additional features:
- **Comprehensive audit log** — Every decision recorded
- **Sandboxed execution** — Safe code eval via `PerfectExecutor`
- **SHA-256 hashing** — One-way sensitive data storage

**Example:**
```python
from lirox.security.advanced_security import AdvancedSecuritySystem

sec = AdvancedSecuritySystem()
allowed = sec.check_permission("write_file", "outputs/report.txt")
result = sec.sandboxed_execution("x = 1 + 1")
```

---

### Layer 8 — Task Planner
**Module:** `lirox/planning/task_planner.py`

Autonomous 8-phase task planning:

| Phase | Description |
|-------|-------------|
| Research | Gather background information |
| Analysis | Extract insights and requirements |
| Planning | Create step-by-step plan |
| Preparation | Gather tools and resources |
| Execution | Carry out the plan |
| Verification | Validate results |
| Optimization | Improve efficiency |
| Documentation | Generate documentation |

**Example:**
```python
from lirox.planning.task_planner import TaskPlanner

planner = TaskPlanner()
plan = planner.plan_task("Build a web scraper for news sites")
print(plan.to_dict())
```

---

### Layer 9 — Agent Swarm
**Module:** `lirox/swarms/agent_swarm.py`

Coordinate multiple agents in parallel:

- **Dynamic spawning** — Create agents on demand
- **Parallel execution** — All agents work simultaneously
- **Result aggregation** — Merge outputs from all agents
- **Collective history** — Track all swarm tasks

**Example:**
```python
from lirox.swarms.agent_swarm import AgentSwarm

swarm = AgentSwarm()
result = swarm.coordinate_task(
    "Analyze the latest AI research papers",
    agent_types=["research", "analysis", "verification"],
)
print(result["combined"])
```

---

### Layer 10 — Self-Modifying Agent
**Module:** `lirox/meta/self_modification.py`

Agents that improve their own source code:

- **Code analysis** — `inspect.getsource()` + AST parsing
- **Issue detection** — Long lines, TODOs, bare excepts, print statements
- **Complexity estimation** — Cyclomatic complexity via AST
- **Improvement generation** — Proposes concrete fixes
- **Safe application** — Tests improvements before applying

**Example:**
```python
from lirox.meta.self_modification import SelfModifyingAgent

agent = SelfModifyingAgent()
analysis = agent.analyze_own_code()
improvements = agent.generate_improvements()
applied = agent.apply_improvements()
```

---

## Supporting Infrastructure

### Browser Tool
**Module:** `lirox/tools/browser.py`

- URL safety validation (SSRF protection)
- Connection pooling via `requests.Session`
- HTML text extraction and CSS selector support
- DuckDuckGo web search

### Browser Security
**Module:** `lirox/tools/browser_security.py`

- SSRF protection (private IPs, cloud metadata)
- Dangerous port blocking (SSH, MySQL, Redis, etc.)
- CRLF/null-byte header injection prevention
- JavaScript prototype pollution detection
- Per-domain token-bucket rate limiting

### Browser Manager
**Module:** `lirox/tools/browser_manager.py`

- `AsyncBridge` — Run async coroutines synchronously with timeout

### Browser CDP Bridge
**Module:** `lirox/tools/browser_bridge.py`

- `CDPError` — Structured Chrome DevTools Protocol errors

### Network Diagnostics
**Module:** `lirox/tools/network_diagnostics.py`

- Human-readable diagnosis of network errors (refused, timeout, DNS, SSL)

### Real-Time Data Extractor
**Module:** `lirox/tools/real_time_data.py`

- Extract stock prices and change percentages from text

### Agent Memory
**Module:** `lirox/agent/memory.py`

- Persistent conversation history
- Keyword search over memory
- Role-based statistics

### Task Scheduler
**Module:** `lirox/agent/scheduler.py`

- Schedule, list, and cancel future tasks

### Planner
**Module:** `lirox/agent/planner.py`

- LLM-driven structured plan generation
- Markdown-fenced JSON extraction
- Numbered-list fallback parsing
- Heuristic tool selection (`_guess_tool`)

### Reasoner
**Module:** `lirox/agent/reasoner.py`

- Step-by-step evaluation with confidence scoring
- Retry/skip/abort recommendations
- Progress reflection and human-readable summaries

### Advanced Memory
**Module:** `lirox/memory/advanced_memory.py`

Multi-tier memory:
- **Episodic** — Past events with timestamps
- **Semantic** — Concepts and facts
- **Procedural** — Learned procedures
- Importance-weighted recall
- Capacity pruning (removes least important first)

### Skills System
**Module:** `lirox/skills/`

- `SkillRegistry` — Register, route, enable/disable skills
- `BashSkill` — Terminal command execution
- Auto-discovery on import

---

## Security Architecture

### Attack Surfaces Covered

| Threat | Mitigation |
|--------|-----------|
| Command injection | Allowlist-based terminal validation |
| Path traversal | `..` detection + safe directory enforcement |
| SSRF | Private IP blocking + cloud metadata endpoint blocking |
| Code injection | Pre-flight checks + sandboxed namespace execution |
| CRLF injection | Header value scanning |
| Null byte injection | Header value scanning |
| Prototype pollution | JavaScript pattern matching |
| Rate abuse | Token bucket per domain + action rate limiter |
| Privilege escalation | 5-level permission system |
| Audit evasion | Comprehensive immutable audit log |
| Data exfiltration | Network access restrictions in sandbox |
| Resource exhaustion | Code size limits + execution timeouts |

---

## Testing

Run the full test suite:

```bash
# All tests
python -m pytest tests/ -q

# New v2.0 tests only
python -m pytest tests/test_all.py -v

# Legacy tests
python -m pytest tests/test_v0_3.py tests/test_v071_hardening.py -v
```

Test coverage:
- `tests/test_all.py` — 73 tests covering all new v2.0 components
- `tests/test_v0_3.py` — 70 tests for core agent components
- `tests/test_v071_hardening.py` — 21 tests for browser/security hardening

---

## Module Index

```
lirox/
├── agents/
│   ├── agent_factory.py       # Dynamic agent creation
│   ├── specialized_agents.py  # 10 specialized agent classes
│   ├── base_agent.py          # Abstract base + PlanningMixin
│   └── personal_agent.py      # Personal agent implementation
├── agent/
│   ├── memory.py              # Persistent conversation memory
│   ├── planner.py             # LLM-driven plan generator
│   ├── reasoner.py            # Step evaluation and reflection
│   ├── scheduler.py           # Task scheduling
│   └── executor.py            # Browser + headless detection
├── desktop/
│   └── advanced_control.py   # Desktop automation
├── execution/
│   └── perfect_executor.py   # Sandboxed code execution
├── io/
│   └── perfect_file_io.py    # Atomic file I/O
├── learning/
│   └── self_learning.py      # Self-learning system
├── memory/
│   ├── advanced_memory.py    # Multi-tier memory
│   └── manager.py             # Base memory manager
├── meta/
│   └── self_modification.py  # Self-improving agents
├── planning/
│   └── task_planner.py       # 8-phase task planning
├── security/
│   └── advanced_security.py  # Bank-grade security
├── skills/
│   ├── __init__.py            # SkillRegistry
│   └── bash_skill.py          # Terminal skill
├── swarms/
│   └── agent_swarm.py        # Multi-agent coordination
├── thinking/
│   └── advanced_reasoning.py # 8-phase reasoning engine
└── tools/
    ├── browser.py             # HTTP browser with safety
    ├── browser_bridge.py      # CDP error types
    ├── browser_manager.py     # Async bridge
    ├── browser_security.py    # URL/header/JS validation
    ├── network_diagnostics.py # Error diagnosis
    └── real_time_data.py      # Financial data extraction
```
