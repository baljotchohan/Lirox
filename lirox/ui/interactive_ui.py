"""Lirox UI — Multi-step Interactive UI.

Provides helpers for multi-step conversations, presenting numbered choices,
and guiding the user through approval flows.
"""
from __future__ import annotations

from typing import List, Optional

from rich.console import Console
from rich.markup import escape

console = Console()

_CLR_ACCENT  = "bold #FFD54F"
_CLR_WARN    = "bold #f59e0b"
_CLR_DIM     = "dim #94a3b8"
_CLR_SUCCESS = "bold #10b981"


def present_options(
    prompt: str,
    options: List[str],
    *,
    allow_skip: bool = False,
) -> Optional[int]:
    """Show numbered options and return the 1-based index chosen (or None for skip)."""
    console.print(f"\n  [{_CLR_ACCENT}]{escape(prompt)}[/]")
    for i, opt in enumerate(options, 1):
        console.print(f"    [{_CLR_DIM}]{i}.[/] {escape(opt)}")
    if allow_skip:
        console.print(f"    [{_CLR_DIM}]0.[/] Skip")

    while True:
        raw = console.input(f"  [{_CLR_WARN}]Choose (1-{len(options)}): [/]").strip()
        if allow_skip and raw == "0":
            return None
        if raw.isdigit():
            choice = int(raw)
            if 1 <= choice <= len(options):
                return choice
        console.print(f"  [{_CLR_WARN}]Please enter a number between 1 and {len(options)}.[/]")


def confirm_step(message: str, default: bool = True) -> bool:
    """Ask a yes/no question, returning the boolean answer."""
    hint = "(Y/n)" if default else "(y/N)"
    raw  = console.input(f"  [{_CLR_WARN}]⚠ {escape(message)} {hint}: [/]").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


def show_multi_step_progress(steps: List[str], current: int) -> None:
    """Render a numbered step list with the current step highlighted."""
    console.print()
    for i, step in enumerate(steps, 1):
        if i < current:
            console.print(f"  [{_CLR_SUCCESS}]✓[/] {i}. {escape(step)}")
        elif i == current:
            console.print(f"  [{_CLR_ACCENT}]▶[/] {i}. [{_CLR_ACCENT}]{escape(step)}[/]")
        else:
            console.print(f"  [{_CLR_DIM}]○ {i}. {escape(step)}[/]")
    console.print()
