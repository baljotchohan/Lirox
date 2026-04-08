"""
Lirox v2.0 — Bash Skill

Handles terminal/shell command execution requests.
"""

from __future__ import annotations

from typing import List

from lirox.skills import BaseSkill


class BashSkill(BaseSkill):
    """Skill for running bash/terminal commands."""

    @property
    def name(self) -> str:
        return "bash"

    @property
    def description(self) -> str:
        return "Run terminal/bash shell commands safely."

    @property
    def keywords(self) -> List[str]:
        return [
            "terminal", "bash", "shell", "command", "run", "execute",
            "install", "pip", "npm", "script", "cli",
        ]

    def run(self, query: str, context: dict = None) -> str:
        """Execute a shell command extracted from the query."""
        from lirox.tools.terminal import run_command, is_safe
        safe, reason = is_safe(query)
        if not safe:
            return f"[Blocked] {reason}"
        return run_command(query)
