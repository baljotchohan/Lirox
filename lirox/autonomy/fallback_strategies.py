"""Lirox Autonomy — Fallback Strategies.

When a permission is denied or an operation fails, this module generates
rule-based alternative approaches so the agent can continue helping without
stopping.

No external APIs or network calls.
"""
from __future__ import annotations

from typing import Any, Dict, Generator, List, Optional

from lirox.autonomy.permission_system import PermissionTier


# ── Rule-based fallback table ─────────────────────────────────────────────────
# Maps (blocked_tier, task_keyword) → list of fallback descriptions
_FALLBACK_RULES: List[Dict[str, Any]] = [
    {
        "blocked_tier": PermissionTier.FULL_SYSTEM,
        "keywords":     ["shell", "bash", "git", "command"],
        "alternatives": [
            "Use subprocess (TIER 3) to run the equivalent Python code",
            "Implement the operation as a Python script",
            "Describe the required commands and let the user run them manually",
        ],
    },
    {
        "blocked_tier": PermissionTier.CODE_EXEC,
        "keywords":     ["execute", "run", "test"],
        "alternatives": [
            "Show the code for manual review and execution",
            "Perform static analysis only (no execution)",
            "Provide step-by-step instructions for the user to run",
        ],
    },
    {
        "blocked_tier": PermissionTier.FILE_WRITE,
        "keywords":     ["write", "create", "save", "modify"],
        "alternatives": [
            "Display the proposed file contents for manual copy-paste",
            "Generate the content and instruct the user to save it",
        ],
    },
    {
        "blocked_tier": PermissionTier.FILE_READ,
        "keywords":     ["read", "analyze", "analyse", "scan"],
        "alternatives": [
            "Ask the user to paste the relevant code snippets",
            "Advise based on general best practices",
        ],
    },
    {
        "blocked_tier": PermissionTier.SELF_MODIFY,
        "keywords":     ["improve", "fix", "patch", "self"],
        "alternatives": [
            "Use `/improve` command for the standard audit workflow",
            "Request TIER 5 permission with `/ask-permission 5`",
            "Show analysis results and let the user apply fixes manually",
        ],
    },
]


class FallbackStrategies:
    """Generate and stream fallback alternatives when an action is blocked."""

    def find_alternatives(
        self,
        blocked_tier: PermissionTier,
        task_description: str,
    ) -> List[str]:
        """Return a list of alternative suggestions for a blocked operation."""
        q   = task_description.lower()
        out: List[str] = []

        for rule in _FALLBACK_RULES:
            if rule["blocked_tier"] != blocked_tier:
                continue
            if any(kw in q for kw in rule["keywords"]):
                out.extend(rule["alternatives"])

        # Generic fallback if nothing matched
        if not out:
            out = [
                "Ask the user to grant the required permission tier",
                "Describe the intended outcome and ask how to proceed",
            ]
        return out

    def stream_fallback(
        self,
        blocked_tier: PermissionTier,
        task_description: str,
        original_error: Optional[str] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """Yield agent-bus events describing the fallback options."""
        from lirox.autonomy.permission_system import _TIER_LABELS  # type: ignore[attr-defined]

        label = _TIER_LABELS.get(blocked_tier, str(blocked_tier))
        yield {
            "type":    "fallback",
            "message": (
                f"⚡ Permission blocked ({label}). "
                f"Applying fallback strategy for: {task_description[:80]}"
            ),
        }

        if original_error:
            yield {
                "type":    "fallback",
                "message": f"  Original error: {original_error[:150]}",
            }

        alternatives = self.find_alternatives(blocked_tier, task_description)
        yield {
            "type":    "fallback",
            "message": "  💡 Alternatives:\n" + "\n".join(
                f"    {i}. {alt}" for i, alt in enumerate(alternatives, 1)
            ),
        }

    def apply_best_fallback(
        self,
        blocked_tier: PermissionTier,
        task_description: str,
    ) -> Generator[Dict[str, Any], None, None]:
        """Yield events for the first (best) fallback strategy only."""
        alternatives = self.find_alternatives(blocked_tier, task_description)
        if not alternatives:
            yield {"type": "fallback", "message": "No automatic fallback available."}
            return

        best = alternatives[0]
        yield {
            "type":    "fallback",
            "message": f"🔄 Switching to fallback approach:\n  → {best}",
        }
