"""Lirox UI — Permission Request Dialogs."""
from __future__ import annotations

from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.markup import escape

from lirox.autonomy.permission_system import (
    PermissionTier,
    PermissionRequest,
    TIER_ICONS,
    TIER_LABELS,
)

console = Console()

_CLR_WARN    = "bold #f59e0b"
_CLR_SUCCESS = "bold #10b981"
_CLR_ERROR   = "bold #ef4444"
_CLR_DIM     = "dim #94a3b8"


def render_permission_request(request: PermissionRequest) -> None:
    """Display a permission-request panel to the user."""
    icon  = TIER_ICONS[request.tier]
    label = TIER_LABELS[request.tier]
    body  = (
        f"[{_CLR_WARN}]{icon}  TIER {request.tier.value} — {label}[/]\n\n"
        f"  [bold]Reason :[/] {escape(request.reason)}\n"
        f"  [bold]Action :[/] {escape(request.action)}"
    )
    if request.alternatives:
        body += "\n\n  [dim]Alternatives if denied:[/]"
        for alt in request.alternatives:
            body += f"\n    • {escape(alt)}"
    console.print(Panel(
        body,
        title=f"[{_CLR_WARN}]🔐 Permission Request[/]",
        border_style="#f59e0b",
        padding=(0, 1),
    ))


def render_permission_grant(tier: PermissionTier) -> None:
    icon  = TIER_ICONS[tier]
    label = TIER_LABELS[tier]
    console.print(
        f"  [{_CLR_SUCCESS}]✓ Permission granted: {icon} TIER {tier.value} — {label}[/]"
    )


def render_permission_deny(tier: PermissionTier) -> None:
    icon  = TIER_ICONS[tier]
    label = TIER_LABELS[tier]
    console.print(
        f"  [{_CLR_ERROR}]✖ Permission denied for {icon} TIER {tier.value} — {label}[/]"
    )


def ask_permission(
    tier: PermissionTier,
    reason: str,
    action: str,
    alternatives: Optional[List[str]] = None,
) -> bool:
    """Interactively ask the user to grant a permission tier."""
    req = PermissionRequest(tier=tier, reason=reason, action=action,
                            alternatives=alternatives or [])
    render_permission_request(req)
    answer = console.input(f"  [{_CLR_WARN}]Allow? (y/n): [/]").strip().lower()
    granted = answer in ("y", "yes")
    if granted:
        render_permission_grant(tier)
    else:
        render_permission_deny(tier)
    return granted
