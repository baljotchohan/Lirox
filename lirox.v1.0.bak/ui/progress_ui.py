"""Lirox UI — Progress Indicators.

Rich progress bars and step indicators for long-running autonomous operations.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Iterable, Optional

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

_console = Console()


@contextmanager
def step_progress(
    description: str = "Working…",
    total: Optional[int] = None,
) -> Generator["Progress", None, None]:
    """Context manager that displays a Rich progress bar.

    Usage::

        with step_progress("Scanning files…", total=100) as prog:
            task = prog.add_task("scan", total=100)
            for i in range(100):
                prog.advance(task)
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold white]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=_console,
        transient=True,
    ) as progress:
        yield progress


def show_step(step: int, total: int, description: str) -> None:
    """Print a single-line step indicator."""
    _console.print(f"  [bold #FFC107][{step}/{total}][/] {description}")


def show_deep_thinking(message: str) -> None:
    """Render a deep-thinking trace in a dim italic style."""
    _console.print(f"  [dim italic #a78bfa]🧠 {message[:300]}[/]")


def show_code_analysis(message: str) -> None:
    """Render a code-analysis progress message."""
    _console.print(f"  [bold cyan]🔍 {message[:200]}[/]")


def show_self_improvement(message: str) -> None:
    """Render a self-improvement progress message."""
    _console.print(f"  [bold #10b981]🔬 {message[:200]}[/]")
