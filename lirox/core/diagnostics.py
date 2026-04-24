"""Lirox v1.1 — System Diagnostics

Comprehensive diagnostics for the /test command.
Reports on Python environment, providers, database, memory, and tools.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List


def run_diagnostics() -> None:
    """
    Run comprehensive system diagnostics and display results.
    Called by the /test command.
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()
    results = _collect_diagnostics()
    report = _format_report(results)
    console.print(report)


def _collect_diagnostics() -> Dict[str, Any]:
    """Collect diagnostic data from all subsystems."""
    results: Dict[str, Any] = {
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "lirox_path": str(Path(__file__).resolve().parent.parent),
        "workspace": os.getenv("LIROX_WORKSPACE", "not set"),
        "providers": [],
        "database": False,
        "memory": False,
        "tools": {},
    }

    # Check LLM providers
    try:
        from lirox.utils.llm import available_providers
        results["providers"] = available_providers()
    except Exception as e:
        results["providers_error"] = str(e)

    # Check database
    try:
        from lirox.database.store import DatabaseStore
        db = DatabaseStore()
        results["database"] = True
        results["db_stats"] = db.stats()
    except Exception:
        results["database"] = False

    # Check memory / learnings system
    try:
        from lirox.mind.learnings import LearningsStore
        learnings = LearningsStore()
        results["memory"] = True
        results["facts_count"] = len(learnings.data.get("user_facts", []))
        results["topics_count"] = len(learnings.data.get("topics", {}))
    except Exception:
        results["memory"] = False

    # Check core tools
    tools_to_check = [
        "lirox.tools.file_tools",
        "lirox.tools.shell_verified",
        "lirox.tools.file_generator",
    ]
    for tool_path in tools_to_check:
        short = tool_path.rsplit(".", 1)[-1]
        try:
            __import__(tool_path)
            results["tools"][short] = True
        except Exception:
            results["tools"][short] = False

    return results


def _format_report(results: Dict[str, Any]):
    """Format diagnostics into a Rich Panel."""
    from rich.table import Table
    from rich.panel import Panel

    table = Table(show_header=True, header_style="bold cyan", box=None)
    table.add_column("Check", style="bold white")
    table.add_column("Status", style="bold")
    table.add_column("Details", style="dim")

    # Python
    table.add_row("Python", f"[green]✓[/] {results['python_version']}", "")

    # Workspace
    table.add_row("Workspace", "[green]✓[/]", results["workspace"])

    # Providers
    provs = results.get("providers", [])
    if provs:
        table.add_row("LLM Providers", f"[green]✓[/] {len(provs)} found", ", ".join(provs))
    else:
        err = results.get("providers_error", "none configured")
        table.add_row("LLM Providers", "[red]✗[/]", err)

    # Database
    if results["database"]:
        table.add_row("Database", "[green]✓[/] SQLite OK", "")
    else:
        table.add_row("Database", "[red]✗[/] unavailable", "")

    # Memory
    if results["memory"]:
        fc = results.get("facts_count", 0)
        tc = results.get("topics_count", 0)
        table.add_row("Memory", "[green]✓[/]", f"{fc} facts, {tc} topics")
    else:
        table.add_row("Memory", "[red]✗[/]", "")

    # Tools
    for tool, ok in results.get("tools", {}).items():
        status = "[green]✓[/]" if ok else "[red]✗[/]"
        table.add_row(f"Tool: {tool}", status, "")

    return Panel(
        table,
        title="[bold cyan]SYSTEM DIAGNOSTICS[/]",
        border_style="cyan",
        padding=(1, 2),
    )
