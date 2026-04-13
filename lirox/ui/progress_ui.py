"""Lirox UI — Progress Indicators."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from rich.console import Console
from rich.markup import escape

console = Console()

_CLR_DIM  = "dim #94a3b8"
_CLR_INFO = "bold #60a5fa"


def render_progress_step(step: str, total: int, current: int, label: str = "") -> None:
    """Print a compact progress line: [2/5] Generating code…"""
    pct  = int(current / total * 100) if total else 0
    bar  = "█" * (pct // 10) + "░" * (10 - pct // 10)
    msg  = f"  [{_CLR_DIM}][{current}/{total}] {bar} {escape(label or step)}[/]"
    console.print(msg)


@contextmanager
def progress_status(label: str) -> Generator[None, None, None]:
    """Context manager that shows a Rich spinner while work is being done."""
    with console.status(f"[{_CLR_INFO}]{escape(label)}[/]", spinner="dots") as s:
        yield s


def render_step_execution(message: str) -> None:
    console.print(f"  [{_CLR_DIM}]  ├─ ▶ {escape(message)}[/]")


def render_deep_thinking(message: str) -> None:
    """Display an advanced/deep-thinking progress message."""
    console.print(f"  [bold #a78bfa]  🧠 {escape(message)}[/]")
