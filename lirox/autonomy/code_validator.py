"""Lirox Autonomy — Code Validator.

Checks generated code for syntax errors, import availability,
type-hint consistency, and unsafe operations before execution.
"""
from __future__ import annotations

import ast
import importlib
import re
from dataclasses import dataclass, field
from typing import List


# Patterns that should be refused in generated code
_DANGEROUS_PATTERNS = [
    r"\bos\.system\b",
    r"\bsubprocess\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\b__import__\s*\(",
    r"\bopen\s*\(.*['\"]w['\"]",   # writing to arbitrary files
    r"\bshutil\.rmtree\b",
    r"\bpathlib\.Path\b.*\.unlink\b",
    r"\bsocket\b",
]


@dataclass
class ValidationResult:
    valid:    bool
    errors:   List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class CodeValidator:
    """Validate Python source before it is executed or applied."""

    # ── Public API ─────────────────────────────────────────────────────────

    def validate(self, source: str, security_scan: bool = True) -> ValidationResult:
        result = ValidationResult(valid=True)

        self._check_syntax(source, result)
        if not result.valid:
            return result  # No point continuing if code won't even parse

        self._check_imports(source, result)
        if security_scan:
            self._check_security(source, result)
        self._check_type_hints(source, result)

        return result

    # ── Checks ─────────────────────────────────────────────────────────────

    def _check_syntax(self, source: str, result: ValidationResult) -> None:
        try:
            ast.parse(source)
        except SyntaxError as exc:
            result.valid = False
            result.errors.append(f"SyntaxError at line {exc.lineno}: {exc.msg}")

    def _check_imports(self, source: str, result: ValidationResult) -> None:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mod = None
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        mod = alias.name.split(".")[0]
                        if not self._is_importable(mod):
                            result.warnings.append(
                                f"Import may not be available: {alias.name}"
                            )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    mod = node.module.split(".")[0]
                    if not self._is_importable(mod):
                        result.warnings.append(
                            f"Import may not be available: {node.module}"
                        )

    def _check_security(self, source: str, result: ValidationResult) -> None:
        for pattern in _DANGEROUS_PATTERNS:
            if re.search(pattern, source):
                result.valid = False
                result.errors.append(
                    f"Security: dangerous pattern detected — {pattern}"
                )

    def _check_type_hints(self, source: str, result: ValidationResult) -> None:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.returns is None and node.name not in ("__init__", "__new__"):
                    result.warnings.append(
                        f"Function '{node.name}' is missing a return type hint."
                    )

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _is_importable(module_name: str) -> bool:
        """Return True if the top-level module exists in the environment."""
        try:
            importlib.util.find_spec(module_name)
            return True
        except (ModuleNotFoundError, ValueError):
            return False
