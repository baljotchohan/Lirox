"""Repo map — Aider-style codebase understanding, dependency-free.

Aider's signature memory/context trick is a concise repository map (built with
tree-sitter) so the model understands a codebase's shape without loading every
file into context. Lirox has no tree-sitter dependency, so this builds an
equivalent map with the standard library: Python's ``ast`` module for accurate
class/function signatures, and light regex scanning for other common
languages. Good enough to orient an agent before it starts reading files.
"""
from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import List

_IGNORE_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "env",
    "dist", "build", ".pytest_cache", ".mypy_cache", "egg-info",
    ".idea", ".vscode", "site-packages",
}

_CODE_EXT = {
    ".py": "python", ".js": "javascript", ".ts": "typescript", ".tsx": "typescript",
    ".jsx": "javascript", ".go": "go", ".rs": "rust", ".java": "java",
    ".rb": "ruby", ".php": "php", ".c": "c", ".cpp": "cpp", ".h": "c",
}

# Lightweight top-level declaration finders for non-Python languages.
_GENERIC_DECL_RE = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?"
    r"(?:function|class|def|interface|type|struct|impl|fn|public\s+\w+\s+\w+\s*\()"
    r"\s*([A-Za-z_][A-Za-z0-9_]*)",
)


def _python_signatures(path: Path) -> List[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        return []
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = ", ".join(a.arg for a in node.args.args)
            prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            out.append(f"  {prefix} {node.name}({args})")
        elif isinstance(node, ast.ClassDef):
            bases = ", ".join(getattr(b, "id", getattr(b, "attr", "")) for b in node.bases)
            out.append(f"  class {node.name}({bases})" if bases else f"  class {node.name}")
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    args = ", ".join(a.arg for a in sub.args.args)
                    out.append(f"    def {sub.name}({args})")
    return out


def _generic_signatures(path: Path) -> List[str]:
    out = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            m = _GENERIC_DECL_RE.match(line)
            if m:
                out.append(f"  {line.strip()[:100]}")
    except Exception:  # noqa: BLE001
        pass
    return out


def build_repo_map(root: str = ".", max_files: int = 150, max_chars: int = 6000) -> str:
    """Walk ``root`` and produce a concise map of files and their top-level
    symbols, capped to ``max_chars`` so it's cheap to inject into a prompt."""
    root_path = Path(root).expanduser()
    if not root_path.exists():
        return f"(root '{root}' does not exist)"

    lines: List[str] = []
    file_count = 0

    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS and not d.startswith(".")]
        rel_dir = os.path.relpath(dirpath, root_path)
        for fname in sorted(filenames):
            ext = Path(fname).suffix
            if ext not in _CODE_EXT:
                continue
            if file_count >= max_files:
                lines.append("… (further files omitted, map size-capped) …")
                return _cap(lines, max_chars)
            file_count += 1
            fpath = Path(dirpath) / fname
            rel = fpath.relative_to(root_path)
            lines.append(str(rel))
            sigs = _python_signatures(fpath) if ext == ".py" else _generic_signatures(fpath)
            lines.extend(sigs[:12])
            if len("\n".join(lines)) > max_chars:
                return _cap(lines, max_chars)

    if not lines:
        return "(no recognized source files found)"
    return _cap(lines, max_chars)


def _cap(lines: List[str], max_chars: int) -> str:
    text = "\n".join(lines)
    return text[:max_chars] + ("\n… (truncated)" if len(text) > max_chars else "")


def repo_map_tool(root: str = ".") -> "ExecutionReceipt":  # type: ignore[name-defined]
    from lirox.verify.receipt import ExecutionReceipt
    text = build_repo_map(root or ".")
    return ExecutionReceipt(tool="repo_map", ok=True, verified=True, message=text)


def register_repo_map_tool(registry) -> None:
    from lirox.agentic.tools import DANGER_SAFE
    registry.add(
        "repo_map",
        "Get a concise map of the codebase: files with their top-level "
        "classes/functions. Use this FIRST to orient before reading individual "
        "files on unfamiliar codebases.",
        {"root": {"type": "string", "description": "Directory to map.", "required": False}},
        repo_map_tool, danger=DANGER_SAFE,
    )
