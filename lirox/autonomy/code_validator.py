"""Lirox Autonomy — Code Validator.

Pure-Python syntax and security checking:
  - Syntax validation via compile()
  - Import availability check
  - Security scan (block dangerous builtins)
  - Type-hint audit

No external services or network calls.
"""
from __future__ import annotations

import ast
import importlib.util
from typing import Any, Dict, List

# Dangerous patterns that are blocked in generated / user-supplied code
_BLOCKED_CALLS = frozenset({
    "eval", "exec", "__import__", "compile",
    "open",          # controlled via filesystem_manager instead
    "os.system",     "os.popen",
    "subprocess.run", "subprocess.call", "subprocess.Popen",  # use CodeExecutor
    "shutil.rmtree", "shutil.move",
})

_BLOCKED_ATTR_ACCESS = frozenset({
    "__class__", "__bases__", "__subclasses__", "__globals__", "__builtins__",
})


class ValidationResult:
    """Result of a code validation run."""

    def __init__(self) -> None:
        self.valid:    bool       = True
        self.errors:   List[str]  = []
        self.warnings: List[str]  = []
        self.info:     List[str]  = []

    def add_error(self, msg: str) -> None:
        self.valid = False
        self.errors.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def add_info(self, msg: str) -> None:
        self.info.append(msg)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid":    self.valid,
            "errors":   self.errors,
            "warnings": self.warnings,
            "info":     self.info,
        }

    def summary(self) -> str:
        status = "✓ Valid" if self.valid else "✖ Invalid"
        lines  = [status]
        for e in self.errors:
            lines.append(f"  ERROR  : {e}")
        for w in self.warnings:
            lines.append(f"  WARN   : {w}")
        for i in self.info:
            lines.append(f"  INFO   : {i}")
        return "\n".join(lines)


class CodeValidator:
    """Validate Python source code without executing it."""

    # ── Syntax ─────────────────────────────────────────────────────────────

    def check_syntax(self, source: str, filename: str = "<code>") -> ValidationResult:
        """Check whether *source* is syntactically valid Python."""
        result = ValidationResult()
        try:
            compile(source, filename, "exec")
        except SyntaxError as exc:
            result.add_error(f"SyntaxError at line {exc.lineno}: {exc.msg}")
        return result

    # ── Import availability ────────────────────────────────────────────────

    def check_imports(self, source: str) -> ValidationResult:
        """Check whether all top-level imports in *source* are available."""
        result = ValidationResult()
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            result.add_error(f"SyntaxError (cannot check imports): {exc}")
            return result

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self._check_module(alias.name, result)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    self._check_module(node.module.split(".")[0], result)
        return result

    def _check_module(self, module: str, result: ValidationResult) -> None:
        if importlib.util.find_spec(module) is None:
            result.add_warning(f"Module not available: {module}")

    # ── Security scan ──────────────────────────────────────────────────────

    def security_scan(self, source: str) -> ValidationResult:
        """Detect dangerous patterns in *source* using AST analysis."""
        result = ValidationResult()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return result  # syntax errors caught elsewhere

        for node in ast.walk(tree):
            # Direct calls: eval(...), exec(...), __import__(...)
            if isinstance(node, ast.Call):
                name = self._call_name(node)
                if name in _BLOCKED_CALLS:
                    lineno = getattr(node, "lineno", "?")
                    result.add_warning(
                        f"Potentially dangerous call `{name}` at line {lineno}"
                    )
            # Attribute access: obj.__class__, obj.__subclasses__(), etc.
            if isinstance(node, ast.Attribute):
                if node.attr in _BLOCKED_ATTR_ACCESS:
                    lineno = getattr(node, "lineno", "?")
                    result.add_warning(
                        f"Potentially unsafe attribute `{node.attr}` at line {lineno}"
                    )
        return result

    @staticmethod
    def _call_name(node: ast.Call) -> str:
        """Extract the dotted name from a Call node, or empty string."""
        func = node.func
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            if isinstance(func.value, ast.Name):
                return f"{func.value.id}.{func.attr}"
        return ""

    # ── Type-hint audit ────────────────────────────────────────────────────

    def check_type_hints(self, source: str) -> ValidationResult:
        """Report functions and methods that are missing type annotations."""
        result = ValidationResult()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return result

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                missing: List[str] = []
                for arg in node.args.args:
                    if arg.arg != "self" and arg.annotation is None:
                        missing.append(arg.arg)
                if node.returns is None:
                    missing.append("→ return type")
                if missing:
                    result.add_info(
                        f"Function `{node.name}` (line {node.lineno}) missing hints"
                        f" for: {', '.join(missing)}"
                    )
        return result

    # ── Combined ───────────────────────────────────────────────────────────

    def full_check(self, source: str, filename: str = "<code>") -> ValidationResult:
        """Run syntax, import, security, and type-hint checks on *source*."""
        result = ValidationResult()

        for sub in (
            self.check_syntax(source, filename),
            self.check_imports(source),
            self.security_scan(source),
            self.check_type_hints(source),
        ):
            result.errors.extend(sub.errors)
            result.warnings.extend(sub.warnings)
            result.info.extend(sub.info)
            if sub.errors:
                result.valid = False

        return result
