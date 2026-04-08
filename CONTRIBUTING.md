# 🤝 Contributing to Lirox

> We welcome contributions from the community! This guide explains how to get involved.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Setup](#development-setup)
4. [How to Contribute](#how-to-contribute)
5. [Code Standards](#code-standards)
6. [Testing Requirements](#testing-requirements)
7. [Pull Request Process](#pull-request-process)
8. [Areas Needing Help](#areas-needing-help)

---

## Code of Conduct

By participating in this project, you agree to:
- Be respectful and inclusive
- Welcome constructive feedback
- Focus on what is best for the community
- Show empathy toward other contributors

---

## Getting Started

### 1. Fork the Repository

Click "Fork" on the [Lirox GitHub page](https://github.com/baljotchohan/Lirox).

### 2. Clone Your Fork

```bash
git clone https://github.com/YOUR_USERNAME/Lirox.git
cd Lirox
```

### 3. Add Upstream Remote

```bash
git remote add upstream https://github.com/baljotchohan/Lirox.git
```

### 4. Keep Fork Updated

```bash
git fetch upstream
git checkout main
git merge upstream/main
```

---

## Development Setup

### Prerequisites

- Python 3.8+
- pip
- Git

### Install Dependencies

```bash
pip install -r requirements.txt
pip install -e .
```

### Configure Environment

```bash
# Create .env file and add your API key
echo "GROQ_API_KEY=your_key_here" > .env
```

### Run Lirox

```bash
lirox
# or
python -m lirox
```

---

## How to Contribute

### Reporting Bugs

1. Check [existing issues](https://github.com/baljotchohan/Lirox/issues)
2. Create a new issue with:
   - Clear description of the bug
   - Steps to reproduce
   - Expected vs actual behavior
   - Your OS and Python version
   - Relevant error messages

### Suggesting Features

1. Open a [GitHub Discussion](https://github.com/baljotchohan/Lirox/discussions)
2. Describe the feature and its benefits
3. Get community feedback before implementing

### Submitting Code

```bash
# Create a feature branch
git checkout -b feature/my-new-feature

# Make your changes
# ...

# Commit with clear message
git commit -m "Add: brief description of change"

# Push to your fork
git push origin feature/my-new-feature

# Open a Pull Request on GitHub
```

---

## Code Standards

### Python Style

- Follow [PEP 8](https://pep8.org/)
- Use type hints for all function signatures
- Use `from __future__ import annotations` at the top of files with forward references
- Use `Optional[T]` rather than `T | None` for Python 3.8 compatibility
- Maximum line length: 100 characters
- Use descriptive variable names

```python
# Good
def calculate_response_time(start_time: float, end_time: float) -> float:
    """Calculate the time taken for a response in milliseconds."""
    return (end_time - start_time) * 1000
```

### Docstrings

All public functions and classes must have docstrings. Use Google-style:

```python
def process_query(query: str, context: dict = None) -> str:
    """Process a user query and return a response.

    Args:
        query: The user input query.
        context: Optional context dictionary with session data.

    Returns:
        The processed response string.

    Raises:
        ValueError: If query is empty.
    """
```

### Logging

Use the structured logger:

```python
from lirox.utils.structured_logger import get_logger

logger = get_logger(__name__)
logger.info("Processing query", extra={"query_length": len(query)})
```

### Security

- Never use `shell=True` in subprocess calls
- Never hardcode secrets or API keys
- Validate all user input before processing
- Respect `SAFE_DIRS` from `lirox.config` for filesystem access

### Commit Messages

Use conventional commit format:

```
feat: add new skill creation wizard
fix: resolve memory leak in session manager
docs: update README installation steps
refactor: simplify agent routing logic
test: add unit tests for memory manager
chore: update dependencies
```

---

## Testing Requirements

### Writing Tests

All new features should include tests:

```python
# tests/test_my_feature.py
import pytest
from lirox.my_module import MyClass

class TestMyClass:
    def test_basic_functionality(self):
        obj = MyClass()
        result = obj.process("test input")
        assert result is not None
        assert isinstance(result, str)

    def test_edge_case(self):
        obj = MyClass()
        with pytest.raises(ValueError):
            obj.process("")
```

### Adding New Agents

New agents must:
1. Live in `lirox/agents/<name>/agent.py`
2. Extend `BaseAgent` from `lirox.agents.base_agent`
3. Implement the abstract `name`, `description`, and `run()` members
4. Override `get_onboarding_message()` with an agent-specific welcome
5. Use an isolated `MemoryManager` (pass `agent_name=self.name` in `__init__`)

### Adding New Tools

New tools must:
1. Live in `lirox/tools/<name>.py`
2. Respect `SAFE_DIRS` from `lirox.config` for any filesystem access
3. Validate input before processing
4. Return structured results (dicts or typed dataclasses)
5. Never use `shell=True` in subprocess calls

---

## Pull Request Process

### Before Submitting

- [ ] Code follows style guidelines
- [ ] Tests pass locally
- [ ] New tests added for new features
- [ ] Documentation updated if needed
- [ ] Commit messages are clear

### PR Description Template

```markdown
## What does this PR do?
Brief description of the change.

## Why is this needed?
Motivation and context.

## How was it tested?
Description of testing approach.

## Related Issues
Closes #123
```

### Review Process

1. Automated checks must pass
2. At least one maintainer review required
3. Address all review comments
4. Maintainer merges approved PRs

---

## Areas Needing Help

We especially welcome contributions in these areas:

- **Bug fixes**: Check issues labeled 
- **Features**: Check issues labeled 
- **Documentation**: Improve existing docs, add more examples
- **Testing**: Increase test coverage, add integration tests

---

## Questions?

- Open a [GitHub Discussion](https://github.com/baljotchohan/Lirox/discussions)
- Create an [Issue](https://github.com/baljotchohan/Lirox/issues)

Thank you for contributing to Lirox! 🦁
