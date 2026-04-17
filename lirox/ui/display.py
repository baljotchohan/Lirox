"""Lirox v2.0.0 — Terminal UI

3D gradient 6-tone amber logo: dark shadow → bright highlight.
Rich panels, tables, streaming responses, status cards.

BUG-2 FIX: render_progress_indicator imported at module level (not inside a function).
"""
from __future__ import annotations

import re
import time
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.markup import escape
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from lirox.config import APP_VERSION

console = Console()

# BUG-2 FIX: render_progress_indicator imported at module level (was previously imported
# inside a function body, causing NameError on first call). Aliased here to match the
# name used throughout the codebase.
from rich.progress import Progress as render_progress_indicator  # noqa: F401

# ── Color Palette ─────────────────────────────────────────────────────────────

CLR_SHADOW   = "bold #7B4A00"   # darkest amber shadow
CLR_DARK     = "bold #A65C00"
CLR_MID      = "bold #CC7A00"
CLR_LIROX    = "bold #FFA500"   # primary amber
CLR_BRIGHT   = "bold #FFC107"
CLR_HIGHL    = "bold #FFD54F"   # brightest highlight
CLR_SUCCESS  = "bold #10b981"
CLR_ERROR    = "bold #ef4444"
CLR_WARN     = "bold #f59e0b"
CLR_DIM      = "dim #94a3b8"
CLR_THINK    = "bold #a78bfa"

# ── 3D Gradient 6-tone Amber Logo ─────────────────────────────────────────────

LOGO = (
    f"\n"
    f"  [{CLR_SHADOW}]██╗     ██╗██████╗  ██████╗ ██╗  ██╗[/]\n"
    f"  [{CLR_DARK}]██║     ██║██╔══██╗██╔═══██╗╚██╗██╔╝[/]\n"
    f"  [{CLR_MID}]██║     ██║██████╔╝██║   ██║ ╚███╔╝ [/]\n"
    f"  [{CLR_LIROX}]██║     ██║██╔══██╗██║   ██║ ██╔██╗ [/]\n"
    f"  [{CLR_BRIGHT}]███████╗██║██║  ██║╚██████╔╝██╔╝ ██╗[/]\n"
    f"  [{CLR_HIGHL}]╚══════╝╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝[/]\n"
    f"  [{CLR_DIM}]Intelligence as an Operating System — v{APP_VERSION}[/]\n"
)


# ── Public Functions ──────────────────────────────────────────────────────────

def show_welcome() -> None:
    """Display the welcome screen with logo."""
    console.print(LOGO)
    console.print(f"  [{CLR_DIM}]Files · Web · Memory · Self-Learning[/]")
    console.print(f"  [{CLR_DIM}]Type /help for commands · /setup to configure[/]\n")
    try:
        from lirox.agent.profile import UserProfile
        p = UserProfile()
        if p.is_setup():
            user  = p.data.get("user_name", "")
            agent = p.data.get("agent_name", "Lirox")
            if user:
                console.print(f"  [{CLR_BRIGHT}]Welcome back, {user}! 👋  {agent} is ready.[/]\n")
            else:
                console.print(f"  [{CLR_BRIGHT}]{agent} is ready.[/]\n")
    except Exception:
        pass


def show_thinking(msg: str) -> None:
    """Display a thinking/reasoning panel."""
    console.print(Panel(
        f"[{CLR_THINK}]{escape(msg[:800])}[/]",
        title=f"[{CLR_THINK}]🧠 THINKING[/]",
        border_style="#a78bfa", padding=(0, 1)))


def show_response(text: str, agent_name: str = "Lirox") -> None:
    """Display a response panel with markdown rendering."""
    try:
        console.print(Panel(
            Markdown(text),
            title=f"[{CLR_BRIGHT}]⚡ {agent_name}[/]",
            border_style="#FFA500",
            padding=(0, 1),
        ))
    except Exception:
        console.print(Panel(
            escape(text),
            title=f"[{CLR_BRIGHT}]⚡ {agent_name}[/]",
            border_style="#FFA500",
            padding=(0, 1),
        ))


def stream_response(text: str, agent_name: str = "Lirox") -> None:
    """Stream a response to the console with paragraph chunking."""
    from lirox.utils.streaming import StreamingResponse
    sr = StreamingResponse()
    console.print(f"\n[{CLR_BRIGHT}]⚡ {agent_name}:[/]")
    for chunk in sr.stream_in_paragraphs(text, delay=0.02):
        console.print(chunk, end="")
    console.print("\n")


def show_step(action: str, result: str) -> None:
    """Show a tool execution step."""
    console.print(f"  [{CLR_DIM}]  ├─ 🔧 {escape(action)}: {escape(result[:120])}[/]")


def show_error(msg: str) -> None:
    """Display an error message."""
    console.print(f"[{CLR_ERROR}]✖ {escape(msg)}[/]")


def show_success(msg: str) -> None:
    """Display a success message."""
    console.print(f"[{CLR_SUCCESS}]✓ {escape(msg)}[/]")


def show_status(profile=None, learnings=None, memory=None, bg_engine=None) -> None:
    """Display a status card with context metrics."""
    table = Table(box=None, padding=(0, 2), show_header=False)
    table.add_column("key",   style="dim")
    table.add_column("value", style="bold white")

    if profile:
        p = profile.data
        table.add_row("🤖 Agent",    p.get("agent_name", "Lirox"))
        table.add_row("👤 Operator", p.get("user_name", "-"))
        table.add_row("💼 Work",     p.get("niche", "-"))
        if p.get("current_project"):
            table.add_row("📦 Project", p["current_project"])

    if learnings:
        s = learnings.summary_dict()
        table.add_row("🧠 Facts",    str(s.get("facts", 0)))
        table.add_row("📚 Topics",   str(s.get("topics", 0)))
        table.add_row("📁 Projects", str(s.get("projects", 0)))
        last = s.get("last_trained", "never")
        if last and last != "never":
            last = last[:10]
        table.add_row("🔄 Last Trained", str(last))

    if memory:
        table.add_row("💬 Exchanges", str(memory.count_exchanges()))

    if bg_engine:
        table.add_row("⚙️  Auto-train", f"every {bg_engine.TRAIN_INTERVAL} messages")

    try:
        from lirox.utils.llm import available_providers
        providers = available_providers()
        table.add_row("🌐 Providers", ", ".join(providers) if providers else "None configured")
    except Exception:
        pass

    console.print(Panel(
        table,
        title=f"[{CLR_BRIGHT}]✦ STATUS[/]",
        border_style="#FFA500",
        padding=(0, 1),
    ))


def show_memory(learnings) -> None:
    """Display the memory/learnings panel."""
    facts   = learnings.get_facts()[-20:]
    topics  = learnings.get_topics()[-10:]
    projs   = learnings.get_projects()[-5:]
    style   = learnings.get_communication_style()

    lines = []
    if facts:
        lines.append(f"[{CLR_BRIGHT}]Facts ({len(facts)})[/]")
        for f in facts[-10:]:
            lines.append(f"  • {escape(f[:100])}")
    if topics:
        lines.append(f"\n[{CLR_BRIGHT}]Topics[/]: {escape(', '.join(topics))}")
    if projs:
        lines.append(f"[{CLR_BRIGHT}]Projects[/]: {escape(', '.join(projs))}")
    if style:
        style_str = ", ".join(f"{k}: {v}" for k, v in list(style.items())[:5])
        lines.append(f"[{CLR_BRIGHT}]Style[/]: {escape(style_str)}")

    content = "\n".join(lines) if lines else "[dim]No learnings yet. Chat more or run /train.[/]"
    console.print(Panel(
        content,
        title=f"[{CLR_BRIGHT}]🧠 MEMORY[/]",
        border_style="#a78bfa",
        padding=(0, 1),
    ))


def show_help() -> None:
    """Display command help table."""
    table = Table(box=None, padding=(0, 2), show_header=True)
    table.add_column("Command",     style=f"{CLR_BRIGHT}", no_wrap=True)
    table.add_column("Description", style="white")

    commands = [
        ("/help",                "Show this help"),
        ("/setup",               "Run setup wizard"),
        ("/think <query>",       "Deep think + execute a plan"),
        ("/status",              "Show context and system status"),
        ("/profile",             "Show your profile"),
        ("/memory",              "View learned knowledge"),
        ("/train",               "Extract and save learnings now"),
        ("/use-model <provider>","Pin an LLM provider"),
        ("/add-skill <desc>",    "Generate a new skill via LLM"),
        ("/skills",              "List all skills"),
        ("/use-skill <n>",       "Execute skill by number or name"),
        ("/add-agent <desc>",    "Generate a new sub-agent via LLM"),
        ("/agents",              "List all sub-agents"),
        ("@name <query>",        "Talk to a named sub-agent"),
        ("/backup",              "Backup memory and profile"),
        ("/export-memory",       "Export memory as JSON"),
        ("/import-memory",       "Import memory from JSON file"),
        ("/history",             "Show session history"),
        ("/reset",               "Reset current session"),
        ("/exit",                "Exit Lirox"),
    ]

    for cmd, desc in commands:
        table.add_row(cmd, desc)

    console.print(Panel(
        table,
        title=f"[{CLR_BRIGHT}]⚡ LIROX COMMANDS[/]",
        border_style="#FFA500",
        padding=(0, 1),
    ))


def spinner(msg: str):
    """Return a rich spinner context manager for showing progress."""
    return console.status(f"[{CLR_DIM}]{msg}[/]", spinner="dots")
