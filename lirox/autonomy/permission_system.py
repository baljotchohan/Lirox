"""Lirox Autonomy — Permission System (TIER 0-5).

Session-based permission grants: once the user approves a tier, it stays
granted for the lifetime of the current process.  Nothing is persisted to disk.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable, Dict, Generator, List, Optional, Set


class PermissionTier(IntEnum):
    """Capability tiers from most restricted to most powerful."""
    BASIC       = 0   # Read-only, no system access
    FILE_READ   = 1   # Read files in project
    FILE_WRITE  = 2   # Modify files (with preview)
    CODE_EXEC   = 3   # Execute Python scripts
    FULL_SYSTEM = 4   # Shell commands, git operations
    SELF_MODIFY = 5   # Modify own codebase


TIER_LABELS: Dict[PermissionTier, str] = {
    PermissionTier.BASIC:       "Basic Mode (read-only, no system access)",
    PermissionTier.FILE_READ:   "File Read (read files in project)",
    PermissionTier.FILE_WRITE:  "File Write (modify files with preview)",
    PermissionTier.CODE_EXEC:   "Code Execution (execute Python scripts)",
    PermissionTier.FULL_SYSTEM: "Full System (shell commands, git operations)",
    PermissionTier.SELF_MODIFY: "Self-Modification (modify own codebase)",
}

TIER_ICONS: Dict[PermissionTier, str] = {
    PermissionTier.BASIC:       "🔒",
    PermissionTier.FILE_READ:   "📖",
    PermissionTier.FILE_WRITE:  "✏️",
    PermissionTier.CODE_EXEC:   "⚙️",
    PermissionTier.FULL_SYSTEM: "🖥️",
    PermissionTier.SELF_MODIFY: "🔬",
}


@dataclass
class PermissionRequest:
    """Describes a single permission request from the agent."""
    tier:        PermissionTier
    reason:      str                    # Why the agent needs this
    action:      str                    # What it wants to do
    alternatives: List[str] = field(default_factory=list)  # Lower-tier workarounds


@dataclass
class PermissionEvent:
    """Yielded by the PermissionSystem to drive the UI interaction."""
    type:    str   # "permission_request" | "permission_grant" | "permission_deny"
    tier:    PermissionTier
    message: str
    data:    dict = field(default_factory=dict)


class PermissionSystem:
    """Manages capability tiers and handles interactive permission requests.

    Usage::

        ps = PermissionSystem()
        if not ps.has_permission(PermissionTier.FILE_WRITE):
            req = PermissionRequest(
                tier=PermissionTier.FILE_WRITE,
                reason="I need to save the generated code to disk.",
                action="Write file: output.py",
            )
            granted = ps.request_interactive(req, user_confirm_fn=ask_user)
    """

    def __init__(self) -> None:
        # Start at BASIC by default; accumulate grants during the session
        self._granted: Set[PermissionTier] = {PermissionTier.BASIC}

    # ── Query ──────────────────────────────────────────────────────────────

    def has_permission(self, tier: PermissionTier) -> bool:
        """Return True if *tier* (or higher) has already been granted."""
        return any(g >= tier for g in self._granted)

    def current_max_tier(self) -> PermissionTier:
        return max(self._granted) if self._granted else PermissionTier.BASIC

    def list_granted(self) -> List[PermissionTier]:
        return sorted(self._granted)

    # ── Grant / Revoke ─────────────────────────────────────────────────────

    def grant(self, tier: PermissionTier) -> None:
        """Permanently grant *tier* for this session."""
        # Also grant all tiers below it (cumulative)
        for t in PermissionTier:
            if t <= tier:
                self._granted.add(t)

    def revoke(self, tier: PermissionTier) -> None:
        """Revoke *tier* and all tiers above it."""
        self._granted = {t for t in self._granted if t < tier}

    # ── Interactive request ────────────────────────────────────────────────

    def request_events(
        self, req: PermissionRequest
    ) -> Generator[PermissionEvent, None, None]:
        """Yield events that describe a permission request (for the UI to render)."""
        yield PermissionEvent(
            type="permission_request",
            tier=req.tier,
            message=(
                f"{TIER_ICONS[req.tier]} Permission requested: "
                f"TIER {req.tier} ({TIER_LABELS[req.tier]})\n"
                f"  Reason : {req.reason}\n"
                f"  Action : {req.action}"
            ),
            data={"request": req, "alternatives": req.alternatives},
        )

    def process_grant(self, tier: PermissionTier) -> PermissionEvent:
        self.grant(tier)
        return PermissionEvent(
            type="permission_grant",
            tier=tier,
            message=f"✓ Permission granted: TIER {tier} ({TIER_LABELS[tier]})",
        )

    def process_deny(self, tier: PermissionTier) -> PermissionEvent:
        return PermissionEvent(
            type="permission_deny",
            tier=tier,
            message=f"✖ Permission denied for TIER {tier}.",
        )

    def request_interactive(
        self,
        req: PermissionRequest,
        user_confirm_fn: Callable[[str], bool],
    ) -> bool:
        """Blocking helper: show request, ask user, update grants.

        *user_confirm_fn* receives a prompt string and returns True/False.
        """
        icon  = TIER_ICONS[req.tier]
        label = TIER_LABELS[req.tier]
        prompt = (
            f"\n{icon}  Permission needed: TIER {req.tier.value} — {label}\n"
            f"  Reason : {req.reason}\n"
            f"  Action : {req.action}"
        )
        if req.alternatives:
            prompt += "\n  Alternatives:\n" + "\n".join(
                f"    • {a}" for a in req.alternatives
            )
        prompt += "\n  Allow?"
        granted = user_confirm_fn(prompt)
        if granted:
            self.grant(req.tier)
        return granted

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def describe_tier(tier: PermissionTier) -> str:
        return f"TIER {tier.value}: {TIER_ICONS[tier]} {TIER_LABELS[tier]}"

    def summary_table(self) -> str:
        lines = ["PERMISSION TIERS\n"]
        for t in PermissionTier:
            status = "✓ GRANTED" if self.has_permission(t) else "  locked"
            lines.append(f"  {TIER_ICONS[t]} TIER {t.value}  {TIER_LABELS[t]:<50}  [{status}]")
        return "\n".join(lines)
