# Code Inspection Engine

Lirox v1.0.0 introduces a built-in **Code Inspection Engine** that lets agents read, analyze, validate, and self-fix code — all before showing it to the user.

## Architecture

```
User query
    │
    ▼
CodeAgent.run()
    │
    ├─► LLM generates code
    │
    ▼
CodeInspector.inspect()
    │
    ├─► CodeReader.read_file()          ← reads user's existing code for context
    ├─► CodeAnalyzer.analyze()          ← LLM analysis (syntax, logic, security)
    ├─► CodeExecutor.execute_python()   ← optional live test (Python only)
    │
    ├── issues found?
    │       ├── YES → CodeInspector.self_fix() → re-run analysis
    │       └── NO  → pass
    │
    ▼
Validated code shown to user (with diff / explanation if fixes were applied)
```

## Components

### `lirox/tools/code_reader.py` — `CodeReader`

Safely reads code files from the filesystem.

```python
from lirox.tools.code_reader import CodeReader

reader = CodeReader()
result = reader.read_file("src/utils.py")
# result = {"path": "...", "content": "...", "language": "python", "lines": 120, "size": 3400}

files = reader.read_directory("src/", max_files=5)
# files = [{"path": "...", "content": "...", "language": "..."}, ...]
```

Path validation enforces `SAFE_DIRS` from `lirox/config.py` — the agent cannot read system files.

### `lirox/tools/code_analyzer.py` — `CodeAnalyzer`

LLM-powered analysis of code quality, correctness, and security.

```python
from lirox.tools.code_analyzer import CodeAnalyzer

analyzer = CodeAnalyzer()
result = analyzer.analyze(code="def foo(x): return x/0", language="python")
# result = {
#   "issues": [{"severity": "error", "message": "Division by zero", "line": 1}],
#   "suggestions": ["Add a zero check before division"],
#   "score": 40,
#   "summary": "Critical division by zero bug found"
# }

vulns = analyzer.security_scan(code)
# vulns = [{"severity": "high", "message": "Possible SQL injection", "line": 5}]
```

### `lirox/tools/code_executor.py` — `CodeExecutor`

Executes Python code in a safe subprocess (no `shell=True`) for live validation.

```python
from lirox.tools.code_executor import CodeExecutor

executor = CodeExecutor()
result = executor.execute_python("print('hello world')", timeout=5)
# result = {"success": True, "output": "hello world\n", "error": ""}

valid, msg = executor.validate_syntax("def foo(:", language="python")
# valid = False, msg = "SyntaxError: ..."
```

### `lirox/agents/code/code_inspector.py` — `CodeInspector`

Orchestrates the full inspection pipeline.

```python
from lirox.agents.code.code_inspector import CodeInspector

inspector = CodeInspector()
result = inspector.inspect(
    code="def divide(a, b): return a/b",
    language="python",
    user_code_paths=["myproject/utils.py"]   # optional context files
)
# result = {
#   "valid": False,
#   "issues": [...],
#   "suggestions": [...],
#   "fixed_code": "def divide(a, b):\n    if b == 0:\n        raise ValueError('Cannot divide by zero')\n    return a / b",
#   "explanation": "Added zero-division guard"
# }
```

### `lirox/agents/code/agent.py` — `CodeAgent`

A `BaseAgent` subclass that integrates `CodeInspector` into the standard agent `run()` loop.

Every time the `CodeAgent` generates code, it automatically:
1. Runs `CodeInspector.inspect()` on the output
2. Attempts `self_fix()` if issues are found
3. Reports any remaining issues to the user

## Configuration

No additional configuration is needed. The engine uses:
- `SAFE_DIRS` from `lirox/config.py` to sandbox file reads
- `MAX_TOOL_RESULT_CHARS` to cap large file reads
- The same LLM provider configured for the rest of Lirox

## Supported Languages

Detection is based on file extension:

| Extension | Language |
|-----------|----------|
| `.py` | Python |
| `.js` | JavaScript |
| `.ts` | TypeScript |
| `.java` | Java |
| `.go` | Go |
| `.rs` | Rust |
| `.cpp`, `.cc`, `.cxx` | C++ |
| `.c` | C |
| `.cs` | C# |
| `.rb` | Ruby |
| `.php` | PHP |
| `.swift` | Swift |
| `.kt` | Kotlin |
| `.sh`, `.bash` | Shell |

Live execution (via `CodeExecutor`) is currently supported for **Python only**.
Syntax validation via `ast.parse` is Python-only; other languages rely on LLM analysis.
