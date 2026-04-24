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

# Complexity-to-color mapping used by thinking panel display
COMPLEXITY_COLORS = {
    "simple":   "#10b981",
    "medium":   "#FFC107",
    "complex":  "#a78bfa",
    "creative": "#f472b6",
}

_raw_logo = [
    "██╗      ██╗ ██████╗   ██████╗ ██╗  ██╗",
    "██║      ██║ ██╔══██╗ ██╔═══██╗╚██╗██╔╝",
    "██║      ██║ ██████╔╝ ██║   ██║ ╚███╔╝ ",
    "██║      ██║ ██╔══██╗ ██║   ██║ ██╔██╗ ",
    "███████╗ ██║ ██║  ██║ ╚██████╔╝██╔╝ ██╗",
    "╚══════╝ ╚═╝ ╚═╝  ╚═╝  ╚═════╝ ╚═╝  ╚═╝"
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
        user  = p.data.get("user_name", "").strip().replace("\\n", "").rstrip("\r\n")
        agent = p.data.get("agent_name", "Lirox")
        if user:
            console.print(f"  [bold #FFC107]Welcome back, {user}! 👋  {agent} is ready.[/]\n")


def show_status_card(profile_data: dict, providers: list):
    agent = profile_data.get("agent_name", "Lirox")
    user  = profile_data.get("user_name", "").strip().replace("\\n", "").rstrip("\r\n")
    prov  = ", ".join(providers[:3]) if providers else "None (run /setup)"
    console.print(f"  [{CLR_DIM}]Agent: {agent}  ·  User: {user or '?'}  ·  Providers: {prov}[/]")


def show_thinking(msg: str):
    console.print(Panel(f"[{CLR_THINK}]{escape(msg)}[/]",
                        title=f"[{CLR_THINK}]🧠 THINKING[/]",
                        border_style="#a78bfa", padding=(0, 1)))


def show_thinking_phase(event: dict):
    """
    Render a live, animated thinking phase.
    """
    from rich.live import Live
    from rich.spinner import Spinner
    
    idx = event.get("phase_index", 0)
    name = event.get("phase_name", "PHASE")
    icon = event.get("phase_icon", "🧠")
    total = event.get("phase_total", 3)
    steps = event.get("steps", [])
    
    # Simple one-line status
    console.print(f"  [bold #a78bfa]{icon} {name}[/] [dim][{idx+1}/{total}][/]")
    for step in steps:
        console.print(f"    [dim]├─ ✓ {step}[/]")

def show_thinking(query: str, steps: list, elapsed: float):
    """
    Show full, expanded thinking results (for /expand thinking)
    """
    from rich.table import Table
    from rich.panel import Panel
    
    table = Table(show_header=True, header_style="bold cyan", box=None)
    table.add_column("Agent / Step", style="bold white")
    table.add_column("Details", style="dim")
    
    for i, step in enumerate(steps):
        agent = "System"
        msg = step
        if ":" in step and len(step.split(":")[0]) < 15:
            agent, msg = step.split(":", 1)
        table.add_row(f"[{i+1}] {agent}", msg.strip())
        
    panel = Panel(
        table,
        title=f"[bold cyan]🧠 Reasoning Trace: {query}[/]",
        subtitle=f"[dim]Total time: {elapsed:.2f}s[/]",
        border_style="cyan",
        padding=(1, 2)
    )
    console.print(panel)



def show_thinking_panel_open(complexity: str):
    """
    Shows the 'Thinking' status line.
    """
    msg = f"  ⟳ [bold #a78bfa]🧠 Thinking[/] [dim]· {complexity} · 5 agents debating...[/] [yellow](type /expand thinking for trace)[/]"
    console.print(msg)


def show_thinking_panel_close(total_ms: int, complexity: str):
    """Print the closing summary inline with the open indicator."""
    secs = total_ms / 1000
    console.print(
        f"[dim]⏱ {secs:.1f}s — /expand thinking for details[/]"
    )


def show_agent_event(message: str, agent: str = "personal", etype: str = "agent_progress"):
    if etype == "agent_start": return
    elif etype == "tool_call":
        console.print(f"  [{CLR_DIM}]  ├─ 🔧 {escape(message)}[/]")
    elif etype == "tool_result":
        if message and message.strip() and len(message.strip()) > 3:
            console.print(f"  [{CLR_DIM}]  ├─ ✓ {escape(message[:200])}[/]")
    elif etype == "agent_progress":
        if message and message.lower().strip() not in {"thinking…", "analyzing…"}:
            console.print(f"  [{CLR_DIM}]  ├─ {escape(message)}[/]")
    elif etype == "error":
        console.print(f"  [{CLR_ERROR}]  ├─ ✖ {escape(message)}[/]")



def show_answer(text: str, agent: str = "personal"):
    icon = "⚡" if agent == "personal" else "🧠"
    console.print(f"{icon} [bold #FFD700]Response:[/]")
    from rich.markdown import Markdown
    from rich.live import Live
    from lirox.utils.streaming import StreamingResponse

    streamer = StreamingResponse()
    full_text = ""
    chunk_count = 0
    _MARKDOWN_WORD_BATCH = 6  # refresh Markdown rendering every N words (avoids partial-markup flicker)
    try:
        with Live(Markdown(""), console=console, refresh_per_second=12) as live:
            for chunk in streamer.stream_words(text, delay=0.025):
                full_text += chunk
                chunk_count += 1
                if chunk_count % _MARKDOWN_WORD_BATCH == 0:
                    try:
                        live.update(Markdown(full_text))
                    except Exception:
                        live.update(full_text)
            # Final update with the complete text so nothing is cut off
            try:
                live.update(Markdown(full_text))
            except Exception:
                live.update(full_text)
    except Exception:
        # Fallback: plain print when Live/Markdown rendering is unsupported
        console.print(text)

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
