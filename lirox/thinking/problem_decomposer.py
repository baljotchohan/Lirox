"""Lirox Thinking — Problem Decomposer.

Breaks a complex user query into an ordered list of concrete sub-tasks
that can be executed one at a time (enabling step_execution events and
interactive approval flows).
"""
from __future__ import annotations

import re
from typing import List

from lirox.utils.llm import generate_response


class ProblemDecomposer:
    """Break a complex request into ordered, actionable sub-tasks."""

    def __init__(self, provider: str = "auto") -> None:
        self.provider = provider

    # ── Public API ─────────────────────────────────────────────────────────

    def decompose(self, query: str, context: str = "") -> List[str]:
        """Return an ordered list of sub-task strings.

        Returns an empty list when the query is already atomic.
        """
        raw = self._call_llm(query, context)
        return self._parse(raw)

    def decompose_with_permissions(
        self, query: str, context: str = ""
    ) -> List[dict]:
        """Return sub-tasks annotated with required permission tier.

        Each item is:  {"step": str, "tier": PermissionTier}
        """
        from lirox.autonomy.permission_system import PermissionTier

        steps = self.decompose(query, context)
        result = []
        for step in steps:
            tier = self._infer_tier(step)
            result.append({"step": step, "tier": tier})
        return result

    # ── LLM call ──────────────────────────────────────────────────────────

    def _call_llm(self, query: str, context: str) -> str:
        prompt = (
            "Break the following task into a numbered list of concrete, "
            "ordered sub-tasks. Each sub-task must be one clear action.\n"
            "If the task is already simple and atomic, reply with just: ATOMIC\n\n"
            f"Task: {query}\n"
        )
        if context:
            prompt += f"\nContext: {context[:1000]}\n"
        try:
            return generate_response(
                prompt,
                self.provider,
                system_prompt=(
                    "Task decomposition expert. "
                    "Output a short numbered list of sub-tasks or 'ATOMIC'."
                ),
            )
        except Exception:
            return ""

    # ── Parsing ────────────────────────────────────────────────────────────

    @staticmethod
    def _parse(raw: str) -> List[str]:
        if not raw or "ATOMIC" in raw.upper():
            return []
        steps = []
        for line in raw.splitlines():
            line = line.strip()
            m    = re.match(r"^[\d]+[.)]\s*(.+)", line)
            if m:
                steps.append(m.group(1).strip())
        return steps

    # ── Tier inference ─────────────────────────────────────────────────────

    @staticmethod
    def _infer_tier(step: str) -> "PermissionTier":
        from lirox.autonomy.permission_system import PermissionTier

        s = step.lower()
        if any(kw in s for kw in ("git", "shell", "terminal", "run command", "docker")):
            return PermissionTier.FULL_SYSTEM
        if any(kw in s for kw in ("modify own", "patch lirox", "self-modify", "edit lirox")):
            return PermissionTier.SELF_MODIFY
        if any(kw in s for kw in ("execute", "run python", "run script", "run tests")):
            return PermissionTier.CODE_EXEC
        if any(kw in s for kw in ("write file", "save file", "create file", "edit file")):
            return PermissionTier.FILE_WRITE
        if any(kw in s for kw in ("read file", "open file", "list files", "scan")):
            return PermissionTier.FILE_READ
        return PermissionTier.BASIC
