"""
Lirox v3.0 — Code Executor Tool

Safe code execution for testing and validation. Runs Python code in an
isolated subprocess with a hard timeout and caps output to
``MAX_TOOL_RESULT_CHARS`` from the project configuration. No shell
expansion is used (``shell=False``) to prevent injection attacks.
"""

from __future__ import annotations

import ast
import subprocess
import sys
import textwrap
from typing import Optional

from lirox.config import MAX_TOOL_RESULT_CHARS


class CodeExecutor:
    """
    Execute and validate code snippets safely.

    Only Python execution is supported at runtime.  Syntax validation is
    available for any language supported by the Python ``ast`` module or
    via a basic compile check.
    """

    # ── Python execution ──────────────────────────────────────────────────────

    def execute_python(self, code: str, timeout: int = 10) -> dict:
        """
        Execute *code* as a Python script in a subprocess.

        The subprocess is launched with ``shell=False`` and killed
        automatically after *timeout* seconds.  Both stdout and stderr
        are captured and truncated to ``MAX_TOOL_RESULT_CHARS``.

        Args:
            code:    Python source code to run.
            timeout: Maximum wall-clock seconds before the process is
                     killed (default 10).

        Returns:
            A dict with keys:

            * ``success`` (bool)   – True if exit code is 0
            * ``output``  (str)    – captured stdout
            * ``error``   (str)    – captured stderr or exception message
            * ``exit_code`` (int)
        """
        if not code.strip():
            return {"success": False, "output": "", "error": "Empty code.", "exit_code": -1}

        try:
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
            stdout = result.stdout[:MAX_TOOL_RESULT_CHARS]
            stderr = result.stderr[:MAX_TOOL_RESULT_CHARS]
            return {
                "success":   result.returncode == 0,
                "output":    stdout,
                "error":     stderr,
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "success":   False,
                "output":    "",
                "error":     f"Execution timed out after {timeout} seconds.",
                "exit_code": -1,
            }
        except Exception as exc:
            return {
                "success":   False,
                "output":    "",
                "error":     f"Execution error: {exc}",
                "exit_code": -1,
            }

    # ── Syntax validation ─────────────────────────────────────────────────────

    def validate_syntax(self, code: str, language: str) -> tuple[bool, str]:
        """
        Validate the syntax of *code* without executing it.

        For Python, the built-in ``ast.parse`` / ``compile`` is used.
        For other languages a basic non-empty check is performed.

        Args:
            code:     Source code to validate.
            language: Language name (e.g. ``"python"``, ``"javascript"``).

        Returns:
            A ``(valid, message)`` tuple where *valid* is ``True`` when
            no syntax errors were detected and *message* gives details.
        """
        if not code.strip():
            return False, "Code is empty."

        lang = language.lower()

        if lang == "python":
            return self._validate_python(code)

        # For other languages we can only confirm the snippet is non-empty.
        return True, f"Basic validation passed for {language} (runtime check not available)."

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _validate_python(code: str) -> tuple[bool, str]:
        """Compile-only Python syntax check (no execution)."""
        # Dedent to handle snippets that may be indented
        source = textwrap.dedent(code)
        try:
            ast.parse(source)
            return True, "Syntax is valid."
        except SyntaxError as exc:
            return False, f"SyntaxError at line {exc.lineno}: {exc.msg}"
        except Exception as exc:
            return False, f"Validation error: {exc}"
