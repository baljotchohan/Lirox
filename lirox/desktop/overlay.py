"""
Lirox v1.0.0 — Desktop Overlay
Real-time visual feedback while the agent controls the desktop.
"""
from __future__ import annotations

from typing import Optional


class DesktopOverlay:
    """
    Displays a non-blocking status overlay on screen during desktop control.

    Falls back silently when the underlying display libraries are not
    available (headless environments, CI, etc.).
    """

    def __init__(self) -> None:
        self._active: bool = False

    # ── Public API ────────────────────────────────────────────────────────────

    def show_status(self, message: str) -> None:
        """Display a status banner at the top of the screen."""
        self._active = True
        self._print_overlay(f"🤖 LIROX AGENT  |  {message}")

    def show_step(self, step: int, action: str, target: str) -> None:
        """Update the overlay with the current action step."""
        label = f"Step {step}: {action}"
        if target:
            label += f" → {target[:60]}"
        self._print_overlay(f"🤖 LIROX  |  {label}")

    def clear(self) -> None:
        """Remove the overlay."""
        self._active = False

    # ── Internals ─────────────────────────────────────────────────────────────

    @staticmethod
    def _print_overlay(message: str) -> None:
        """Terminal fallback: print to stderr so it doesn't pollute stdout."""
        import sys
        print(f"\r  \033[36m[DESKTOP]\033[0m  {message}", end="", file=sys.stderr)
