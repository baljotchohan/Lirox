"""Lirox UI — Permission Request Panels.

Rich-formatted permission request dialogs that block for user confirmation.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from lirox.autonomy.permission_system import PermissionSystem, PermissionTier

_console = Console()

_TIER_COLORS = {
    PermissionTier.BASIC:       "dim white",
    PermissionTier.FILE_READ:   "cyan",
    PermissionTier.FILE_WRITE:  "yellow",
    PermissionTier.CODE_EXEC:   "bold yellow",
    PermissionTier.FULL_SYSTEM: "bold orange1",
    PermissionTier.SELF_MODIFY: "bold red",
}

_TIER_ICONS = {
    PermissionTier.BASIC:       "⬜",
    PermissionTier.FILE_READ:   "📖",
    PermissionTier.FILE_WRITE:  "✏️ ",
    PermissionTier.CODE_EXEC:   "⚙️ ",
    PermissionTier.FULL_SYSTEM: "🖥️ ",
    PermissionTier.SELF_MODIFY: "🔬",
}


def render_permission_request(event: Dict[str, Any]) -> None:
    """Render a `permission_request` event as a Rich panel."""
    data    = event.get("data", {})
    tier    = PermissionTier(data.get("tier", 0))
    label   = data.get("label", str(tier))
    reason  = data.get("reason", "")
    action  = data.get("action", "")
    alts    = data.get("alternatives", [])
    color   = _TIER_COLORS.get(tier, "white")
    icon    = _TIER_ICONS.get(tier, "🔐")

    lines = [f"[bold]{icon} {label}[/]"]
    if reason:
        lines.append(f"\n  [dim]Reason :[/] {reason}")
    if action:
        lines.append(f"  [dim]Action :[/] {action}")
    if alts:
        lines.append("\n  [dim]Alternatives:[/]")
        for a in alts:
            lines.append(f"    • {a}")

    _console.print(Panel(
        "\n".join(lines),
        title=f"[bold {color}]🔐 Permission Request[/]",
        border_style=color,
        padding=(1, 2),
    ))


def render_permission_grant(event: Dict[str, Any]) -> None:
    """Render a `permission_grant` event."""
    label = event.get("data", {}).get("label", "Unknown tier")
    _console.print(f"  [bold #10b981]✓ Permission granted:[/] {label}")


def render_permission_deny(event: Dict[str, Any]) -> None:
    """Render a `permission_deny` event."""
    label = event.get("data", {}).get("label", "Unknown tier")
    alts  = event.get("data", {}).get("alternatives", [])
    _console.print(f"  [bold red]✖ Permission denied:[/] {label}")
    for a in alts:
        _console.print(f"    [dim]• {a}[/]")


def ask_permission(
    permission_system: PermissionSystem,
    tier: PermissionTier,
    reason: str = "",
) -> bool:
    """Blocking prompt: ask the user to grant *tier*.  Returns True if granted."""
    from lirox.autonomy.permission_system import _TIER_LABELS

    label = _TIER_LABELS.get(tier, str(tier))
    _console.print(f"\n  [bold yellow]🔐 Permission Request:[/] {label}")
    if reason:
        _console.print(f"  [dim]Reason: {reason}[/]")

    answer = Prompt.ask(
        "  [bold]Allow?[/]",
        choices=["y", "n"],
        default="n",
        console=_console,
    )
    if answer.lower() == "y":
        permission_system.grant(tier)
        _console.print(f"  [bold #10b981]✓ Granted: {label}[/]")
        return True
    else:
        _console.print(f"  [bold red]✖ Denied: {label}[/]")
        return False


def show_permissions_table(permission_system: PermissionSystem) -> None:
    """Display a Rich table of all permission tiers and their grant status."""
    from rich.table import Table

    table = Table(
        show_header=True,
        header_style="bold #FFC107",
        border_style="dim",
    )
    table.add_column("Tier", style="bold white", width=6)
    table.add_column("Label",       style="white")
    table.add_column("Status",      style="white", width=10)
    table.add_column("Description", style="dim white")

    for row in permission_system.status_table():
        status = "[bold #10b981]✓ Granted[/]" if row["granted"] else "[dim]—[/]"
        table.add_row(
            str(row["tier"]),
            row["label"],
            status,
            row["description"],
        )

    _console.print(Panel(table, title="[bold #FFC107]PERMISSION TIERS[/]",
                          border_style="#FFC107"))
