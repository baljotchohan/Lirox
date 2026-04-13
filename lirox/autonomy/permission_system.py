"""Lirox Autonomy — Tiered Permission System.

Implements a session-scoped, cumulative permission model with TIER 0–5:

  TIER 0  BASIC       — Read-only reasoning; no filesystem access
  TIER 1  FILE_READ   — Read project files
  TIER 2  FILE_WRITE  — Create / modify files (with preview)
  TIER 3  CODE_EXEC   — Execute Python scripts in a sandbox
  TIER 4  FULL_SYSTEM — Shell commands, git operations
  TIER 5  SELF_MODIFY — Modify the Lirox codebase itself

Permissions are granted cumulatively: granting TIER 3 implies TIER 0–2.
No external APIs or network calls are used.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, Generator, List, Optional


class PermissionTier(IntEnum):
    BASIC       = 0
    FILE_READ   = 1
    FILE_WRITE  = 2
    CODE_EXEC   = 3
    FULL_SYSTEM = 4
    SELF_MODIFY = 5


_TIER_LABELS: Dict[PermissionTier, str] = {
    PermissionTier.BASIC:       "TIER 0 — Basic (read-only reasoning)",
    PermissionTier.FILE_READ:   "TIER 1 — File Read",
    PermissionTier.FILE_WRITE:  "TIER 2 — File Write",
    PermissionTier.CODE_EXEC:   "TIER 3 — Code Execution",
    PermissionTier.FULL_SYSTEM: "TIER 4 — Full System (shell / git)",
    PermissionTier.SELF_MODIFY: "TIER 5 — Self-Modification",
}

_TIER_DESCRIPTIONS: Dict[PermissionTier, str] = {
    PermissionTier.BASIC:       "Pure reasoning with no filesystem or system access.",
    PermissionTier.FILE_READ:   "Read project files to analyse and understand them.",
    PermissionTier.FILE_WRITE:  "Create or modify files (diffs shown before writing).",
    PermissionTier.CODE_EXEC:   "Execute Python scripts in an isolated subprocess.",
    PermissionTier.FULL_SYSTEM: "Run shell commands and git operations.",
    PermissionTier.SELF_MODIFY: "Scan the Lirox codebase, generate and apply patches.",
}


@dataclass
class PermissionRequest:
    """Describes a permission request the agent wants to make."""
    tier:         PermissionTier
    reason:       str
    action:       str
    alternatives: List[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return _TIER_LABELS.get(self.tier, str(self.tier))

    @property
    def description(self) -> str:
        return _TIER_DESCRIPTIONS.get(self.tier, "")


@dataclass
class PermissionEvent:
    """An event emitted during permission flow."""
    type:    str            # "permission_request" | "permission_grant" | "permission_deny"
    message: str
    data:    Dict[str, Any] = field(default_factory=dict)


@dataclass
class PermissionGrant:
    """Records a successful permission grant."""
    tier:    PermissionTier
    session: str = ""       # optional session tag


class PermissionSystem:
    """Session-scoped, cumulative permission manager.

    Permissions are additive: granting TIER N implies all tiers below N are
    also available (``has_permission(tier)`` checks ≤ current max).

    All logic is pure Python — no external APIs, no network calls.
    """

    def __init__(self) -> None:
        # Highest tier currently granted (None = nothing granted yet)
        self._max_tier: Optional[PermissionTier] = None
        self._grants:   List[PermissionGrant]    = []

    # ── Queries ────────────────────────────────────────────────────────────

    def current_tier(self) -> Optional[PermissionTier]:
        """Return the highest tier currently granted, or None."""
        return self._max_tier

    def has_permission(self, tier: PermissionTier) -> bool:
        """Return True if *tier* (or higher) has been granted this session."""
        if self._max_tier is None:
            return tier == PermissionTier.BASIC
        return int(self._max_tier) >= int(tier)

    def status_table(self) -> List[Dict[str, Any]]:
        """Return a list of dicts describing each tier and its grant status."""
        rows = []
        for t in PermissionTier:
            rows.append({
                "tier":        int(t),
                "label":       _TIER_LABELS[t],
                "description": _TIER_DESCRIPTIONS[t],
                "granted":     self.has_permission(t),
            })
        return rows

    # ── Mutations ──────────────────────────────────────────────────────────

    def grant(self, tier: PermissionTier) -> PermissionGrant:
        """Grant *tier* (and implicitly all lower tiers).  Returns the grant."""
        if self._max_tier is None or int(tier) > int(self._max_tier):
            self._max_tier = tier
        g = PermissionGrant(tier=tier)
        self._grants.append(g)
        return g

    def revoke_all(self) -> None:
        """Reset the permission system to the initial state (BASIC only)."""
        self._max_tier = None
        self._grants   = []

    # ── Event stream helpers ───────────────────────────────────────────────

    def request_events(
        self, req: PermissionRequest
    ) -> Generator[PermissionEvent, None, None]:
        """Yield structured events for a permission request (no I/O performed).

        The caller is responsible for displaying the events and obtaining user
        confirmation; then calling :meth:`grant` or handling the denial.
        """
        yield PermissionEvent(
            type="permission_request",
            message=(
                f"🔐 Permission Request: {req.label}\n"
                f"  Reason : {req.reason}\n"
                f"  Action : {req.action}"
            ),
            data={
                "tier":         int(req.tier),
                "label":        req.label,
                "reason":       req.reason,
                "action":       req.action,
                "alternatives": req.alternatives,
            },
        )

    def grant_event(self, tier: PermissionTier) -> PermissionEvent:
        """Return a *permission_grant* event after calling :meth:`grant`."""
        self.grant(tier)
        return PermissionEvent(
            type="permission_grant",
            message=f"✓ Permission granted: {_TIER_LABELS[tier]}",
            data={"tier": int(tier), "label": _TIER_LABELS[tier]},
        )

    def deny_event(
        self, tier: PermissionTier, alternatives: List[str] = None
    ) -> PermissionEvent:
        """Return a *permission_deny* event (permission NOT granted)."""
        alt_text = ""
        if alternatives:
            alt_text = "\n  Alternatives:\n" + "\n".join(
                f"    • {a}" for a in alternatives
            )
        return PermissionEvent(
            type="permission_deny",
            message=f"✖ Permission denied: {_TIER_LABELS[tier]}{alt_text}",
            data={
                "tier":         int(tier),
                "label":        _TIER_LABELS[tier],
                "alternatives": alternatives or [],
            },
        )
