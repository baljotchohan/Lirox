# Migration Guide: Beta → v1.0.0

This guide helps users upgrade from Lirox beta (v0.5.x) to v1.0.0.

## What Changed

### Version Numbers

All version strings are now unified at `1.0.0`:

| File | Before | After |
|------|--------|-------|
| `lirox/config.py` (`APP_VERSION`) | `0.5.0` | `1.0.0` |
| `lirox/__init__.py` (`__version__`) | `1.0.0b1` | `1.0.0` |
| `pyproject.toml` | `3.0.0` | `1.0.0` |

### New Agent Subdirectory Structure

Agents now live in dedicated subdirectories with isolated memory:

```
lirox/agents/
├── base_agent.py          (unchanged)
├── code/
│   ├── agent.py           NEW — CodeAgent with inspection
│   └── code_inspector.py  NEW — inspection pipeline
├── chat/
│   └── agent.py           NEW — ChatAgent
├── finance/
│   └── agent.py           NEW — FinanceAgent
├── browser/
│   └── agent.py           NEW — BrowserAgent
└── research/
    └── agent.py           NEW — ResearchAgent
```

### New Code Inspection Tools

```
lirox/tools/
├── code_reader.py    NEW — safe code file reader
├── code_analyzer.py  NEW — LLM-powered code analysis
└── code_executor.py  NEW — safe Python execution
```

### Memory System

```
lirox/memory/
├── manager.py         (unchanged — per-agent isolation was already in place)
├── memory_bank.py     NEW — higher-level KV store wrapping MemoryManager
└── session_manager.py NEW — singleton session lifecycle manager
```

## Breaking Changes

There are **no breaking changes** in v1.0.0. All existing functionality continues to work as before. The new modules are additive.

## Upgrade Steps

1. Pull the latest code:
   ```bash
   git pull origin main
   ```

2. No dependency changes are required for core functionality. The new tools use only packages already in `requirements.txt`/`pyproject.toml`.

3. Existing `.env` files and `data/` directories are fully compatible — no migration of stored data is needed.

## If You Import `APP_VERSION` Directly

If any custom scripts import `APP_VERSION` expecting `"0.5.0"`, update them:

```python
# Before
from lirox.config import APP_VERSION  # was "0.5.0"

# After — now "1.0.0"
from lirox.config import APP_VERSION
```

## If You Import `__version__`

```python
# Before
import lirox; lirox.__version__  # was "1.0.0b1"

# After — now "1.0.0"
import lirox; lirox.__version__
```
