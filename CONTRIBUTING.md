# Contributing to Lirox

Thank you for your interest in contributing to Lirox! This document covers the standards and process for contributing.

## Code Quality Standards

All contributions must meet these standards:

- ✅ All files have module-level docstrings
- ✅ All public functions and classes have docstrings
- ✅ All function signatures include type hints
- ✅ All error paths are handled gracefully (never raise unhandled exceptions in production code)
- ✅ No unused imports
- ✅ No dead code
- ✅ Proper logging via `lirox.utils.structured_logger.get_logger()`
- ✅ Security: no `shell=True` in subprocess calls, no hardcoded secrets

## Style Guide

- Use `from __future__ import annotations` at the top of files with forward references
- Follow PEP 8 for formatting
- Prefer explicit type aliases over bare `Any` where possible
- Use `Optional[T]` rather than `T | None` for Python 3.9 compatibility

## Testing

Run the test suite before submitting a PR:

```bash
python -m pytest tests/test_v0_3.py -q
```

All 70 tests must pass. If you add new functionality, add matching tests.

## Adding New Agents

New agents must:
1. Live in `lirox/agents/<name>/agent.py`
2. Extend `BaseAgent` from `lirox.agents.base_agent`
3. Implement the abstract `name`, `description`, and `run()` members
4. Override `get_onboarding_message()` with an agent-specific welcome
5. Use an isolated `MemoryManager` (pass `agent_name=self.name` in `__init__`)

## Adding New Tools

New tools must:
1. Live in `lirox/tools/<name>.py`
2. Respect `SAFE_DIRS` from `lirox.config` for any filesystem access
3. Validate input before processing
4. Return structured results (dicts or typed dataclasses)
5. Never use `shell=True` in subprocess calls

## Pull Request Process

1. Fork the repo and create a feature branch
2. Implement your changes following the standards above
3. Run `python -m pytest tests/test_v0_3.py -q` and confirm all tests pass
4. Open a PR with a clear description of what changed and why
