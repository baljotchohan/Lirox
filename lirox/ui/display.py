"""Lirox v2.0 — Agent-aware Terminal UI with Rich."""
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from lirox.config import APP_VERSION

console = Console()

# Color palette
CLR_LIROX = "bold #FFC107"
CLR_ACCENT = "bold #FFD54F"
CLR_SUCCESS = "bold #10b981"
CLR_ERROR = "bold #ef4444"
CLR_WARN = "bold #f59e0b"
CLR_DIM = "dim #94a3b8"
CLR_THINK = "bold #a78bfa"
CLR_FINANCE = "bold #22d3ee"
CLR_CODE = "bold #34d399"
CLR_BROWSER = "bold #f97316"
CLR_RESEARCH = "bold #818cf8"

AGENT_COLORS = {
    "finance": CLR_FINANCE,
    "code": CLR_CODE,
    "browser": CLR_BROWSER,
    "research": CLR_RESEARCH,
    "chat": CLR_ACCENT,
}
AGENT_ICONS = {
    "finance": "📊",
    "code": "💻",
    "browser": "🌐",
    "research": "🔬",
    "chat": "💬",
    "thinking": "🧠",
}

LOGO = f"""
  [bold #FFB300]██╗     ██╗██████╗  ██████╗ ██╗  ██╗[/] [bold red]BETA 1[/]
  [bold #FFC107]██║     ██║██╔══██╗██╔═══██╗╚██╗██╔╝[/]
  [bold #FFD54F]██║     ██║██████╔╝██║   ██║ ╚███╔╝ [/]
  [bold #FFC107]██║     ██║██╔══██╗██║   ██║ ██╔██╗ [/]
  [bold #FFB300]███████╗██║██║  ██║╚██████╔╝██╔╝ ██╗[/]
  [bold #FFA000]╚══════╝╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝[/]
  [{CLR_LIROX}]v{APP_VERSION} ✦ MULTI-AGENT KERNEL[/]
"""


def show_welcome():
    console.print(LOGO)
    console.print(
        f"  [{CLR_DIM}]Agents: Finance · Code · Browser · Research · Chat[/]"
    )
    console.print(f"  [{CLR_DIM}]Type /help for commands · /agents for status[/]\n")
    from lirox.agent.profile import UserProfile
    p = UserProfile()
    if p.is_setup():
        user = p.data.get("user_name", "")
        agent = p.data.get("agent_name", "Lirox")
        console.print(f"  [bold #FFC107]Welcome back, {user}! 👋 {agent} is ready.[/]\n")


def show_thinking(msg: str):
    console.print(
        Panel(
            f"[{CLR_THINK}]{msg}[/]",
            title=f"[{CLR_THINK}]🧠 THINKING[/]",
            border_style="#a78bfa",
            padding=(0, 1),
        )
    )


def show_agent_event(agent: str, etype: str, msg: str):
    color = AGENT_COLORS.get(agent, CLR_ACCENT)
    icon = AGENT_ICONS.get(agent, "⚡")
    if etype == "agent_start":
        console.print(
            f"  [{color}]{icon} {agent.upper()} AGENT[/] [{CLR_DIM}]activated[/]"
        )
    elif etype == "tool_call":
        console.print(f"  [{CLR_DIM}]  ├─ 🔧 {msg}[/]")
    elif etype == "tool_result":
        console.print(f"  [{CLR_DIM}]  ├─ ✓ {msg[:100]}[/]")
    elif etype == "agent_progress":
        console.print(f"  [{CLR_DIM}]  ├─ {msg}[/]")
    elif etype == "error":
        console.print(f"  [{CLR_ERROR}]  ├─ ✖ {msg}[/]")


def show_answer(answer: str, agent: str = "chat"):
    icon = AGENT_ICONS.get(agent, "💬")
    color = AGENT_COLORS.get(agent, CLR_ACCENT)
    console.print(f"\n{icon} [{color}]{answer.strip()}[/]\n")


def show_status_card(profile_data: dict, providers: list):
    t = Table(box=None, padding=(0, 2), show_header=False)
    t.add_column("Key", style=CLR_DIM)
    t.add_column("Value", style="white")
    t.add_row("Operator", profile_data.get("user_name", "Operator"))
    t.add_row("Agent", profile_data.get("agent_name", "Lirox"))
    t.add_row("Version", f"v{APP_VERSION}")
    t.add_row("Providers", ", ".join(providers) if providers else "None configured")
    t.add_row("Agents", "Finance · Code · Browser · Research · Chat")
    console.print(
        Panel(
            t,
            title=f"[{CLR_LIROX}]✦ SYSTEM STATUS[/]",
            border_style="#FFC107",
            padding=(0, 1),
        )
    )
    console.print()


def error_panel(title: str, msg: str):
    console.print(
        Panel(
            f"[{CLR_ERROR}]{msg}[/]",
            title=f"[{CLR_ERROR}]{title}[/]",
            border_style="#ef4444",
        )
    )


def info_panel(msg: str):
    console.print(
        Panel(f"[{CLR_DIM}]{msg}[/]", border_style="#94a3b8", padding=(0, 1))
    )


def success_message(msg: str):
    console.print(f"  [{CLR_SUCCESS}]✓ {msg}[/]")


def confirm_prompt(msg: str) -> bool:
    r = console.input(f"  [{CLR_WARN}]⚠ {msg} (y/n): [/]")
    return r.strip().lower() in ("y", "yes")
