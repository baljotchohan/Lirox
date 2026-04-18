"""Lirox Thinking — Problem Decomposer.

Breaks complex queries into ordered sub-tasks, each annotated with the
required PermissionTier.

No external services beyond the standard LLM utility.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from lirox.utils.llm import generate_response


_DECOMPOSE_SYSTEM = (
    "You decompose tasks into numbered steps. "
    "Return only a numbered list (1. ... 2. ... etc), one step per line. "
    "Be concise. Maximum 6 steps."
)


class ProblemDecomposer:
    """Decompose a complex query into ordered sub-tasks."""

    def decompose(self, query: str, max_steps: int = 6) -> List[str]:
        """Return a list of sub-task strings for *query*.

        Falls back to a simple split if the LLM call fails.
        """
        try:
            prompt = f"Break this task into numbered steps:\n{query}"
            raw    = generate_response(prompt, provider="auto",
                                       system_prompt=_DECOMPOSE_SYSTEM)
            steps  = self._parse_steps(raw)
            return steps[:max_steps] if steps else self._fallback(query)
        except Exception:
            return self._fallback(query)

    @staticmethod
    def _parse_steps(text: str) -> List[str]:
        """Extract numbered list items from LLM output."""
        lines  = text.strip().splitlines()
        steps: List[str] = []
        for line in lines:
            m = re.match(r"^\s*\d+[.)]\s+(.+)$", line.strip())
            if m:
                steps.append(m.group(1).strip())
        return steps

    @staticmethod
    def _fallback(query: str) -> List[str]:
        """Return a generic decomposition when LLM is unavailable."""
        return [
            "Analyse the requirements",
            "Design the solution",
            "Implement the core logic",
            "Test and validate",
            "Refine and document",
        ]

    def decompose_with_tiers(self, query: str) -> List[Dict[str, Any]]:
        """Return steps annotated with required PermissionTier.

        Each item: ``{"step": str, "tier": PermissionTier}``.
        """
        from lirox.autonomy.permission_system import PermissionTier

        steps = self.decompose(query)
        result: List[Dict[str, Any]] = []

        for step in steps:
            s = step.lower()
            if any(k in s for k in ("self-modif", "patch", "apply fix")):
                tier = PermissionTier.SELF_MODIFY
            elif any(k in s for k in ("shell", "git", "system command")):
                tier = PermissionTier.FULL_SYSTEM
            elif any(k in s for k in ("execute", "run", "test")):
                tier = PermissionTier.CODE_EXEC
            elif any(k in s for k in ("write", "create file", "save", "modify file")):
                tier = PermissionTier.FILE_WRITE
            elif any(k in s for k in ("read", "scan", "analyse", "analyze")):
                tier = PermissionTier.FILE_READ
            else:
                tier = PermissionTier.BASIC
            result.append({"step": step, "tier": tier})

        return result
