"""Lirox Autonomy — Code Intelligence.

Pure-Python AST-based project analysis:
  - Module inventory (classes, functions, imports)
  - Dependency mapping
  - Style detection (type hints, docstrings, dataclasses)
  - High-level project summary

No external services are required.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional

from lirox.autonomy.filesystem_manager import FilesystemManager

_fs = FilesystemManager()


class ModuleInfo:
    """Structural summary of a single Python module."""

    __slots__ = ("path", "classes", "functions", "imports", "loc", "has_type_hints",
                 "has_docstrings", "has_dataclasses", "errors")

    def __init__(self, path: str) -> None:
        self.path:            str       = path
        self.classes:         List[str] = []
        self.functions:       List[str] = []
        self.imports:         List[str] = []
        self.loc:             int       = 0
        self.has_type_hints:  bool      = False
        self.has_docstrings:  bool      = False
        self.has_dataclasses: bool      = False
        self.errors:          List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path":            self.path,
            "classes":         self.classes,
            "functions":       self.functions,
            "imports":         self.imports,
            "loc":             self.loc,
            "has_type_hints":  self.has_type_hints,
            "has_docstrings":  self.has_docstrings,
            "has_dataclasses": self.has_dataclasses,
            "errors":          self.errors,
        }


class CodeIntelligence:
    """Analyse an entire Python project using AST (no external services)."""

    def __init__(self, root: Optional[str] = None) -> None:
        if root is None:
            try:
                from lirox.config import PROJECT_ROOT
                root = str(Path(PROJECT_ROOT) / "lirox")
            except Exception:
                root = "."
        self.root = root
        self._modules: Optional[List[ModuleInfo]] = None

    # ── Internal helpers ───────────────────────────────────────────────────

    def _analyse_module(self, path: str) -> ModuleInfo:
        info = ModuleInfo(path)
        ok, source = _fs.read_file(path)
        if not ok:
            info.errors.append(source)
            return info

        lines = source.splitlines()
        info.loc = len(lines)

        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as exc:
            info.errors.append(f"SyntaxError: {exc}")
            return info

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                info.classes.append(node.name)
                if any(isinstance(d, ast.Name) and d.id == "dataclass"
                       for d in node.decorator_list):
                    info.has_dataclasses = True
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                info.functions.append(node.name)
                # Check for type annotations
                fn: ast.FunctionDef = node  # type: ignore[assignment]
                if fn.returns is not None or any(
                    a.annotation for a in fn.args.args
                ):
                    info.has_type_hints = True
                # Check for docstring
                if (fn.body and isinstance(fn.body[0], ast.Expr)
                        and isinstance(fn.body[0].value, ast.Constant)
                        and isinstance(fn.body[0].value.value, str)):
                    info.has_docstrings = True
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    info.imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    info.imports.append(node.module)

        return info

    # ── Public API ─────────────────────────────────────────────────────────

    def scan(self) -> List[ModuleInfo]:
        """Scan the project root and return a list of ModuleInfo objects."""
        if self._modules is not None:
            return self._modules

        py_files = _fs.get_python_files(self.root)
        self._modules = [self._analyse_module(p) for p in py_files]
        return self._modules

    def dependency_map(self) -> Dict[str, List[str]]:
        """Return ``{module_path: [imported_modules]}`` for the whole project."""
        result: Dict[str, List[str]] = {}
        for mod in self.scan():
            # Only keep intra-project imports (those starting with "lirox")
            internal = [imp for imp in mod.imports if imp.startswith("lirox")]
            if internal:
                result[mod.path] = internal
        return result

    def style_profile(self) -> Dict[str, Any]:
        """Return aggregate style statistics for the project."""
        modules = self.scan()
        if not modules:
            return {}
        type_hint_pct  = sum(m.has_type_hints  for m in modules) / len(modules) * 100
        docstring_pct  = sum(m.has_docstrings  for m in modules) / len(modules) * 100
        dataclass_pct  = sum(m.has_dataclasses for m in modules) / len(modules) * 100
        return {
            "total_modules":    len(modules),
            "total_loc":        sum(m.loc for m in modules),
            "total_classes":    sum(len(m.classes) for m in modules),
            "total_functions":  sum(len(m.functions) for m in modules),
            "type_hints_pct":   round(type_hint_pct, 1),
            "docstrings_pct":   round(docstring_pct, 1),
            "dataclasses_pct":  round(dataclass_pct, 1),
        }

    def summary(self) -> str:
        """Return a human-readable Markdown summary of the project."""
        profile = self.style_profile()
        if not profile:
            return "No Python files found."

        lines = [
            f"## Project Analysis — `{self.root}`\n",
            f"- **Modules**  : {profile['total_modules']}",
            f"- **Lines**    : {profile['total_loc']:,}",
            f"- **Classes**  : {profile['total_classes']}",
            f"- **Functions**: {profile['total_functions']}",
            f"- **Type hints**: {profile['type_hints_pct']}% of modules",
            f"- **Docstrings**: {profile['docstrings_pct']}% of modules",
        ]
        return "\n".join(lines)

    def find_module(self, name: str) -> Optional[ModuleInfo]:
        """Return the ModuleInfo whose path ends with *name*.py, or None."""
        for mod in self.scan():
            if Path(mod.path).stem == name:
                return mod
        return None
