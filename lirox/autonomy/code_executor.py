"""Lirox Autonomy — Intelligent & Safe Code Executor"""

from __future__ import annotations

import ast
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Generator, List


# ─────────────────────────────────────────────────────────────
# Execution Result (Structured Output)
# ─────────────────────────────────────────────────────────────

@dataclass
class ExecutionResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    timed_out: bool = False
    error: str = ""

    def summary(self) -> str:
        if self.timed_out:
            return "⏱ Execution timed out."
        if not self.success:
            return f"✖ Failed (exit {self.exit_code}):\n{self.stderr or self.error}"
        return f"✓ Success\n{self.stdout.strip()}" if self.stdout else "✓ Success (no output)"


# ─────────────────────────────────────────────────────────────
# Code Executor
# ─────────────────────────────────────────────────────────────

class CodeExecutor:
    """Analyse, validate, and safely execute Python code."""

    DEFAULT_TIMEOUT = 15

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout

    # ─────────────────────────────────────────────────────────
    # 🧠 Static Analysis (Agent Intelligence)
    # ─────────────────────────────────────────────────────────

    def parse_ast(self, source: str) -> ast.Module:
        return ast.parse(source)

    def check_syntax(self, source: str) -> List[str]:
        errors = []
        try:
            ast.parse(source)
        except SyntaxError as e:
            errors.append(f"SyntaxError line {e.lineno}: {e.msg}")
        return errors

    def analyse_file(self, path: str) -> Dict[str, Any]:
        result = {"classes": [], "functions": [], "imports": [], "loc": 0, "errors": []}

        try:
            source = Path(path).read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            result["errors"].append(str(e))
            return result

        result["loc"] = len(source.splitlines())

        try:
            tree = self.parse_ast(source)
        except SyntaxError as e:
            result["errors"].append(str(e))
            return result

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                result["classes"].append(node.name)
            elif isinstance(node, ast.FunctionDef):
                result["functions"].append(node.name)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    result["imports"].extend(alias.name for alias in node.names)
                else:
                    result["imports"].append(node.module or "")

        return result

    # ─────────────────────────────────────────────────────────
    # ⚙️ Execution Engine (Safe Sandbox)
    # ─────────────────────────────────────────────────────────

    def execute(self, source: str, extra_context: str = "") -> ExecutionResult:
        full_source = textwrap.dedent(extra_context) + "\n\n" + source if extra_context else source

        # Syntax check first
        errors = self.check_syntax(full_source)
        if errors:
            return ExecutionResult(success=False, error="; ".join(errors))

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tmp:
            tmp.write(full_source)
            tmp_path = tmp.name

        try:
            proc = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            return ExecutionResult(
                success=proc.returncode == 0,
                stdout=proc.stdout[:4000],
                stderr=proc.stderr[:2000],
                exit_code=proc.returncode,
            )

        except subprocess.TimeoutExpired:
            return ExecutionResult(success=False, timed_out=True, error="Timeout exceeded")

        except Exception as e:
            return ExecutionResult(success=False, error=str(e))

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    # ─────────────────────────────────────────────────────────
    # ⚡ Streaming (Agent UX)
    # ─────────────────────────────────────────────────────────

    def run_and_stream(self, source: str) -> Generator[Dict[str, Any], None, None]:
        yield {"type": "agent_progress", "message": "🔍 Checking syntax..."}

        errors = self.check_syntax(source)
        if errors:
            for err in errors:
                yield {"type": "error", "message": err}
            return

        yield {"type": "agent_progress", "message": "⚙️ Running code..."}

        result = self.execute(source)

        if result.success:
            yield {"type": "success", "message": "Execution successful"}
            if result.stdout:
                yield {"type": "output", "message": result.stdout}
        else:
            yield {"type": "error", "message": result.summary()}

    # ─────────────────────────────────────────────────────────
    # 🧪 Quick Snippet Execution
    # ─────────────────────────────────────────────────────────

    def execute_snippet(self, snippet: str) -> ExecutionResult:
        wrapper = f"""
import traceback
try:
    result = {snippet}
    print(repr(result))
except Exception:
    traceback.print_exc()
"""
        return self.execute(wrapper)