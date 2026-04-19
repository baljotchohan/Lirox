"""Lirox v1.1 — Terminal UI"""
import re
from rich.console import Console
from rich.panel import Panel
from rich.markup import escape
from rich.table import Table
from lirox.config import APP_VERSION

console = Console()

CLR_LIROX   = "bold #FFC107"
CLR_SUCCESS = "bold #10b981"
CLR_ERROR   = "bold #ef4444"
CLR_DIM     = "dim #94a3b8"
CLR_THINK   = "bold #a78bfa"

_raw_logo = [
    "██╗     ██╗██████╗  ██████╗ ██╗  ██╗",
    "██║     ██║██╔══██╗██╔═══██╗╚██╗██╔╝",
    "██║     ██║██████╔╝██║   ██║ ╚███╔╝ ",
    "██║     ██║██╔══██╗██║   ██║ ██╔██╗ ",
    "███████╗██║██║  ██║╚██████╔╝██╔╝ ██╗",
    "╚══════╝╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝"
]
_tagline = f"✦  Intelligence as an Operating System  ✦  v{APP_VERSION}"
_box_inner = max(50, len(_tagline) + 4)
_pad_left = (_box_inner - len(_tagline)) // 2
_pad_right = _box_inner - len(_tagline) - _pad_left
_tagline_centered = (" " * _pad_left) + _tagline + (" " * _pad_right)

_logo_lines = []
colors = ["#FF9500", "#FFA500", "#FFB300", "#FFC107", "#FFD54F", "#FFE066"]
border_colors = ["#FF8C00", "#FF9500", "#FFA500", "#FFB300", "#FFC107", "#FFD54F"]
for i, line in enumerate(_raw_logo):
    lpad = (_box_inner - len(line)) // 2
    rpad = _box_inner - len(line) - lpad
    _logo_lines.append(f"  [bold {border_colors[i]}]║[/]" + (" " * lpad) + f"[bold {colors[i]}]{line}[/]" + (" " * rpad) + f"[bold {border_colors[i]}]║[/]")

LOGO = f"  [bold #FF8C00]╔{'═' * _box_inner}╗[/]\n" + "\n".join(_logo_lines) + f"\n  [bold #FFE066]╠{'═' * _box_inner}╣[/]\n  [bold #FFE066]║[/][dim #FFD700]{_tagline_centered}[/][bold #FFE066]║[/]\n  [bold #FFE066]╚{'═' * _box_inner}╝[/]"


def show_welcome():
    console.print(LOGO)
    console.print(f"  [{CLR_DIM}]Type /help for commands · /setup to configure[/]\n")
    from lirox.agent.profile import UserProfile
    p = UserProfile()
    if p.is_setup():
        user  = p.data.get("user_name", "")
        agent = p.data.get("agent_name", "Lirox")
        if user:
            console.print(f"  [bold #FFC107]Welcome back, {user}! 👋  {agent} is ready.[/]\n")


def show_status_card(profile_data: dict, providers: list):
    agent = profile_data.get("agent_name", "Lirox")
    user  = profile_data.get("user_name", "")
    prov  = ", ".join(providers[:3]) if providers else "None (run /setup)"
    console.print(f"  [{CLR_DIM}]Agent: {agent}  ·  User: {user or '?'}  ·  Providers: {prov}[/]")


def show_thinking(msg: str):
    console.print(Panel(f"[{CLR_THINK}]{escape(msg)}[/]",
                        title=f"[{CLR_THINK}]🧠 THINKING[/]",
                        border_style="#a78bfa", padding=(0, 1)))


def show_thinking_phase(event: dict):
    """Render a single thinking phase from a ``thinking_phase`` event dict.

    Produces output like::

      🔍 UNDERSTAND  [1/8]  ████████░░  88%
        ✓ Intent detected: file operation
        ✓ Query length: 7 words — complexity: medium
        ✓ Ambiguity check: None detected
    """
    idx        = event.get("phase_index", 0)
    name       = event.get("phase_name", "PHASE")
    icon       = event.get("phase_icon", "•")
    tagline    = event.get("phase_tagline", "")
    total      = event.get("phase_total", 8)
    steps      = event.get("steps", [])
    confidence = event.get("confidence", 80)
    complexity = event.get("complexity", "medium")

    # ── Progress bar ──────────────────────────────────────────────────────────
    filled   = round((idx + 1) / total * 10)
    bar      = "█" * filled + "░" * (10 - filled)
    phase_lbl = f"[{idx + 1}/{total}]"

    # ── Confidence colour ─────────────────────────────────────────────────────
    if confidence >= 90:
        conf_color = "#10b981"   # green
    elif confidence >= 75:
        conf_color = "#FFC107"   # amber
    else:
        conf_color = "#ef4444"   # red

    header = (
        f"[bold #a78bfa]{icon} {name}[/]  "
        f"[dim]{phase_lbl}[/]  "
        f"[{conf_color}]{bar}[/]  "
        f"[{conf_color}]{confidence}%[/]"
    )
    if tagline:
        header += f"  [dim #94a3b8]— {escape(tagline)}[/]"

    console.print(f"  {header}")
    for step in steps:
        console.print(f"    [{CLR_DIM}]✓ {escape(str(step)[:160])}[/]")


def show_thinking_panel_open(complexity: str):
    """Print the opening banner of the thinking panel."""
    complexity_colors = {
        "simple":   "#10b981",
        "medium":   "#FFC107",
        "complex":  "#a78bfa",
        "creative": "#f472b6",
    }
    color = complexity_colors.get(complexity, "#a78bfa")
    console.print()
    console.print(
        f"  [bold {color}]🧠 DEEP THINKING[/]  "
        f"[dim]({complexity.upper()} — full cognitive pipeline)[/]"
    )
    console.print(f"  [{CLR_DIM}]{'─' * 55}[/]")


def show_thinking_panel_close(total_ms: int, complexity: str):
    """Print the closing summary line of the thinking panel."""
    secs = total_ms / 1000
    console.print(f"  [{CLR_DIM}]{'─' * 55}[/]")
    console.print(
        f"  [{CLR_DIM}]⏱  Reasoning complete in {secs:.2f}s · "
        f"Complexity: {complexity.upper()}[/]"
    )
    console.print()


def show_agent_event(agent: str, etype: str, msg: str):
    if etype == "agent_start": return
    elif etype == "tool_call":
        console.print(f"  [{CLR_DIM}]  ├─ 🔧 {escape(msg)}[/]")
    elif etype == "tool_result":
        if msg and msg.strip() and len(msg.strip()) > 3:
            console.print(f"  [{CLR_DIM}]  ├─ ✓ {escape(msg[:200])}[/]")
    elif etype == "agent_progress":
        if msg and msg.lower().strip() not in {"thinking…", "analyzing…"}:
            console.print(f"  [{CLR_DIM}]  ├─ {escape(msg)}[/]")
    elif etype == "error":
        console.print(f"  [{CLR_ERROR}]  ├─ ✖ {escape(msg)}[/]")


def show_answer(text: str, agent: str = "personal"):
    icon = "⚡" if agent == "personal" else "🧠"
    console.print(f"\n{icon} [bold #FFD700]Response:[/]")
    from rich.markdown import Markdown
    from rich.live import Live
    from lirox.utils.streaming import StreamingResponse
    
    streamer = StreamingResponse()
    full_text = ""
    with Live(Markdown(""), console=console, refresh_per_second=15) as live:
        for chunk in streamer.stream_words(text, delay=0.01):
            full_text += chunk
            live.update(Markdown(full_text))
            
    console.print(f"  [{CLR_SUCCESS}]✓ Done[/]")


def render_streaming_chunk(chunk: str):
    console.print(chunk, end="", highlight=False)


def error_panel(title: str, msg: str):
    console.print(Panel(f"[{CLR_ERROR}]{escape(msg)}[/]",
                        title=f"[{CLR_ERROR}]{title}[/]", border_style="red"))


def info_panel(msg: str):
    console.print(Panel(f"[white]{escape(msg)}[/]", border_style="#FFC107", padding=(0, 2)))


def success_message(msg: str):
    console.print(Panel(f"[{CLR_SUCCESS}]{escape(msg)}[/]", border_style="green", padding=(0, 2)))


def confirm_prompt(msg: str) -> bool:
    answer = console.input(f"  [bold #FFC107]{msg} (y/n): [/]").strip().lower()
    return answer in ("y", "yes")
