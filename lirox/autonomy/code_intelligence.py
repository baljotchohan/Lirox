"""Lirox Autonomy — Code Intelligence.

Understands project structure via AST parsing, dependency mapping,
module relationships, code style detection, and auto-documentation.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── AST visitor helpers ────────────────────────────────────────────────────────

class _ImportVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.imports: List[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self.imports.append(node.module)


class _DefinitionVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.classes:   List[str] = []
        self.functions: List[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.classes.append(node.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.functions.append(node.name)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef


# ── Main class ─────────────────────────────────────────────────────────────────

class CodeIntelligence:
    """Analyse a Python project and answer questions about its structure."""

    def __init__(self, project_root: Optional[str] = None) -> None:
        if project_root is None:
            from lirox.config import PROJECT_ROOT
            project_root = PROJECT_ROOT
        self.root = Path(project_root)
        self._cache: Dict[str, Dict[str, Any]] = {}

    # ── File discovery ─────────────────────────────────────────────────────

    def list_python_files(self, subdir: str = "") -> List[Path]:
        search_root = self.root / subdir if subdir else self.root
        return sorted(
            p for p in search_root.rglob("*.py")
            if "__pycache__" not in str(p)
        )

    # ── Per-file analysis ──────────────────────────────────────────────────

    def analyse_file(self, path: Path) -> Dict[str, Any]:
        key = str(path)
        if key in self._cache:
            return self._cache[key]

        info: Dict[str, Any] = {
            "path":      str(path.relative_to(self.root)),
            "imports":   [],
            "classes":   [],
            "functions": [],
            "lines":     0,
            "docstring": "",
            "parse_error": None,
        }
        try:
            source = path.read_text(errors="replace")
            info["lines"] = source.count("\n") + 1
            tree = ast.parse(source)

            iv = _ImportVisitor()
            iv.visit(tree)
            info["imports"] = iv.imports

            dv = _DefinitionVisitor()
            dv.visit(tree)
            info["classes"]   = dv.classes
            info["functions"] = dv.functions

            # Module-level docstring
            info["docstring"] = ast.get_docstring(tree) or ""
        except SyntaxError as exc:
            info["parse_error"] = str(exc)

        self._cache[key] = info
        return info

    # ── Project-wide analysis ──────────────────────────────────────────────

    def analyse_project(self, subdir: str = "lirox") -> Dict[str, Any]:
        files  = self.list_python_files(subdir)
        result: Dict[str, Any] = {
            "total_files":     len(files),
            "total_lines":     0,
            "modules":         {},
            "dependency_map":  {},   # module -> [imports]
            "all_classes":     [],
            "all_functions":   [],
            "parse_errors":    [],
        }
        for p in files:
            info = self.analyse_file(p)
            rel  = info["path"]
            result["modules"][rel]        = info
            result["dependency_map"][rel] = info["imports"]
            result["total_lines"]        += info["lines"]
            result["all_classes"].extend(info["classes"])
            result["all_functions"].extend(info["functions"])
            if info["parse_error"]:
                result["parse_errors"].append({"file": rel, "error": info["parse_error"]})

        return result

    # ── Style detection ────────────────────────────────────────────────────

    def detect_style(self) -> Dict[str, Any]:
        """Heuristic code-style detection for the project."""
        files   = self.list_python_files("lirox")[:20]
        samples = []
        for p in files:
            try:
                samples.append(p.read_text(errors="replace"))
            except OSError:
                pass

        combined = "\n".join(samples)
        return {
            "uses_type_hints":    "-> " in combined or ": str" in combined,
            "uses_dataclass":     "@dataclass" in combined,
            "uses_slots":         "__slots__" in combined,
            "docstring_style":    "\"\"\"" if '"""' in combined else "'''",
            "indent_size":        4,
            "line_length_approx": 100,
        }

    # ── Quick summary ──────────────────────────────────────────────────────

    def summary(self, subdir: str = "lirox") -> str:
        data   = self.analyse_project(subdir)
        errors = data["parse_errors"]
        lines  = [
            f"Project root  : {self.root}",
            f"Python files  : {data['total_files']}",
            f"Total lines   : {data['total_lines']}",
            f"Classes       : {len(data['all_classes'])}",
            f"Functions     : {len(data['all_functions'])}",
        ]
        if errors:
            lines.append(f"Parse errors  : {len(errors)}")
            for e in errors[:5]:
                lines.append(f"  • {e['file']}: {e['error']}")
        return "\n".join(lines)
