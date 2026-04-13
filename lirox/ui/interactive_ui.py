"""Lirox UI — Interactive Menus.

Numbered option menus and multi-step approval flows using Rich prompts.
"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt, Prompt

_console = Console()


def numbered_menu(
    title: str,
    options: List[str],
    prompt: str = "Select option",
    allow_cancel: bool = True,
) -> Optional[int]:
    """Display a numbered menu and return the selected index (0-based), or None.

    Returns ``None`` if the user cancels (enters 0 when *allow_cancel* is True).
    """
    lines = []
    if allow_cancel:
        lines.append("  [dim]0. Cancel[/]")
    for i, opt in enumerate(options, 1):
        lines.append(f"  [bold white]{i}.[/] {opt}")

    _console.print(Panel(
        "\n".join(lines),
        title=f"[bold #FFC107]{title}[/]",
        border_style="#FFC107",
        padding=(1, 2),
    ))

    max_choice = len(options)
    while True:
        try:
            choice = IntPrompt.ask(
                f"  [bold]{prompt} (0–{max_choice})[/]",
                console=_console,
            )
        except (KeyboardInterrupt, EOFError):
            return None

        if allow_cancel and choice == 0:
            return None
        if 1 <= choice <= max_choice:
            return choice - 1   # 0-based
        _console.print(f"  [dim red]Invalid. Enter 0–{max_choice}.[/]")


def confirm(message: str, default: bool = False) -> bool:
    """Ask a yes/no question and return the answer as bool."""
    try:
        answer = Prompt.ask(
            f"  [bold]{message}[/]",
            choices=["y", "n"],
            default="y" if default else "n",
            console=_console,
        )
        return answer.lower() == "y"
    except (KeyboardInterrupt, EOFError):
        return False


def show_step_approval(
    steps: List[Tuple[str, str]],
    title: str = "Proposed Steps",
) -> List[int]:
    """Show a list of (step_description, required_tier_label) tuples and ask which
    ones to approve.

    Returns a list of approved step indices (0-based).
    """
    lines = []
    for i, (step, tier) in enumerate(steps, 1):
        lines.append(f"  [bold white]{i}.[/] {step}  [dim]({tier})[/]")

    _console.print(Panel(
        "\n".join(lines),
        title=f"[bold #FFC107]{title}[/]",
        border_style="#FFC107",
        padding=(1, 2),
    ))

    approved: List[int] = []
    for i, (step, tier) in enumerate(steps):
        ok = confirm(f"Approve step {i + 1}: {step[:60]}?", default=True)
        if ok:
            approved.append(i)

    return approved
