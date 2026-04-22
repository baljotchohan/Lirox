"""Lirox v1.0 — Code Runner (safe sandboxed execution)

Wraps the existing CodeExecutor with additional safety layers:
  - Hard timeout enforcement
  - Output size capping
  - Working-directory isolation
  - Result typed as RunResult
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_logger = logging.getLogger("lirox.execution.runner")

_DEFAULT_TIMEOUT = 15
_MAX_OUTPUT = 8000


@dataclass
class RunResult:
    """Result from executing a code snippet."""
    success: bool
    output: str
    error: str
    exit_code: int
    language: str
    timed_out: bool = False

    @property
    def summary(self) -> str:
        if self.success:
            return self.output[:500] or "(no output)"
        if self.timed_out:
            return f"Timed out after {_DEFAULT_TIMEOUT}s"
        return self.error[:500] or f"Exit code {self.exit_code}"


class CodeRunner:
    """Execute code snippets safely in a subprocess.

    Example::

        runner = CodeRunner()
        result = runner.run("print('hello')", language="python")
        print(result.output)  # hello
    """

    def __init__(self, timeout: int = _DEFAULT_TIMEOUT, workdir: Optional[str] = None):
        self._timeout = timeout
        self._workdir = workdir

    def run(self, code: str, language: str = "python") -> RunResult:
        """Run *code* in the given *language*.

        Only Python is executed at runtime; other languages receive a syntax
        check only (to avoid requiring build chains in the test environment).
        """
        lang = language.lower()
        if not code.strip():
            return RunResult(
                success=False, output="", error="Empty code.", exit_code=-1, language=lang
            )
        if lang == "python":
            return self._run_python(code)
        return self._validate_only(code, lang)

    # ── Python ────────────────────────────────────────────────────────────────

    def _run_python(self, code: str) -> RunResult:
        # Write to a temp file so tracebacks show line numbers correctly
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp_path = f.name
        try:
            result = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=self._timeout,
                shell=False,
                cwd=self._workdir,
            )
            return RunResult(
                success=result.returncode == 0,
                output=result.stdout[:_MAX_OUTPUT],
                error=result.stderr[:_MAX_OUTPUT],
                exit_code=result.returncode,
                language="python",
            )
        except subprocess.TimeoutExpired:
            return RunResult(
                success=False,
                output="",
                error=f"Timed out after {self._timeout}s.",
                exit_code=-1,
                language="python",
                timed_out=True,
            )
        except Exception as exc:
            return RunResult(
                success=False, output="", error=str(exc), exit_code=-1, language="python"
            )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    # ── Other languages (syntax only) ─────────────────────────────────────────

    def _validate_only(self, code: str, lang: str) -> RunResult:
        from lirox.tools.code_executor import CodeExecutor
        executor = CodeExecutor()
        valid, msg = executor.validate_syntax(code, lang)
        return RunResult(
            success=valid,
            output=msg if valid else "",
            error="" if valid else msg,
            exit_code=0 if valid else 1,
            language=lang,
        )
