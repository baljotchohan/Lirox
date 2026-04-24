"""Lirox v2.0 — Thinking Controls

Keyboard shortcuts and help for the thinking display.
"""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box


class ThinkingControls:
    """
    Keyboard shortcuts reference for thinking display.

    Shortcuts:
      /expand thinking  — Show full agent reasoning trace
      /thinking-help    — Show this help panel
    """

    @staticmethod
    def show_help():
        """Display keyboard shortcuts help panel."""
        console = Console()

        table = Table(
            show_header=True,
            header_style="bold cyan",
            box=box.ROUNDED,
            border_style="cyan",
            padding=(0, 1),
        )
        table.add_column("Command", style="bold yellow", width=22)
        table.add_column("Action", style="white")

        table.add_row("/expand thinking", "Show full agent reasoning trace")
        table.add_row("/thinking-help", "Show this help panel")

        panel = Panel(
            table,
            title="[bold cyan]🧠 Thinking Display Controls[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
        console.print(panel)

        console.print("\n[dim]During thinking, you'll see:[/dim]")
        console.print("  [cyan]⠋[/] [bold]Agent[/]     ████████░░░░  60%  — Agent is still analyzing")
        console.print("  [green]✓[/] [bold]Agent[/]     ████████████ 100%  — Agent analysis complete")
        console.print("  [yellow]💬[/] Debate detected between agents")
        console.print("  [green]🎯[/] Final synthesis and decision\n")
