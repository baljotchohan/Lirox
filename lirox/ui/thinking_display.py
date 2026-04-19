"""Lirox v1.2 — Dynamic Thinking Display

Real-time cognitive display that shows ACTUAL processing steps,
not fake theater. Adapts to query complexity.

Design principles:
  - TRIVIAL queries ("hi", "hello") → NO thinking display at all
  - SIMPLE queries ("what is Python?") → One-line spinner, disappears
  - MODERATE queries → Brief tree with 2-3 actual steps
  - COMPLEX queries (file creation, research) → Full tree with real tool calls
  - NEVER show fake percentages or strategy scoring
  - Show elapsed time — honest and useful
  - Errors shown as ✗ not ✓
"""
from __future__ import annotations

import time
from enum import Enum
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.tree import Tree


class QueryComplexity(Enum):
    TRIVIAL = "trivial"       # "hi", "hello", "thanks" — NO thinking display
    SIMPLE = "simple"         # "what is X?" — minimal 1-line display
    MODERATE = "moderate"     # "explain X in detail" — brief thinking
    COMPLEX = "complex"       # "create a presentation on X" — full display


# ── Patterns for classification ──────────────────────────────

_TRIVIAL_EXACT = frozenset([
    "hi", "hello", "hey", "thanks", "thank you", "ok", "okay",
    "bye", "yes", "no", "sure", "cool", "nice", "great", "good",
    "yo", "sup", "hm", "hmm", "yep", "nope", "yea", "yeah",
    "k", "kk", "lol", "haha", "ty", "thx", "gm", "gn",
])

_COMPLEX_KEYWORDS = [
    "create", "build", "generate", "make", "write",
    "presentation", "pdf", "pptx", "powerpoint", "slides",
    "excel", "spreadsheet", "word", "docx", "document",
    "research", "analyze", "compare", "list files",
    "run command", "execute", "install", "deploy",
]


class ThinkingDisplay:
    """
    Real-time cognitive display that shows ACTUAL processing steps.
    Adapts to query complexity.
    """

    def __init__(self, console: Console):
        self.console = console
        self.tree: Optional[Tree] = None
        self.live: Optional[Live] = None
        self.start_time: float = 0.0
        self.complexity: QueryComplexity = QueryComplexity.MODERATE
        self._step_count: int = 0

    # ── Classification ────────────────────────────────────────

    @staticmethod
    def classify_complexity(query: str) -> QueryComplexity:
        """Classify query complexity based on actual content."""
        q = query.strip().lower()

        # Trivial — greetings, single words, acknowledgments
        if q in _TRIVIAL_EXACT or len(q) <= 3:
            return QueryComplexity.TRIVIAL

        # Complex — file creation, multi-tool tasks
        if any(kw in q for kw in _COMPLEX_KEYWORDS):
            return QueryComplexity.COMPLEX

        # Simple — direct short questions
        if q.startswith(("what", "who", "when", "where", "how", "why",
                         "is ", "are ", "can ", "do ", "does ")):
            if len(query.split()) < 15:
                return QueryComplexity.SIMPLE

        return QueryComplexity.MODERATE

    # ── Lifecycle ─────────────────────────────────────────────

    def start(self, query: str):
        """Start the thinking display based on query complexity."""
        self.start_time = time.time()
        self.complexity = self.classify_complexity(query)
        self._step_count = 0

        if self.complexity == QueryComplexity.TRIVIAL:
            # No thinking display at all — instant response
            return

        if self.complexity == QueryComplexity.SIMPLE:
            # Minimal — just a status spinner (handled externally via console.status)
            return

        # For MODERATE and COMPLEX, show the tree
        self.tree = Tree(
            f"[bold cyan]🧠 Thinking[/bold cyan]",
            guide_style="dim",
        )
        self.live = Live(
            self.tree, console=self.console,
            refresh_per_second=8, transient=True,
        )
        self.live.start()

    def add_step(self, icon: str, message: str, status: str = "running"):
        """Add a real processing step as it happens."""
        if self.tree is None:
            return

        if status == "running":
            label = f"[yellow]{icon}[/yellow] [dim]{message}[/dim]"
        elif status == "done":
            label = f"[green]✓[/green] {icon} {message}"
        elif status == "error":
            label = f"[red]✗[/red] {icon} {message}"
        elif status == "skip":
            label = f"[dim]⊘ {icon} {message} (skipped)[/dim]"
        else:
            label = f"{icon} {message}"

        self.tree.add(label)
        self._step_count += 1

        if self.live:
            self.live.refresh()

    def add_tool_call(self, tool_name: str, detail: str):
        """Show an actual tool being called."""
        self.add_step("🔧", f"{tool_name}: {detail}", "running")

    def add_tool_result(self, tool_name: str, summary: str, success: bool = True):
        """Show tool result."""
        st = "done" if success else "error"
        icon = "📋" if success else "💥"
        self.add_step(icon, f"{tool_name} → {summary}", st)

    def add_planning(self, strategy: str):
        """Show the selected strategy — one line, not fake alternatives."""
        self.add_step("📋", f"Strategy: {strategy}", "done")

    def add_progress(self, message: str):
        """Show a progress message."""
        self.add_step("⟡", message, "running")

    def finish(self):
        """End the thinking display cleanly."""
        if self.live:
            elapsed = time.time() - self.start_time
            if self.tree and self._step_count > 0:
                self.tree.add(f"[dim]⏱ {elapsed:.1f}s[/dim]")
                self.live.refresh()
                time.sleep(0.2)  # Brief pause so user sees final state
            self.live.stop()
            if self.tree and self._step_count > 0:
                self.console.print(self.tree)
        self.tree = None
        self.live = None

    @property
    def is_active(self) -> bool:
        """Whether the tree display is active."""
        return self.live is not None

    @property
    def should_show_spinner(self) -> bool:
        """Whether to use a simple spinner instead of the tree."""
        return self.complexity == QueryComplexity.SIMPLE

    @property
    def should_suppress(self) -> bool:
        """Whether to suppress all thinking display."""
        return self.complexity == QueryComplexity.TRIVIAL
