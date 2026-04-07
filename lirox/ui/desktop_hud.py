"""
Lirox v3.0 — Desktop HUD
Live bottom-center status bar shown while agent controls the desktop.
Uses Rich Live layout for real-time updates.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

_console = Console()


class DesktopHUD:
    """
    A live status bar that renders at the bottom of the terminal
    while the agent is controlling the desktop.
    
    Usage:
        hud = DesktopHUD()
        hud.start("Open Chrome and search for AI news")
        hud.update_step(1, "Taking screenshot...")
        hud.update_step(2, "Clicking Chrome icon")
        hud.stop(success=True)
    """

    def __init__(self):
        self._task: str = ""
        self._step: int = 0
        self._last_action: str = ""
        self._paused: bool = False
        self._live: Optional[Live] = None
        self._thread: Optional[threading.Thread] = None
        self._running: bool = False
        self._start_time: float = 0.0
        self._lock = threading.Lock()

    def _make_panel(self) -> Panel:
        """Build the HUD panel."""
        with self._lock:
            elapsed = int(time.time() - self._start_time) if self._start_time else 0
            mm, ss = divmod(elapsed, 60)

            # Top row: task name
            task_text = Text()
            task_text.append("⚡ LIROX ", style="bold #FFD700")
            task_text.append("AGENT ACTIVE", style="bold white")
            task_text.append("  │  ", style="dim")
            task_text.append(
                self._task[:70] + ("…" if len(self._task) > 70 else ""),
                style="bold #FFC107"
            )

            # Bottom row: step + action + timer + pause hint
            status_text = Text()

            if self._paused:
                status_text.append("⏸  PAUSED", style="bold yellow")
                status_text.append("  │  type /resume to continue", style="dim")
            else:
                status_text.append(f"Step {self._step}", style="bold cyan")
                status_text.append("  │  ", style="dim")
                action_display = self._last_action[:80] + ("…" if len(self._last_action) > 80 else "")
                status_text.append(action_display, style="white")
                status_text.append("  │  ", style="dim")
                status_text.append(f"{mm:02d}:{ss:02d}", style="dim #94a3b8")
                status_text.append("   /pause to stop", style="dim #666")

            table = Table.grid(padding=(0, 0))
            table.add_row(task_text)
            table.add_row(status_text)

            border = "yellow" if not self._paused else "dim yellow"
            return Panel(
                table,
                border_style=border,
                padding=(0, 2),
            )

    def _run_live(self):
        """Background thread: keeps the Live display refreshed."""
        with Live(
            self._make_panel(),
            console=_console,
            refresh_per_second=4,
            transient=True,   # removes HUD when stopped
        ) as live:
            self._live = live
            while self._running:
                live.update(self._make_panel())
                time.sleep(0.25)
            self._live = None

    def start(self, task: str):
        """Start the HUD for a new task."""
        with self._lock:
            self._task = task
            self._step = 0
            self._last_action = "Initializing…"
            self._paused = False
            self._running = True
            self._start_time = time.time()

        self._thread = threading.Thread(target=self._run_live, daemon=True)
        self._thread.start()
        # Small sleep so Live gets to render before agent starts printing
        time.sleep(0.15)

    def update_step(self, step: int, action: str):
        """Update the current step and action label."""
        with self._lock:
            self._step = step
            self._last_action = action

    def set_paused(self, paused: bool):
        with self._lock:
            self._paused = paused

    def stop(self, success: bool = True):
        """Tear down the HUD."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)

        icon = "✅" if success else "❌"
        elapsed = int(time.time() - self._start_time) if self._start_time else 0
        mm, ss = divmod(elapsed, 60)
        _console.print(
            f"\n  [{('bold #10b981' if success else 'bold #ef4444')}]{icon} "
            f"Task {'completed' if success else 'stopped'} "
            f"— {self._step} steps in {mm:02d}:{ss:02d}[/]\n"
        )
        self._start_time = 0.0


# Global singleton
_hud = DesktopHUD()


def get_hud() -> DesktopHUD:
    return _hud
