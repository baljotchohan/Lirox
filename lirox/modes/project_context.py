"""Lirox — Project Context (.liroxrc)
Auto-loads project-specific instructions from .liroxrc or LIROX.md in
the current workspace, injecting them into every query as system context.

Features:
    - Auto-detection on startup/workspace change
    - /init-context  — Generate a .liroxrc from your codebase automatically
    - /show-context  — Display the active project context
    - /clear-context — Forget the project context for this session
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.rule import Rule

# ─────────────────────────────────────────────────────────────
# State
# ─────────────────────────────────────────────────────────────
_active_context: Optional[str] = None
_active_context_path: Optional[str] = None

_FILENAMES = [".liroxrc", "LIROX.md", ".lirox", "lirox.md", ".lirox.md"]


def _find_context_file(workspace: Optional[str] = None) -> Optional[Path]:
    """Search for a project context file in the workspace or cwd."""
    search_dirs = []
    if workspace:
        search_dirs.append(Path(workspace))
    search_dirs.append(Path.cwd())
    # Also check git root
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            search_dirs.append(Path(result.stdout.strip()))
    except Exception:
        pass

    for d in search_dirs:
        for fname in _FILENAMES:
            p = d / fname
            if p.exists() and p.is_file():
                return p
    return None


def load_context(workspace: Optional[str] = None, silent: bool = False) -> Optional[str]:
    """Load project context from .liroxrc file. Returns the context string or None."""
    global _active_context, _active_context_path

    path = _find_context_file(workspace)
    if not path:
        return None

    try:
        content = path.read_text(encoding="utf-8", errors="replace").strip()
        if not content:
            return None
        _active_context = content
        _active_context_path = str(path)
        if not silent:
            from lirox.ui.display import console as _console
            _console.print(f"  [dim #a78bfa]📋 Project context loaded from[/] [bold]{path.name}[/]")
        return content
    except Exception:
        return None


def get_context() -> Optional[str]:
    """Return currently active project context (for injection into prompts)."""
    return _active_context


def get_context_path() -> Optional[str]:
    return _active_context_path


def inject_into_prompt(system_prompt: str) -> str:
    """Prepend project context to a system prompt if available."""
    ctx = get_context()
    if not ctx:
        return system_prompt
    return (
        f"## Project Context (from {_active_context_path or '.liroxrc'})\n"
        f"{ctx}\n\n"
        f"---\n\n"
        f"{system_prompt}"
    )


def clear_context() -> None:
    global _active_context, _active_context_path
    _active_context = None
    _active_context_path = None


# ─────────────────────────────────────────────────────────────
# /init-context — AI generates a .liroxrc from the codebase
# ─────────────────────────────────────────────────────────────
def init_context(console: Console, workspace: Optional[str] = None) -> None:
    """Analyze the codebase and generate a .liroxrc file."""
    import subprocess

    root = workspace or str(Path.cwd())

    # Gather codebase signals
    signals = []

    # Check for package files to detect stack
    stack_files = {
        "package.json":     "Node.js/JavaScript",
        "pyproject.toml":   "Python",
        "requirements.txt": "Python",
        "Cargo.toml":       "Rust",
        "go.mod":           "Go",
        "pom.xml":          "Java/Maven",
        "build.gradle":     "Java/Gradle",
        "Gemfile":          "Ruby",
        "composer.json":    "PHP",
    }
    detected_stack = []
    for fname, lang in stack_files.items():
        if (Path(root) / fname).exists():
            detected_stack.append(lang)

    # Read key files (README, pyproject, package.json) for context
    key_files_content = []
    for fname in ["README.md", "pyproject.toml", "package.json", "go.mod"]:
        p = Path(root) / fname
        if p.exists():
            try:
                content = p.read_text(encoding="utf-8", errors="replace")[:1500]
                key_files_content.append(f"### {fname}\n{content}")
            except Exception:
                pass

    # Get directory structure
    try:
        result = subprocess.run(
            ["find", root, "-maxdepth", "2", "-type", "f",
             "-not", "-path", "*/.git/*",
             "-not", "-path", "*/node_modules/*",
             "-not", "-path", "*/__pycache__/*",
             "-not", "-path", "*/.venv/*"],
            capture_output=True, text=True, timeout=5
        )
        file_tree = result.stdout[:2000]
    except Exception:
        file_tree = ""

    prompt = (
        "You are analyzing a software project to generate a LIROX.md context file.\n\n"
        f"Detected stack: {', '.join(detected_stack) or 'Unknown'}\n\n"
        f"File structure:\n```\n{file_tree}\n```\n\n"
        f"Key files:\n{''.join(key_files_content)}\n\n"
        "Generate a .liroxrc / LIROX.md file that will help an AI assistant "
        "understand this project. Include these sections:\n\n"
        "# Project Context\n"
        "## Stack\n(languages, frameworks, key libraries)\n\n"
        "## Architecture\n(how the project is structured, key modules)\n\n"
        "## Conventions\n(naming, code style, patterns used)\n\n"
        "## Important Rules\n(things AI should NEVER do in this project)\n\n"
        "## Key Files\n(most important files and what they do)\n\n"
        "## Current Focus\n(what's actively being worked on — leave blank if unknown)\n\n"
        "Be concise but precise. This file will be injected into every AI query."
    )

    console.print("[dim #a78bfa]Analyzing codebase…[/]")

    from lirox.utils.llm import generate_response
    context_content = generate_response(prompt, provider="auto").strip()

    output_path = Path(root) / "LIROX.md"
    output_path.write_text(context_content, encoding="utf-8")

    console.print()
    console.print(Rule("[bold #FFC107]Project Context Generated[/]", style="#FFC107 dim"))
    console.print(Markdown(context_content[:1000] + ("…" if len(context_content) > 1000 else "")))
    console.print()
    console.print(f"  [bold #10b981]✓ Saved to[/] [bold]{output_path}[/]")
    console.print("  [dim]This file will be auto-loaded next time you run lirox in this directory.[/]")

    # Load it immediately
    global _active_context, _active_context_path
    _active_context = context_content
    _active_context_path = str(output_path)


# ─────────────────────────────────────────────────────────────
# Command handlers
# ─────────────────────────────────────────────────────────────
def show_context(console: Console) -> None:
    if not _active_context:
        console.print("[dim]No project context loaded.[/]")
        console.print("[dim]Run [bold]/init-context[/] to generate one, or create a [bold]LIROX.md[/] file.[/]")
        return
    console.print()
    console.print(Rule(f"[bold #FFC107]Project Context[/] [dim]({_active_context_path})[/]", style="#FFC107 dim"))
    console.print(Markdown(_active_context))
    console.print()


def handle_context_command(cmd: str, console: Console, workspace: Optional[str] = None) -> None:
    parts = cmd.strip().split()
    base = parts[0].lower()

    if base == "/init-context":
        init_context(console, workspace)
    elif base == "/show-context":
        show_context(console)
    elif base == "/clear-context":
        clear_context()
        console.print("[bold #10b981]✓[/] Project context cleared.")
