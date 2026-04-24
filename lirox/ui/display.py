"""Lirox v1.1 — Terminal UI
Advanced Rich-based display with Live layouts for multi-agent thinking.
"""
import re
import time
from rich.console import Console
from rich.panel import Panel
from rich.markup import escape
from rich.table import Table
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.spinner import Spinner
from rich.progress import Progress, SpinnerColumn, TextColumn
from lirox.config import APP_VERSION
from typing import Dict, List, Any, Optional

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


class ThinkingDisplayManager:
    """Manages the Live thinking display for multi-agent reasoning."""
    def __init__(self):
        self.live: Optional[Live] = None
        self.layout: Optional[Layout] = None
        self.agent_statuses = {}
        self.steps = []
        self.phase_info = {}
        self.current_phase_idx = -1
        try:
            from lirox.ui.thinking_config import DEFAULT_THINKING_CONFIG
            self.config = DEFAULT_THINKING_CONFIG
        except ImportError:
            self.config = None

    def start(self, task_summary: str):
        if self.config and self.config.display_style == 'minimal':
            # Support minimal mode if needed
            return
            
        self.layout = Layout()

        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=3)
        )
        self.layout["body"].split_row(
            Layout(name="agents", ratio=2),
            Layout(name="log", ratio=1)
        )
        # Agents grid (2 rows, 3 cols)
        self.layout["agents"].split_column(
            Layout(name="row1"),
            Layout(name="row2")
        )
        self.layout["row1"].split_row(Layout(name="Arch"), Layout(name="Build"), Layout(name="Res"))
        self.layout["row2"].split_row(Layout(name="Exec"), Layout(name="Ver"), Layout(name="Sys"))
        
        self.update_header(task_summary)
        self.update_footer("Initializing multi-agent protocols...")
        
        for agent in ["Arch", "Build", "Res", "Exec", "Ver", "Sys"]:
            self.agent_statuses[agent] = "Waiting..."
            self._update_agent_panel(agent)

        self.live = Live(self.layout, console=console, refresh_per_second=10, transient=True)
        self.live.start()

    def update_header(self, task: str):
        if self.layout:
            self.layout["header"].update(Panel(f"🧠 [bold white]REASONING:[/] {task[:70]}...", border_style="#a78bfa"))

    def update_footer(self, msg: str):
        if self.layout:
            self.layout["footer"].update(Panel(f" [cyan]●[/] {msg}", border_style="dim"))

    def _update_agent_panel(self, agent_id: str, status: str = None, style: str = "dim"):
        if not self.layout: return
        if status: self.agent_statuses[agent_id] = status
        
        names = {"Arch": "Architect", "Build": "Builder", "Res": "Researcher", "Exec": "Executor", "Ver": "Verifier", "Sys": "Consensus"}
        name = names.get(agent_id, agent_id)
        
        icon = "🤖"
        if "finished" in self.agent_statuses[agent_id].lower(): icon = "✅"; style = "green"
        elif "running" in self.agent_statuses[agent_id].lower(): icon = Spinner("dots", style="cyan"); style = "cyan"
        elif "warning" in self.agent_statuses[agent_id].lower(): icon = "⚠️"; style = "yellow"
        
        panel = Panel(
            Text.assemble((f"{icon} ", style), (self.agent_statuses[agent_id], "italic")),
            title=f"[bold]{name}[/]",
            border_style=style
        )
        try: self.layout[agent_id].update(panel)
        except: pass

    def update_agent(self, agent_name: str, message: str, status: str = "done"):
        mapping = {"Architect": "Arch", "Builder": "Build", "Researcher": "Res", "Executor": "Exec", "Verifier": "Ver", "System": "Sys"}
        aid = mapping.get(agent_name)
        if aid:
            self._update_agent_panel(aid, message, style="green" if status == "done" else "cyan")

    def add_log(self, message: str):
        self.steps.append(message)
        if self.layout:
            table = Table(show_header=False, box=None, padding=(0,1))
            table.add_column(style="dim")
            for s in self.steps[-8:]: # Last 8 steps
                table.add_row(f"├─ {s[:40]}")
            self.layout["log"].update(Panel(table, title="[dim]LOG[/]", border_style="dim"))

    def stop(self):
        if self.live:
            self.live.stop()
            self.live = None
            self.layout = None

# Global manager instance
thinking_manager = ThinkingDisplayManager()

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


def show_thinking_phase(event: dict):
    """Render a live, animated thinking phase."""
    if not thinking_manager.live:
        thinking_manager.start(event.get("phase_tagline", "Analyzing task..."))
    
    idx = event.get("phase_index", 0)
    name = event.get("phase_name", "PHASE")
    icon = event.get("phase_icon", "🧠")
    total = event.get("phase_total", 3)
    steps = event.get("steps", [])
    
    thinking_manager.update_footer(f"{icon} {name} [{idx+1}/{total}]")
    for step in steps:
        thinking_manager.add_log(step)

def show_agent_event(message: str, agent: str = "personal", etype: str = "agent_progress"):
    if not thinking_manager.live:
        # Fallback if not in parallel thinking mode
        if etype == "tool_call":
            console.print(f"  [{CLR_DIM}]  ├─ 🔧 {escape(message)}[/]")
        elif etype == "agent_progress":
            console.print(f"  [{CLR_DIM}]  ├─ {escape(message)}[/]")
        return

    # If it's a specific agent result from the real_engine
    if etype == "agent_progress":
        # Check if the agent parameter is one of our specialists
        if agent in ["Architect", "Builder", "Researcher", "Executor", "Verifier", "System"]:
            thinking_manager.update_agent(agent, message)
            return
            
        # Fallback to parsing message if agent is generic
        if ":" in message:
            parts = message.split(":", 1)
            agent_name = parts[0].strip()
            msg = parts[1].strip()
            if agent_name in ["Architect", "Builder", "Researcher", "Executor", "Verifier", "System"]:
                thinking_manager.update_agent(agent_name, msg)
                return
        
        thinking_manager.add_log(message)
        thinking_manager.update_footer(message)


def show_answer(text: str, agent: str = "personal"):
    # Always stop the thinking display before showing final answer
    thinking_manager.stop()
    
    icon = "⚡" if agent == "personal" else "🧠"
    console.print(f"{icon} [bold #FFD700]Response:[/]")
    from rich.markdown import Markdown
    from rich.live import Live
    from lirox.utils.streaming import StreamingResponse

    streamer = StreamingResponse()
    full_text = ""
    chunk_count = 0
    _MARKDOWN_WORD_BATCH = 6 
    try:
        with Live(Markdown(""), console=console, refresh_per_second=12) as live:
            for chunk in streamer.stream_words(text, delay=0.015):
                full_text += chunk
                chunk_count += 1
                if chunk_count % _MARKDOWN_WORD_BATCH == 0:
                    try: live.update(Markdown(full_text))
                    except: live.update(full_text)
            try: live.update(Markdown(full_text))
            except: live.update(full_text)
    except Exception:
        console.print(text)

    console.print(f"  [{CLR_SUCCESS}]✓ Done[/]")

def show_thinking(query: str, steps: list, elapsed: float):
    """Show full, expanded thinking results (for /expand thinking)."""
    table = Table(show_header=True, header_style="bold cyan", box=None)
    table.add_column("Agent / Step", style="bold white")
    table.add_column("Details", style="dim")
    
    for i, step in enumerate(steps):
        agent = "System"
        msg = step
        if ":" in step and len(step.split(":")[0]) < 15:
            agent, msg = step.split(":", 1)
        table.add_row(f"[{i+1}] {agent}", msg.strip())
        
    panel = Panel(table, title=f"[bold cyan]🧠 Reasoning Trace: {query}[/]",
                  subtitle=f"[dim]Total time: {elapsed:.2f}s[/]",
                  border_style="cyan", padding=(1, 2))
    console.print(panel)

def render_streaming_chunk(chunk: str):
    console.print(chunk, end="", highlight=False)

def error_panel(title: str, msg: str):
    thinking_manager.stop()
    console.print(Panel(f"[{CLR_ERROR}]{escape(msg)}[/]", title=f"[{CLR_ERROR}]{title}[/]", border_style="red"))

def info_panel(msg: str):
    console.print(Panel(f"[white]{escape(msg)}[/]", border_style="#FFC107", padding=(0, 2)))

def success_message(msg: str):
    console.print(Panel(f"[{CLR_SUCCESS}]{escape(msg)}[/]", border_style="green", padding=(0, 2)))

def confirm_prompt(msg: str) -> bool:
    answer = console.input(f"  [bold #FFC107]{msg} (y/n): [/]").strip().lower()
    return answer in ("y", "yes")
