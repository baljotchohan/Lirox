"""Lirox — Token & Cost Tracker
Real-time usage tracking: tokens consumed, estimated cost per provider,
session totals, and budget warnings.

Usage:
    /usage              — Current session stats
    /usage today        — Today's aggregate
    /usage reset        — Clear session counter
    /budget <$amount>   — Set a spending limit (warns when near)
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from datetime import date, datetime
from typing import Dict

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule

# ─────────────────────────────────────────────────────────────
# Pricing per 1M tokens (USD) — input/output
# ─────────────────────────────────────────────────────────────
PRICING: Dict[str, Dict[str, float]] = {
    "groq":       {"input": 0.00,    "output": 0.00},    # free tier
    "gemini":     {"input": 0.075,   "output": 0.30},    # gemini-2.0-flash
    "openai":     {"input": 2.50,    "output": 10.00},   # gpt-4o
    "anthropic":  {"input": 3.00,    "output": 15.00},   # claude-3-5-sonnet
    "deepseek":   {"input": 0.14,    "output": 0.28},    # deepseek-chat
    "openrouter": {"input": 1.00,    "output": 5.00},    # avg estimate
    "ollama":     {"input": 0.00,    "output": 0.00},    # local
    "auto":       {"input": 0.50,    "output": 2.00},    # conservative estimate
}

_DATA_DIR = Path.home() / ".lirox" / "usage"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_SESSION_FILE = _DATA_DIR / "session.json"
_DAILY_FILE   = _DATA_DIR / f"daily_{date.today()}.json"

# In-memory session state
_session: Dict = {
    "start_time": time.time(),
    "queries": 0,
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "by_provider": {},
    "budget_usd": None,
}


def _cost(provider: str, input_tok: int, output_tok: int) -> float:
    pricing = PRICING.get(provider, PRICING["auto"])
    return (input_tok * pricing["input"] + output_tok * pricing["output"]) / 1_000_000


def record(provider: str, input_tokens: int, output_tokens: int) -> None:
    """Called after each LLM response to record usage."""
    _session["queries"] += 1
    _session["total_input_tokens"]  += input_tokens
    _session["total_output_tokens"] += output_tokens

    p = _session["by_provider"].setdefault(provider, {"input": 0, "output": 0, "cost": 0.0})
    p["input"]  += input_tokens
    p["output"] += output_tokens
    p["cost"]   += _cost(provider, input_tokens, output_tokens)

    # Persist to daily file
    try:
        daily = {}
        if _DAILY_FILE.exists():
            daily = json.loads(_DAILY_FILE.read_text())
        for k in ("total_input_tokens", "total_output_tokens", "queries"):
            daily[k] = daily.get(k, 0) + _session.get(k, 0) - daily.get("_last_" + k, 0)
        daily["_last_total_input_tokens"]  = _session["total_input_tokens"]
        daily["_last_total_output_tokens"] = _session["total_output_tokens"]
        daily["_last_queries"]             = _session["queries"]
        _DAILY_FILE.write_text(json.dumps(daily))
    except Exception:
        pass

    # Budget check
    budget = _session.get("budget_usd")
    if budget:
        total_cost = sum(p["cost"] for p in _session["by_provider"].values())
        if total_cost >= budget * 0.9:
            from lirox.ui.display import console as _console
            pct = int((total_cost / budget) * 100)
            _console.print(f"  [bold #FFC107]⚠ Budget:[/] ${total_cost:.4f} / ${budget:.2f} ({pct}% used)")


def set_budget(usd: float) -> None:
    _session["budget_usd"] = usd


def reset_session() -> None:
    _session.update({
        "start_time": time.time(),
        "queries": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "by_provider": {},
    })


def _fmt_tokens(n: int) -> str:
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000:     return f"{n/1_000:.1f}K"
    return str(n)


def show_session(console: Console) -> None:
    """Display a clean session usage summary."""
    elapsed = time.time() - _session["start_time"]
    elapsed_str = f"{int(elapsed // 60)}m {int(elapsed % 60)}s"

    total_in  = _session["total_input_tokens"]
    total_out = _session["total_output_tokens"]
    total_cost = sum(p["cost"] for p in _session["by_provider"].values())

    table = Table(show_header=True, header_style="bold #FFC107", border_style="dim", box=None)
    table.add_column("Provider",    style="bold white")
    table.add_column("Input",       style="dim", justify="right")
    table.add_column("Output",      style="dim", justify="right")
    table.add_column("Est. Cost",   style="bold #10b981", justify="right")

    if _session["by_provider"]:
        for provider, data in sorted(_session["by_provider"].items()):
            cost_str = f"${data['cost']:.4f}" if data['cost'] > 0 else "free"
            table.add_row(
                provider,
                _fmt_tokens(data["input"]),
                _fmt_tokens(data["output"]),
                cost_str,
            )
    else:
        table.add_row("[dim]No queries yet[/]", "—", "—", "—")

    cost_display = f"${total_cost:.4f}" if total_cost > 0 else "free"
    budget_line = ""
    if _session.get("budget_usd"):
        b = _session["budget_usd"]
        pct = min(int((total_cost / b) * 100), 100)
        budget_line = f"\n[dim]Budget:[/] ${total_cost:.4f} / ${b:.2f} ({pct}% used)"

    summary = (
        f"[bold]Session Duration:[/] {elapsed_str}  ·  "
        f"[bold]Queries:[/] {_session['queries']}\n"
        f"[bold]Total Tokens:[/] {_fmt_tokens(total_in + total_out)} "
        f"([dim]{_fmt_tokens(total_in)} in · {_fmt_tokens(total_out)} out[/])\n"
        f"[bold]Est. Total Cost:[/] [bold #10b981]{cost_display}[/]"
        f"{budget_line}"
    )

    console.print()
    console.print(Rule("[bold #FFC107]Usage This Session[/]", style="#FFC107 dim"))
    console.print()
    console.print(summary)
    if _session["by_provider"]:
        console.print()
        console.print(table)
    console.print()


def show_today(console: Console) -> None:
    """Show today's aggregate usage from the daily file."""
    if not _DAILY_FILE.exists():
        console.print("[dim]No usage data for today yet.[/]")
        return
    try:
        daily = json.loads(_DAILY_FILE.read_text())
        total_in  = daily.get("total_input_tokens", 0)
        total_out = daily.get("total_output_tokens", 0)
        queries   = daily.get("queries", 0)
        console.print(Panel(
            f"[bold]Today ({date.today()}):[/]\n"
            f"Queries: {queries}\n"
            f"Tokens:  {_fmt_tokens(total_in + total_out)} total",
            title="[bold #FFC107]Daily Usage[/]", border_style="#FFC107"
        ))
    except Exception as e:
        console.print(f"[dim]Could not read daily stats: {e}[/]")


def handle_usage_command(cmd: str, console: Console) -> None:
    parts = cmd.strip().split()
    sub = parts[1].lower() if len(parts) > 1 else ""
    if sub == "today":
        show_today(console)
    elif sub == "reset":
        reset_session()
        console.print("[bold #10b981]✓[/] Session usage reset.")
    else:
        show_session(console)


def handle_budget_command(cmd: str, console: Console) -> None:
    parts = cmd.strip().split()
    if len(parts) < 2:
        current = _session.get("budget_usd")
        if current:
            console.print(f"  [dim]Current budget: [bold]${current:.2f}[/][/]")
        else:
            console.print("  [dim]No budget set. Usage: [bold]/budget 5.00[/][/]")
        return
    try:
        amount = float(parts[1].lstrip("$"))
        set_budget(amount)
        console.print(f"  [bold #10b981]✓[/] Budget set to [bold]${amount:.2f}[/] — I'll warn you at 90%.")
    except ValueError:
        console.print(f"  [bold red]✗[/] Invalid amount. Usage: [bold]/budget 5.00[/]")
