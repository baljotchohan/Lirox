"""
Lirox v1.0.0 — Code Inspection Engine

Orchestrates ``CodeReader``, ``CodeAnalyzer``, and ``CodeExecutor`` to
provide a unified code-inspection and self-fix pipeline.  The engine
validates code, collects issues, attempts LLM-driven auto-fixes, and
returns a structured inspection report.
"""

from __future__ import annotations

from typing import Optional

from lirox.tools.code_reader import CodeReader
from lirox.tools.code_analyzer import CodeAnalyzer
from lirox.tools.code_executor import CodeExecutor


class CodeInspector:
    """
    Orchestrate full code inspection: read → analyse → execute → fix.

    This class is intentionally dependency-injectable; pass custom
    instances of the three tool classes in tests or specialised setups.
    """

    def __init__(
        self,
        reader:   Optional[CodeReader]   = None,
        analyzer: Optional[CodeAnalyzer] = None,
        executor: Optional[CodeExecutor] = None,
    ) -> None:
        self._reader   = reader   or CodeReader()
        self._analyzer = analyzer or CodeAnalyzer()
        self._executor = executor or CodeExecutor()

    # ── Main inspection entry-point ───────────────────────────────────────────

    def inspect(
        self,
        code: str,
        language: str,
        user_code_paths: Optional[list[str]] = None,
    ) -> dict:
        """
        Perform a full inspection of *code*.

        Pipeline:

        1. Validate syntax (fast local check for Python).
        2. If *user_code_paths* provided, read those files and include
           them as context for the LLM analyser.
        3. Run LLM analysis.
        4. For Python: execute the code in a subprocess.
        5. If issues found: attempt to obtain a fixed version via
           :meth:`self_fix`.

        Args:
            code:            Source code to inspect.
            language:        Language name (e.g. ``"python"``).
            user_code_paths: Optional list of file paths to read and
                             include as analysis context.

        Returns:
            A dict with keys:

            * ``valid``      (bool)
            * ``issues``     (list[str])
            * ``suggestions`` (list[str])
            * ``fixed_code`` (str or None) – auto-fixed version, if any
            * ``explanation`` (str)
        """
        result: dict = {
            "valid":       True,
            "issues":      [],
            "suggestions": [],
            "fixed_code":  None,
            "explanation": "",
        }

        if not code.strip():
            result["valid"] = False
            result["issues"].append("Code is empty.")
            result["explanation"] = "Nothing to inspect."
            return result

        # 1. Syntax check
        syntax_ok, syntax_msg = self._executor.validate_syntax(code, language)
        if not syntax_ok:
            result["valid"] = False
            result["issues"].append(syntax_msg)

        # 2. Read context files
        context = self._read_context_files(user_code_paths or [])

        # 3. LLM analysis
        analysis = self._analyzer.analyze(code, language, context=context)
        result["issues"].extend(analysis.get("issues", []))
        result["suggestions"].extend(analysis.get("suggestions", []))

        # 4. Python execution test
        execution_error = ""
        if language.lower() == "python" and syntax_ok:
            exec_result = self._executor.execute_python(code, timeout=10)
            if not exec_result["success"] and exec_result["error"]:
                execution_error = exec_result["error"]
                result["issues"].append(f"Runtime error: {execution_error}")

        # 5. Validity and auto-fix
        if result["issues"]:
            result["valid"] = False
            error_hint = (
                execution_error
                or (result["issues"][0] if result["issues"] else "")
            )
            result["fixed_code"] = self.self_fix(code, error_hint, language) or None

        summary_parts = []
        if analysis.get("summary"):
            summary_parts.append(analysis["summary"])
        if result["issues"]:
            summary_parts.append(
                f"{len(result['issues'])} issue(s) detected."
            )
        else:
            summary_parts.append("Code looks good.")
        result["explanation"] = " ".join(summary_parts)

        return result

    # ── Auto-fix ──────────────────────────────────────────────────────────────

    def self_fix(self, code: str, error: str, language: str) -> str:
        """
        Attempt to auto-fix *code* for a given *error* using the LLM.

        Args:
            code:     Source code that contains an error.
            error:    Error message or description.
            language: Programming language.

        Returns:
            A corrected version of the code as a string, or an empty
            string if no fix could be produced.
        """
        if not code.strip():
            return ""
        suggestion = self._analyzer.get_fix_suggestions(code, error)
        return suggestion or ""

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _read_context_files(self, paths: list[str]) -> str:
        """
        Read *paths* and concatenate their contents as a context string.

        Files that cannot be read (outside safe dirs, not found, etc.)
        are silently skipped.
        """
        parts: list[str] = []
        for path in paths:
            file_result = self._reader.read_file(path)
            if file_result["success"]:
                parts.append(
                    f"--- {path} ({file_result['language']}) ---\n"
                    f"{file_result['content']}"
                )
        return "\n\n".join(parts)
