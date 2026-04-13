"""Lirox Autonomy — Autonomous Code Executor

Analyses Python source files via AST, runs generated code in an isolated
subprocess, and returns structured execution results.
"""
from __future__ import annotations

import ast
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any, Dict, Generator, List


class CodeExecutor:
    """Analyse, validate, and execute Python code autonomously."""

    # ------------------------------------------------------------------
    # Static analysis
    # ------------------------------------------------------------------

    def parse_ast(self, source: str) -> ast.Module:
        """Return the AST for *source*, raising SyntaxError on bad code."""
        return ast.parse(source)

    def analyse_file(self, path: str) -> Dict[str, Any]:
        """Return a structural summary of a Python source file.

        Returns a dict with keys:
          - ``classes``: list of class names
          - ``functions``: list of top-level function names
          - ``imports``: list of imported module names
          - ``loc``: number of source lines
          - ``errors``: list of syntax / IO error messages
        """
        result: Dict[str, Any] = {
            "classes": [], "functions": [], "imports": [], "loc": 0, "errors": []
        }
        try:
            source = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            result["errors"].append(str(exc))
            return result

        lines = source.splitlines()
        result["loc"] = len(lines)

        try:
            tree = self.parse_ast(source)
        except SyntaxError as exc:
            result["errors"].append(f"SyntaxError: {exc}")
            return result

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                result["classes"].append(node.name)
            elif isinstance(node, ast.FunctionDef):
                result["functions"].append(node.name)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        result["imports"].append(alias.name)
                else:
                    result["imports"].append(node.module or "")

        return result

    def check_syntax(self, source: str) -> List[str]:
        """Return a list of syntax error messages; empty list means valid."""
        errors: List[str] = []
        try:
            ast.parse(source)
        except SyntaxError as exc:
            errors.append(f"SyntaxError at line {exc.lineno}: {exc.msg}")
        return errors

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run_code(self, source: str, timeout: int = 15) -> Dict[str, Any]:
        """Execute *source* in an isolated subprocess.

        Returns a dict with keys:
          - ``stdout``: captured standard output
          - ``stderr``: captured standard error
          - ``returncode``: process exit code
          - ``success``: True when returncode == 0
          - ``error``: human-readable error message or empty string
        """
        result: Dict[str, Any] = {
            "stdout": "", "stderr": "", "returncode": -1, "success": False, "error": ""
        }

        syntax_errors = self.check_syntax(source)
        if syntax_errors:
            result["error"] = "; ".join(syntax_errors)
            result["stderr"] = result["error"]
            return result

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(source)
            tmp_path = tmp.name

        try:
            proc = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            result["stdout"] = proc.stdout
            result["stderr"] = proc.stderr
            result["returncode"] = proc.returncode
            result["success"] = proc.returncode == 0
            if not result["success"]:
                result["error"] = (proc.stderr or "Non-zero exit code").strip()
        except subprocess.TimeoutExpired:
            result["error"] = f"Execution timed out after {timeout}s"
        except Exception as exc:
            result["error"] = str(exc)
        finally:
            try:
                Path(tmp_path).unlink()
            except OSError:
                pass

        return result

    def run_and_stream(
        self, source: str, timeout: int = 15
    ) -> Generator[Dict[str, Any], None, None]:
        """Execute *source* and yield progress events suitable for the agent event bus.

        Yields dicts with ``type`` and ``message`` keys.
        """
        yield {"type": "agent_progress", "message": "🔬 Validating code syntax…"}
        errors = self.check_syntax(source)
        if errors:
            for err in errors:
                yield {"type": "agent_progress", "message": f"  ✖ {err}"}
            yield {"type": "tool_result", "message": "Code has syntax errors — not executed."}
            return

        yield {"type": "agent_progress", "message": "⚙️  Executing code in sandbox…"}
        result = self.run_code(source, timeout=timeout)

        if result["success"]:
            yield {"type": "tool_result", "message": "✓ Execution succeeded"}
            if result["stdout"]:
                yield {
                    "type": "tool_result",
                    "message": textwrap.shorten(result["stdout"], width=300, placeholder="…"),
                }
        else:
            yield {"type": "tool_result", "message": f"✖ Execution failed: {result['error']}"}
            if result["stderr"]:
                yield {
                    "type": "tool_result",
                    "message": textwrap.shorten(result["stderr"], width=300, placeholder="…"),
                }
