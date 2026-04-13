"""Lirox Autonomy — Code Executor.

Runs Python source in a sandboxed sub-process with timeout protection,
stdout/stderr capture, and structured result reporting.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ExecutionResult:
    success:   bool
    stdout:    str = ""
    stderr:    str = ""
    exit_code: int = 0
    timed_out: bool = False
    error:     str = ""

    def summary(self) -> str:
        if self.timed_out:
            return "⏱ Execution timed out."
        if not self.success:
            return f"✖ Execution failed (exit {self.exit_code}):\n{self.stderr or self.error}"
        out = self.stdout.strip()
        return f"✓ Execution succeeded.\n{out}" if out else "✓ Execution succeeded (no output)."


class CodeExecutor:
    """Execute Python source safely in a child process."""

    DEFAULT_TIMEOUT = 15  # seconds

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout

    # ── Public API ─────────────────────────────────────────────────────────

    def execute(self, source: str, extra_context: str = "") -> ExecutionResult:
        """Run *source* in an isolated subprocess and return the result."""
        full_source = source
        if extra_context:
            full_source = textwrap.dedent(extra_context) + "\n\n" + source

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as tmp:
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
                success=(proc.returncode == 0),
                stdout=proc.stdout[:4000],
                stderr=proc.stderr[:2000],
                exit_code=proc.returncode,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                timed_out=True,
                error=f"Script exceeded {self.timeout}s timeout.",
            )
        except Exception as exc:
            return ExecutionResult(success=False, error=str(exc))
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def execute_snippet(self, snippet: str) -> ExecutionResult:
        """Execute a short expression or snippet, returning its repr."""
        wrapper = (
            "import sys, traceback\n"
            "try:\n"
            f"    _result = ({snippet})\n"
            "    print(repr(_result))\n"
            "except Exception:\n"
            "    traceback.print_exc()\n"
            "    sys.exit(1)\n"
        )
        return self.execute(wrapper)
