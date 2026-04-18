"""Lirox v2.0 — Terminal UI"""
import re
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markup import escape
from rich.markdown import Markdown
from lirox.config import APP_VERSION

console = Console()


def _strip_md(text: str) -> str:
    """Convert common markdown symbols to clean plain text for terminal streaming."""
    text = re.sub(r'```[\w]*\n?', '', text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*{3}(.+?)\*{3}', r'\1', text)
    text = re.sub(r'\*{2}(.+?)\*{2}', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    text = re.sub(r'^[\*\-]\s+', '• ', text, flags=re.MULTILINE)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'^[-\*]{3,}\s*$', '', text, flags=re.MULTILINE)
    return text


CLR_LIROX    = "bold #FFC107"
CLR_ACCENT   = "bold #FFD54F"
CLR_SUCCESS  = "bold #10b981"
CLR_ERROR    = "bold #ef4444"
CLR_WARN     = "bold #f59e0b"
CLR_DIM      = "dim #94a3b8"
CLR_THINK    = "bold #a78bfa"
CLR_PERSONAL = "bold #FFD700"
CLR_PERM     = "bold #f59e0b"

AGENT_COLORS = {"personal": CLR_PERSONAL, "mind": CLR_ACCENT, "skill": "bold #34d399"}
AGENT_ICONS  = {"personal": "⚡", "mind": "🧠", "skill": "🔧"}

# ── NEW 3D GRADIENT LOGO ─────────────────────────────────────────────────────
# Dark amber (#FF8C00) → warm gold (#FFC107) → light gold (#FFE66D)
# Shadow row beneath each block row creates 3D depth illusion.
LOGO = """
  [bold #FF8C00]╔═══════════════════════════════════════╗[/]
  [bold #FF8C00]║[/]  [bold #FF9500]██╗     ██╗██████╗  ██████╗ ██╗  ██╗[/]  [bold #FF8C00]║[/]
  [bold #FF9500]║[/]  [bold #FFA500]██║     ██║██╔══██╗██╔═══██╗╚██╗██╔╝[/]  [bold #FF9500]║[/]
  [bold #FFA500]║[/]  [bold #FFB300]██║     ██║██████╔╝██║   ██║ ╚███╔╝ [/]  [bold #FFA500]║[/]
  [bold #FFB300]║[/]  [bold #FFC107]██║     ██║██╔══██╗██║   ██║ ██╔██╗ [/]  [bold #FFB300]║[/]
  [bold #FFC107]║[/]  [bold #FFD54F]███████╗██║██║  ██║╚██████╔╝██╔╝ ██╗[/]  [bold #FFC107]║[/]
  [bold #FFD54F]║[/]  [bold #FFE066]╚══════╝╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝[/]  [bold #FFD54F]║[/]
  [bold #FFE066]╠═══════════════════════════════════════╣[/]
  [bold #FFE066]║[/]  [dim #FFD700]✦  Intelligence as an Operating System  ✦  v{v}[/]  [bold #FFE066]║[/]
  [bold #FFE066]╚═══════════════════════════════════════╝[/]
""".format(v=APP_VERSION)


def show_welcome():
    console.print(LOGO)
    console.print(f"  [{CLR_DIM}]Memory · Skills · Self-Learning · Always Growing[/]")
    console.print(f"  [{CLR_DIM}]Type /help for commands · /setup to configure[/]\n")
    from lirox.agent.profile import UserProfile
    p = UserProfile()
    if p.is_setup():
        user  = p.data.get("user_name", "")
        agent = p.data.get("agent_name", "Lirox")
        if user:
            console.print(f"  [bold #FFC107]Welcome back, {user}! 👋  {agent} is ready.[/]\n")
        else:
            console.print(f"  [bold #FFC107]{agent} is ready.[/]\n")


def show_thinking(msg: str):
    console.print(Panel(
        f"[{CLR_THINK}]{escape(msg)}[/]",
        title=f"[{CLR_THINK}]🧠 THINKING[/]",
        border_style="#a78bfa", padding=(0, 1)))


def show_agent_event(agent: str, etype: str, msg: str):
    """Show only genuine activity. Suppress boilerplate activation noise."""
    color = AGENT_COLORS.get(agent, CLR_ACCENT)

    if etype == "agent_start":
        return  # suppress spam

    elif etype == "tool_call":
        console.print(f"  [{CLR_DIM}]  ├─ 🔧 {escape(msg)}[/]")

    elif etype == "tool_result":
        if msg and msg.strip() and len(msg.strip()) > 3:
            console.print(f"  [{CLR_DIM}]  ├─ ✓ {escape(msg[:140])}[/]")

    elif etype == "agent_progress":
        trivial = {"thinking…", "analyzing…", "analyzing task…", "thinking..."}
        if msg and msg.lower().strip() not in trivial:
            console.print(f"  [{CLR_DIM}]  ├─ {escape(msg)}[/]")

    elif etype == "error":
        console.print(f"  [{CLR_ERROR}]  ├─ ✖ {escape(msg)}[/]")


def show_answer(answer: str, agent: str = "personal"):
    icon  = AGENT_ICONS.get(agent, "⚡")
    color = AGENT_COLORS.get(agent, CLR_ACCENT)
    console.print(f"\n{icon} [{color}]Response:[/]")
    try:
        console.print(Markdown(answer.strip()))
    except Exception:
        console.print(escape(answer.strip()))
    console.print()


def render_deep_thinking(message: str) -> None:
    """Render a deep-thinking event in a dim italic purple style."""
    if message:
        console.print(f"  [dim italic #a78bfa]🧠 {escape(message[:300])}[/]")


def render_permission_request(event_data: dict) -> None:
    try:
        from lirox.ui.permission_ui import render_permission_request as _render
        _render(event_data)
    except Exception:
        console.print(f"  [{CLR_WARN}]🔐 {escape(event_data.get('message', '')[:200])}[/]")


def render_permission_grant(event_data: dict) -> None:
    try:
        from lirox.ui.permission_ui import render_permission_grant as _render
        _render(event_data)
    except Exception:
        console.print(f"  [{CLR_SUCCESS}]✓ {escape(event_data.get('message', '')[:200])}[/]")


def render_permission_deny(event_data: dict) -> None:
    try:
        from lirox.ui.permission_ui import render_permission_deny as _render
        _render(event_data)
    except Exception:
        console.print(f"  [{CLR_ERROR}]✖ {escape(event_data.get('message', '')[:200])}[/]")


def render_progress_indicator(event_type: str, message: str) -> None:
    """Render code_analysis, code_generation, self_improvement, etc. events."""
    _ICONS = {
        "code_analysis":    "🔍",
        "code_generation":  "✍️ ",
        "code_validation":  "🔎",
        "code_testing":     "🧪",
        "self_improvement": "🔬",
        "step_execution":   "▶️ ",
        "fallback":         "⚡",
        "agent_progress":   "•",
    }
    icon = _ICONS.get(event_type, "•")
    if message and message.strip():
        console.print(f"  [{CLR_DIM}]  ├─ {icon} {escape(message[:180])}[/]")


def render_streaming_chunk(chunk: str) -> None:
    """Print a streaming chunk with live character-by-character animation."""
    if not chunk:
        return
    if chunk.strip().startswith("```"):
        try:
            console.print(Markdown(chunk))
        except Exception:
            console.print(escape(chunk), soft_wrap=True)
    else:
        import sys
        import time
        clean = _strip_md(chunk)
        for char in clean:
            sys.stdout.write(char)
            sys.stdout.flush()
            time.sleep(0.007)


def show_status_card(profile_data: dict, providers: list):
    t = Table(box=None, padding=(0, 2), show_header=False)
    t.add_column("Key",   style=CLR_DIM)
    t.add_column("Value", style="white")
    t.add_row("Operator",  profile_data.get("user_name", "Operator"))
    t.add_row("Agent",     profile_data.get("agent_name", "Atlas"))
    t.add_row("Version",   f"v{APP_VERSION}")
    t.add_row("Providers", ", ".join(providers) if providers else "None — run /setup")
    t.add_row("Mode",      "Personal AI OS")
    console.print(Panel(t, title=f"[{CLR_LIROX}]✦ LIROX v{APP_VERSION} — SYSTEM STATUS[/]",
                         border_style="#FFC107", padding=(0, 1)))
    console.print()


def error_panel(title: str, msg: str):
    hint = "\n  [dim]Try /help or /restart if this persists.[/]"
    console.print(Panel(
        f"[{CLR_ERROR}]{escape(msg)}[/]{hint}",
        title=f"[{CLR_ERROR}]{escape(title)}[/]",
        border_style="#ef4444"))


def info_panel(msg: str):
    console.print(Panel(f"[white]{escape(msg)}[/]", border_style="#94a3b8", padding=(0, 1)))


def success_message(msg: str):
    console.print(f"  [{CLR_SUCCESS}]✓ {escape(msg)}[/]")


def confirm_prompt(msg: str) -> bool:
    r = console.input(f"  [{CLR_WARN}]⚠ {msg} (y/n): [/]")
    return r.strip().lower() in ("y", "yes")


def show_context_status(buffer_msgs: int, facts_count: int, provider: str = "") -> None:
    """Show a compact status line — memory usage + provider."""
    est_tokens = buffer_msgs * 100 // 4
    ctx_limit  = 8192
    pct = min(100, (est_tokens * 100) // ctx_limit) if ctx_limit > 0 else 0

    filled = pct // 10
    bar = "█" * filled + "░" * (10 - filled)

    provider_str = f" · {provider}" if provider else ""
    console.print(
        f"  [dim]💾 {buffer_msgs} msgs · {facts_count} facts · "
        f"[{bar}] {pct}% ctx{provider_str}[/]",
        end="\n"
    )
