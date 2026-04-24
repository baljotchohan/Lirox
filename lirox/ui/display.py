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
    """Manages the Live thinking display with progress bars for multi-agent reasoning."""
    def __init__(self):
        self.live: Optional[Live] = None
        self.layout: Optional[Layout] = None
        self.progress = None
        self.agent_tasks: Dict[str, Any] = {}
        self.steps: List[str] = []
        self.current_phase_idx = -1
        self._display = None
        try:
            from lirox.ui.thinking_config import DEFAULT_THINKING_CONFIG
            self.config = DEFAULT_THINKING_CONFIG
        except ImportError:
            self.config = None

    @property
    def _adv(self):
        if self._display is None:
            from lirox.ui.advanced_thinking_display import AdvancedThinkingDisplay
            self._display = AdvancedThinkingDisplay()
        return self._display

    def start(self, task_summary: str):
        if self.config and getattr(self.config, 'display_style', 'full') == 'minimal':
            return
        if self.live:
            return  # already running

        self.progress, self.agent_tasks = self._adv.create_live_progress()
        self.layout = self._adv.build_live_layout(self.progress, task_summary)

        self.live = Live(self.layout, console=console, refresh_per_second=12, transient=True)
        self.live.start()

    def update(self, agent_name: str, message: str, status: str = "done"):
        """Update a specific agent's progress bar."""
        if self.progress and agent_name in self.agent_tasks:
            task_id = self.agent_tasks[agent_name]
            if status == "done":
                self.progress.update(task_id, completed=100)
            elif status == "running":
                self.progress.update(task_id, advance=5)
            elif status == "warning":
                self.progress.update(task_id, completed=100)
        self.steps.append(f"{agent_name}: {message}")

    def update_status(self, icon: str, message: str, border: str = "cyan"):
        if self.layout:
            self._adv.update_status(self.layout, icon, message, border)

    def show_synthesis(self, decision: str, confidence: int, elapsed: float):
        if self.layout:
            self._adv.show_synthesis_panel(self.layout, decision, confidence, elapsed)

    def add_log(self, message: str):
        self.steps.append(message)

    def stop(self):
        if self.live:
            try:
                self.live.stop()
            except Exception:
                pass
            self.live = None
            self.layout = None
            self.progress = None
            self.agent_tasks = {}

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
    """Render thinking phase progress using the Live layout.
    
    Uses the ThinkingDisplayManager to show progress bars per agent and 
    real-time status updates for the current phase.
    """
    idx = event.get("phase_index", 0)
    name = event.get("phase_name", "PHASE")
    icon = event.get("phase_icon", "🧠")
    tagline = event.get("phase_tagline", "")
    
    # Start the live display on the first phase
    if idx == 0 and not thinking_manager.live:
        thinking_manager.start(tagline or "Analyzing task...")
    
    # Update the status panel with current phase info
    thinking_manager.update_status(icon, f"[bold]{name}[/] · {tagline}")

def show_agent_event(message: str, agent: str = "personal", etype: str = "agent_progress"):
    """Show agent events. If thinking display is active, route to progress bars."""
    if thinking_manager.live and agent != "personal":
        status = "done" if "finished" in message.lower() or "✓" in message else "running"
        if "Resolving" in message or "Analyzing conflict" in message:
            thinking_manager.update_status("💬", message, border="yellow")
        else:
            thinking_manager.update(agent, message, status=status)
    else:
        # Fallback to inline for tool calls or when thinking display is off
        if etype == "tool_call":
            console.print(f"  [{CLR_DIM}]  ├─ 🔧 {escape(message)}[/]")
        elif etype == "agent_progress":
            console.print(f"  [{CLR_DIM}]  ├─ {escape(message)}[/]")


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

def show_thinking(query: str, steps: list, elapsed: float, full_result: Optional[Dict] = None):
    """Show full, expanded thinking results (for /expand thinking).
    
    If full_result is provided (from RealThinkingEngine), shows the rich
    agent perspective view. Otherwise falls back to step-based display.
    """
    if full_result:
        from lirox.ui.advanced_thinking_display import AdvancedThinkingDisplay
        AdvancedThinkingDisplay().show_expanded_result(full_result)
        return
    
    # Fallback: step-based display
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
