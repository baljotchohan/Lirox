"""Lirox v2.0 — Advanced Thinking Display

Professional, classy terminal UI for multi-agent reasoning:
  - Live progress bars per agent (with spinner + percentage)
  - Real-time status panel with streaming updates
  - Smooth transitions between phases
  - Beautiful expanded view for /expand command
  - Professional color scheme
"""
from __future__ import annotations

import time
from typing import Dict, List, Any, Optional

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich.text import Text
from rich.progress import (
    Progress, SpinnerColumn, BarColumn,
    TextColumn, TimeElapsedColumn, TaskID,
)
from rich.align import Align
from rich.box import ROUNDED, HEAVY, DOUBLE
from rich import box


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AGENT COLORS — Professional palette
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AGENT_COLORS: Dict[str, str] = {
    "Architect":  "bright_cyan",
    "Builder":    "bright_green",
    "Researcher": "bright_blue",
    "Executor":   "bright_magenta",
    "Verifier":   "bright_yellow",
    "System":     "white",
}


class AdvancedThinkingDisplay:
    """
    Classy, professional thinking display with:
    - Live multi-agent progress bars
    - Real-time status streaming
    - Beautiful final synthesis panel
    - Full expanded reasoning view
    """

    def __init__(self):
        self.console = Console()

    # ──────────────────────────────────────────────────────────
    # COMPACT INDICATOR (one-line, shown before live display)
    # ──────────────────────────────────────────────────────────

    def show_thinking_compact(self, task: str, num_agents: int = 5):
        """One-line thinking indicator with expand hint."""
        text = Text()
        text.append("⟳ ", style="bold cyan")
        text.append("Thinking ", style="bold white")
        text.append(f"({num_agents} agents) ", style="dim")
        text.append("· ", style="dim white")
        text.append("/expand thinking", style="italic yellow")
        text.append(" for details", style="dim")
        self.console.print(text)

    # ──────────────────────────────────────────────────────────
    # LIVE DISPLAY (full progress bars during thinking)
    # ──────────────────────────────────────────────────────────

    def create_live_progress(self) -> tuple:
        """
        Create progress bar tracker and agent task handles.

        Returns:
            (progress, agent_tasks, status_text)
        """
        progress = Progress(
            SpinnerColumn(spinner_name="dots"),
            TextColumn("[bold]{task.description}"),
            BarColumn(bar_width=30, complete_style="green", finished_style="bold green"),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            expand=False,
        )

        agent_tasks: Dict[str, TaskID] = {}
        agent_names = ["Architect", "Builder", "Researcher", "Executor", "Verifier"]

        for name in agent_names:
            color = AGENT_COLORS.get(name, "white")
            agent_tasks[name] = progress.add_task(
                f"[{color}]{name:<12}",
                total=100,
            )

        return progress, agent_tasks

    def build_live_layout(self, progress, status_msg: str = "Initializing agents..."):
        """Build the full live layout with header, progress, and status."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="agents", size=9),
            Layout(name="status", size=5),
        )

        # Header
        header = Panel(
            Align.center(
                Text("🧠 MULTI-AGENT REASONING", style="bold white"),
                vertical="middle",
            ),
            style="bold cyan",
            box=HEAVY,
        )
        layout["header"].update(header)

        # Progress bars
        layout["agents"].update(Panel(progress, border_style="dim", box=ROUNDED))

        # Status
        status_panel = Panel(
            Text(status_msg, style="dim"),
            title="[bold white]Status",
            border_style="dim",
            box=ROUNDED,
        )
        layout["status"].update(status_panel)

        return layout

    def update_status(self, layout: Layout, icon: str, message: str, border: str = "cyan"):
        """Update the status panel in the live layout."""
        status_text = Text()
        status_text.append(f"{icon} ", style="bold")
        status_text.append(message, style="white")

        status_panel = Panel(
            status_text,
            title="[bold white]Status",
            border_style=border,
            box=ROUNDED,
        )
        layout["status"].update(status_panel)

    def show_synthesis_panel(self, layout: Layout, decision: str, confidence: int, elapsed: float):
        """Replace the status panel with the final synthesis."""
        synth = Text()
        synth.append("✓ ", style="bold green")
        synth.append("Decision: ", style="bold white")
        synth.append(decision[:120], style="green")
        synth.append(f"\n\nConfidence: {confidence}%", style="dim")
        synth.append(f" · Time: {elapsed:.1f}s", style="dim")

        synthesis_panel = Panel(
            synth,
            title="[bold green]Synthesis",
            border_style="bold green",
            box=HEAVY,
        )
        layout["status"].update(synthesis_panel)

    # ──────────────────────────────────────────────────────────
    # EXPANDED VIEW (for /expand thinking command)
    # ──────────────────────────────────────────────────────────

    def show_expanded_result(self, result: Dict[str, Any]):
        """
        Show detailed expanded view of thinking result.

        Args:
            result: Output from RealThinkingEngine.think_and_decide() 'data' dict.
                    Expected keys: agent_views, debate, synthesis, decision, time_taken
        """
        self.console.print()

        # ── Title ──
        title = Panel(
            Align.center(
                Text("🧠 DETAILED REASONING", style="bold white"),
                vertical="middle",
            ),
            style="bold cyan",
            box=DOUBLE,
        )
        self.console.print(title)

        # ── Agent Perspectives ──
        self.console.print("\n[bold white]Agent Perspectives:[/bold white]\n")

        agent_views = result.get("agent_views", {})
        for agent_name, view in agent_views.items():
            color = AGENT_COLORS.get(agent_name, "white")

            table = Table(
                title=f"🤖 {agent_name}",
                title_style=f"bold {color}",
                box=ROUNDED,
                border_style=color,
                show_header=False,
                padding=(0, 1),
            )
            table.add_column("Field", style="dim", width=12)
            table.add_column("Value", style="white")

            summary = view.get("summary", "No summary")
            analysis = view.get("analysis", "No analysis")
            concerns = view.get("concerns", "None identified")

            table.add_row("Summary", f"[bold]{summary}[/bold]")
            table.add_row("Analysis", analysis[:300])
            table.add_row("Concerns", concerns)

            self.console.print(table)
            self.console.print()

        # ── Debates ──
        debate = result.get("debate", {})
        conflicts = debate.get("conflicts", [])

        if conflicts:
            self.console.print("[bold yellow]💬 Debates:[/bold yellow]\n")
            for conflict in conflicts:
                agent_a = conflict.get("agent_a", "Agent A")
                agent_b = conflict.get("agent_b", "Agent B")
                issue = conflict.get("conflict", conflict.get("issue", "Unknown"))
                resolution = conflict.get("resolution", "Resolved via consensus")

                debate_panel = Panel(
                    f"[bold]{agent_a}[/bold] vs [bold]{agent_b}[/bold]\n\n"
                    f"[yellow]Conflict:[/yellow] {issue}\n\n"
                    f"[green]Resolution:[/green] {resolution}",
                    border_style="yellow",
                    box=ROUNDED,
                )
                self.console.print(debate_panel)
                self.console.print()
        else:
            self.console.print("[dim]No conflicts detected — all agents aligned.[/dim]\n")

        # ── Synthesis ──
        self.console.print("[bold green]🎯 Final Synthesis:[/bold green]\n")

        synthesis = result.get("synthesis", {})
        if isinstance(synthesis, dict):
            decision = synthesis.get("final_decision", result.get("decision", ""))
            reasoning = synthesis.get("reasoning", "")
            confidence = synthesis.get("confidence", 0)
        else:
            decision = result.get("decision", str(synthesis))
            reasoning = ""
            confidence = 0

        elapsed = result.get("time_taken", 0)
        views_count = len(agent_views)

        synthesis_panel = Panel(
            f"[bold white]{decision}[/bold white]\n\n"
            f"{reasoning}\n\n"
            f"[dim]Confidence: {confidence}% · "
            f"Agents: {views_count} · "
            f"Total time: {elapsed:.1f}s[/dim]",
            border_style="bold green",
            box=HEAVY,
        )
        self.console.print(synthesis_panel)
        self.console.print()
