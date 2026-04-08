"""
Lirox v1.0.0 — Code Analyzer Tool

LLM-powered static analysis for source code. Provides issue detection,
syntax checking, security scanning, and auto-fix suggestions by delegating
to the configured LLM provider via ``generate_response``.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from lirox.utils.llm import generate_response


class CodeAnalyzer:
    """
    Analyse source code using the Lirox LLM backend.

    All public methods catch every exception internally and return safe
    fallback values, so callers never need to guard against crashes.
    """

    # ── Public API ────────────────────────────────────────────────────────────

    def analyze(
        self,
        code: str,
        language: str,
        context: str = "",
    ) -> dict:
        """
        Perform a full quality analysis of *code*.

        Args:
            code:     Source code to analyse.
            language: Programming language (e.g. ``"python"``).
            context:  Optional extra context to guide the LLM.

        Returns:
            A dict with keys:

            * ``issues``      (list[str])  – problems found
            * ``suggestions`` (list[str])  – improvement ideas
            * ``score``       (int)        – quality 0-100
            * ``summary``     (str)        – one-paragraph summary
        """
        empty: dict = {"issues": [], "suggestions": [], "score": 0, "summary": ""}
        if not code.strip():
            return empty

        context_block = f"\n\nAdditional context:\n{context}" if context else ""
        prompt = (
            f"Analyse the following {language} code for quality, correctness, "
            f"style, and potential bugs.{context_block}\n\n"
            f"Return ONLY valid JSON with this schema:\n"
            f'{{"issues": ["..."], "suggestions": ["..."], "score": 0-100, "summary": "..."}}\n\n'
            f"Code:\n```{language}\n{code}\n```"
        )
        system = (
            "You are an expert code reviewer. "
            "Respond ONLY with a JSON object matching the requested schema."
        )
        try:
            raw = generate_response(prompt, system_prompt=system)
            return self._parse_analysis(raw)
        except Exception:
            return empty

    def check_syntax(self, code: str, language: str) -> dict:
        """
        Perform a lightweight syntax check on *code*.

        For Python a compile-only check is done locally; for other
        languages the LLM is queried.

        Args:
            code:     Source code to check.
            language: Programming language.

        Returns:
            A dict with keys:

            * ``valid``   (bool)
            * ``errors``  (list[str]) – syntax errors found
            * ``message`` (str)       – human-readable verdict
        """
        ok_result: dict = {"valid": True, "errors": [], "message": "No syntax errors found."}
        if not code.strip():
            return ok_result

        if language.lower() == "python":
            return self._python_syntax_check(code)

        prompt = (
            f"Check the following {language} code for syntax errors only.\n"
            f"Return ONLY valid JSON: "
            f'{{"valid": true/false, "errors": ["..."], "message": "..."}}\n\n'
            f"Code:\n```{language}\n{code}\n```"
        )
        system = (
            "You are a compiler. Check syntax only. "
            "Respond ONLY with the requested JSON object."
        )
        try:
            raw = generate_response(prompt, system_prompt=system)
            parsed = self._extract_json(raw)
            if parsed and "valid" in parsed:
                return {
                    "valid":   bool(parsed.get("valid", True)),
                    "errors":  list(parsed.get("errors", [])),
                    "message": str(parsed.get("message", "")),
                }
        except Exception:
            pass
        return ok_result

    def security_scan(self, code: str) -> list:
        """
        Scan *code* for common security vulnerabilities.

        Args:
            code: Source code to scan (language is inferred by the LLM).

        Returns:
            A list of vulnerability descriptions (strings).
            Empty list if no issues are found or if the LLM fails.
        """
        if not code.strip():
            return []

        prompt = (
            "Scan the following code for security vulnerabilities such as "
            "SQL injection, XSS, command injection, hardcoded credentials, "
            "insecure deserialization, path traversal, and similar issues.\n"
            "Return ONLY a JSON array of strings describing each vulnerability "
            "found. Return an empty array [] if none found.\n\n"
            f"Code:\n```\n{code}\n```"
        )
        system = (
            "You are a security auditor. "
            "Respond ONLY with a JSON array of vulnerability descriptions."
        )
        try:
            raw = generate_response(prompt, system_prompt=system)
            data = self._extract_json(raw)
            if isinstance(data, list):
                return [str(v) for v in data]
        except Exception:
            pass
        return []

    def get_fix_suggestions(self, code: str, error: str) -> str:
        """
        Ask the LLM for concrete fix suggestions for a given *error*.

        Args:
            code:  Source code that is producing the error.
            error: Error message or description.

        Returns:
            A string with fix suggestions, or an empty string on failure.
        """
        if not code.strip() or not error.strip():
            return ""

        prompt = (
            f"The following code has this error:\n{error}\n\n"
            f"Explain concisely how to fix it and provide corrected code if possible.\n\n"
            f"Code:\n```\n{code}\n```"
        )
        system = "You are an expert debugging assistant. Be concise and actionable."
        try:
            return generate_response(prompt, system_prompt=system) or ""
        except Exception:
            return ""

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _python_syntax_check(code: str) -> dict:
        """Compile-only syntax check for Python (no LLM call)."""
        try:
            compile(code, "<string>", "exec")
            return {"valid": True, "errors": [], "message": "No syntax errors found."}
        except SyntaxError as exc:
            msg = f"SyntaxError at line {exc.lineno}: {exc.msg}"
            return {"valid": False, "errors": [msg], "message": msg}
        except Exception as exc:
            return {"valid": False, "errors": [str(exc)], "message": str(exc)}

    @staticmethod
    def _extract_json(text: str) -> Optional[object]:
        """
        Best-effort extraction of a JSON value from *text*.

        Handles LLM responses that wrap the JSON in markdown fences.
        """
        # Strip markdown code fences
        text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Find first JSON-like substring
        for pattern in (r"\{.*\}", r"\[.*\]"):
            m = re.search(pattern, text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group())
                except json.JSONDecodeError:
                    pass
        return None

    def _parse_analysis(self, raw: str) -> dict:
        """Parse LLM response into the analysis schema."""
        fallback = {"issues": [], "suggestions": [], "score": 0, "summary": raw[:500]}
        parsed = self._extract_json(raw)
        if not isinstance(parsed, dict):
            return fallback
        return {
            "issues":      list(parsed.get("issues", [])),
            "suggestions": list(parsed.get("suggestions", [])),
            "score":       int(parsed.get("score", 0)),
            "summary":     str(parsed.get("summary", "")),
        }
