"""Graduated permission model for the agentic loop.

Modelled on Claude Code's defense-in-depth design (research-grounded): a
deny-first policy where **deny overrides ask overrides allow**, combined with
graduated permission *modes* that scale autonomy from read-only planning up to
full bypass. This lets Lirox run long autonomous sessions without a prompt on
every step, while still hard-blocking dangerous actions.

Modes (increasing autonomy):
    PLAN          — read-only; no writes, shell, or network. The agent may only
                    inspect and produce a plan.
    DEFAULT       — safe/read tools auto-run; writes, shell and network ask.
    ACCEPT_EDITS  — file writes/edits auto-run; shell and network still ask.
    AUTO          — everything auto-runs except the hard deny-list.
    BYPASS        — everything runs (still audited). Use with care.

The deny-list is always enforced, in every mode.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

from lirox.agentic.tools import (
    DANGER_NETWORK, DANGER_SAFE, DANGER_SHELL, DANGER_WRITE, ToolSpec,
)


class PermissionMode(str, Enum):
    PLAN = "plan"
    DEFAULT = "default"
    ACCEPT_EDITS = "acceptEdits"
    AUTO = "auto"
    BYPASS = "bypass"

    @classmethod
    def coerce(cls, value) -> "PermissionMode":
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value))
        except ValueError:
            # tolerate friendly aliases
            m = {
                "readonly": cls.PLAN, "read-only": cls.PLAN, "plan": cls.PLAN,
                "safe": cls.DEFAULT, "normal": cls.DEFAULT,
                "edits": cls.ACCEPT_EDITS, "accept": cls.ACCEPT_EDITS,
                "yolo": cls.BYPASS, "full": cls.BYPASS, "auto": cls.AUTO,
            }
            return m.get(str(value).lower(), cls.DEFAULT)


class Decision(str, Enum):
    ALLOW = "allow"   # run without asking
    ASK = "ask"       # confirm with the user first
    DENY = "deny"     # never run


# Hard deny-list — patterns that are refused in *every* mode. These mirror the
# spirit of Lirox's existing shell blocklist but are enforced pre-dispatch.
_DENY_SHELL_PATTERNS = [
    r"\brm\s+-rf\s+[/~]",           # rm -rf / or ~
    r"\brm\s+-rf\s+--no-preserve",
    r":\(\)\s*\{.*\|.*&\s*\}",       # fork bomb
    r"\bmkfs\.",                     # format filesystem
    r"\bdd\s+if=.*of=/dev/(sd|nvme|disk)",
    r">\s*/dev/(sd|nvme|disk)",
    r"\bchmod\s+-R\s+777\s+/",
    r"\b(shutdown|reboot|halt|poweroff)\b",
    r"\b:>\s*/etc/",
    r"curl[^|]*\|\s*(sudo\s+)?(sh|bash)\b",   # curl | sh
    r"wget[^|]*\|\s*(sudo\s+)?(sh|bash)\b",
]
_DENY_RE = [re.compile(p, re.IGNORECASE) for p in _DENY_SHELL_PATTERNS]


@dataclass
class PermissionManager:
    """Decides allow / ask / deny for each tool call."""

    mode: PermissionMode = PermissionMode.DEFAULT
    # Optional user callback for ASK decisions: (tool_name, args) -> bool.
    approver: Optional[Callable[[str, dict], bool]] = None
    # Tool names the user has granted "always allow" this session.
    session_allow: set = field(default_factory=set)
    # Per-danger auto-run policy per mode.
    _MODE_POLICY: Dict[PermissionMode, Dict[str, Decision]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.mode = PermissionMode.coerce(self.mode)
        A, K, D = Decision.ALLOW, Decision.ASK, Decision.DENY
        self._MODE_POLICY = {
            PermissionMode.PLAN: {
                DANGER_SAFE: A, DANGER_WRITE: D, DANGER_SHELL: D, DANGER_NETWORK: D,
            },
            PermissionMode.DEFAULT: {
                DANGER_SAFE: A, DANGER_WRITE: K, DANGER_SHELL: K, DANGER_NETWORK: K,
            },
            PermissionMode.ACCEPT_EDITS: {
                DANGER_SAFE: A, DANGER_WRITE: A, DANGER_SHELL: K, DANGER_NETWORK: K,
            },
            PermissionMode.AUTO: {
                DANGER_SAFE: A, DANGER_WRITE: A, DANGER_SHELL: A, DANGER_NETWORK: A,
            },
            PermissionMode.BYPASS: {
                DANGER_SAFE: A, DANGER_WRITE: A, DANGER_SHELL: A, DANGER_NETWORK: A,
            },
        }

    # ── hard deny-list (always on) ────────────────────────────────────────
    @staticmethod
    def hard_denied(tool: ToolSpec, args: dict) -> Optional[str]:
        """Return a reason string if this call is categorically forbidden."""
        if tool.danger in (DANGER_SHELL,):
            cmd = str(args.get("command", "")) + " " + str(args.get("code", ""))
            for rx in _DENY_RE:
                if rx.search(cmd):
                    return f"blocked by deny-list ({rx.pattern})"
        return None

    # ── main decision ─────────────────────────────────────────────────────
    def decide(self, tool: ToolSpec, args: dict) -> Decision:
        # 1. Deny always wins.
        if self.hard_denied(tool, args):
            return Decision.DENY
        # 2. Session-granted allow.
        if tool.name in self.session_allow:
            return Decision.ALLOW
        # 3. Mode policy by danger class.
        return self._MODE_POLICY[self.mode].get(tool.danger, Decision.ASK)

    def authorize(self, tool: ToolSpec, args: dict) -> tuple[bool, str]:
        """Resolve a decision to a concrete (allowed, reason). ASK is resolved
        via the approver callback; without one, ASK conservatively denies in
        non-interactive contexts."""
        deny_reason = self.hard_denied(tool, args)
        if deny_reason:
            return False, f"DENIED: {deny_reason}"

        decision = self.decide(tool, args)
        if decision is Decision.ALLOW:
            return True, "allowed"
        if decision is Decision.DENY:
            return False, f"DENIED: '{tool.name}' not permitted in {self.mode.value} mode"

        # ASK
        if self.approver is None:
            return False, f"NEEDS APPROVAL: '{tool.name}' requires confirmation (none available)"
        try:
            ok = bool(self.approver(tool.name, args))
        except Exception:  # noqa: BLE001
            ok = False
        return (ok, "approved by user" if ok else "declined by user")

    def set_mode(self, mode) -> None:
        self.mode = PermissionMode.coerce(mode)

    def allow_for_session(self, tool_name: str) -> None:
        self.session_allow.add(tool_name)
