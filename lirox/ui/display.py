"""
Lirox v0.5 — Professional Terminal UI

Aesthetic components for the command-line experience:
- Modern, hacker-ready terminal panels
- Real-time spinners with dynamic message updates
- System status cards with version v0.5
- Execution trace & thinking breakdown visuals
- Confetti-inspired success animations (ASCII)
"""

import sys
import time
import threading
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text
from rich.layout import Layout
from rich.columns import Columns
from rich.progress import Progress, SpinnerColumn, TextColumn
from lirox.config import APP_VERSION

console = Console()

# ─── Color Palette ──────────────────────────────────────────────────────────

CLR_LIROX = "bold #3b82f6"  # Premium Blue
CLR_ACCENT = "bold #60a5fa"
CLR_SUCCESS = "bold #10b981" # Emerald Green
CLR_ERROR = "bold #ef4444"   # Rose Red
CLR_WARN = "bold #f59e0b"    # Amber
CLR_DIM = "dim #94a3b8"      # Slate

# ─── Logos & Branding ───────────────────────────────────────────────────────

LOGO = f"""
  [bold #1d4ed8]██╗     ██╗██████╗  ██████╗ ██╗  ██╗[/]
  [bold #2563eb]██║     ██║██╔══██╗██╔═══██╗╚██╗██╔╝[/]
  [bold #3b82f6]██║     ██║██████╔╝██║   ██║ ╚███╔╝ [/]
  [bold #60a5fa]██║     ██║██╔══██╗██║   ██║ ██╔██╗ [/]
  [bold #93c5fd]███████╗██║██║  ██║╚██████╔╝██╔╝ ██╗[/]
  [bold #bfdbfe]╚══════╝╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝[/]
  [bold #3b82f6]v{APP_VERSION} ✦ AUTONOMOUS AGENT OS[/]
"""

def show_welcome():
    console.print(LOGO)

# ─── Status Cards ───────────────────────────────────────────────────────────

def show_status_card(profile_data, providers):
    table = Table(box=None, padding=(0, 2))
    table.add_column("Agent Status", style=CLR_LIROX)
    table.add_column("Operator Context", style=CLR_ACCENT)
    
    agent_name = profile_data.get("agent_name", "Lirox")
    user_name = profile_data.get("user_name", "Operator")
    niche = profile_data.get("niche", "Generalist")
    
    table.add_row(
        f"Name: [white]{agent_name}[/]\nVersion: [white]{APP_VERSION}[/]",
        f"User: [white]{user_name}[/]\nNiche: [white]{niche}[/]"
    )
    
    prov_str = ", ".join(providers[:4]) + (f" (+{len(providers)-4})" if len(providers) > 4 else "")
    
    console.print(Panel(
        table,
        title=f"[{CLR_LIROX}] SYSTEM PARAMETERS [/]",
        subtitle=f"[{CLR_DIM}] Active Channels: {prov_str or 'None'} [/]",
        border_style=CLR_LIROX,
        padding=(1, 2)
    ))

# ─── Spinners & Live Updating ───────────────────────────────────────────────

class AgentSpinner:
    """Manages a persistent, updateable spinner for the terminal."""
    def __init__(self, message="Thinking..."):
        self.message = message
        self.spinner = Spinner("dots", style=CLR_LIROX)
        self.live = None

    def start(self):
        self.live = Live(self._render(), refresh_per_second=10)
        self.live.start()

    def update_message(self, new_message: str):
        """Update the message being displayed next to the spinner."""
        self.message = new_message
        if self.live:
            self.live.update(self._render())

    def stop(self):
        if self.live:
            self.live.stop()

    def _render(self):
        return Columns([self.spinner, Text(f" {self.message}", style=CLR_ACCENT)])


def thinking_panel(goal: str, thought_trace: str):
    """Shows a detailed 'Internal Monologue' panel."""
    console.print(Panel(
        thought_trace,
        title=f"[{CLR_WARN}] INTERNAL REASONING: {goal[:40]}... [/]",
        title_align="left",
        border_style=CLR_WARN,
        padding=(1, 2)
    ))

# ─── Execution Trace ────────────────────────────────────────────────────────

def show_plan_table(plan):
    table = Table(title="STRATEGIC EXECUTION PLAN", border_style=CLR_DIM, header_style=CLR_LIROX)
    table.add_column("Phase", justify="center", width=6)
    table.add_column("Autonomous Objective", style="white")
    table.add_column("Tools", justify="right", style=CLR_ACCENT)
    
    for i, step in enumerate(plan.get("steps", []), 1):
        tools = ", ".join(step.get("tools", ["llm"]))
        table.add_row(str(i), step["task"], tools)
    
    console.print(table)

def execute_panel(command):
    console.print(f"[{CLR_DIM}]执行指令:[/] [bold white]{command}[/]")

def update_plan_step(step_id, task, status="waiting"):
    """
    Called by executor to indicate progress.
    status: waiting, progress, success, failed, error
    """
    icon = "⏳" if status == "waiting" else "⚙️" if status == "progress" else "✅" if status == "success" else "❌"
    color = CLR_DIM if status == "waiting" else CLR_LIROX if status == "progress" else CLR_SUCCESS if status == "success" else CLR_ERROR
    
    console.print(f"  {icon} [italic {color}]Step {step_id}: {task}[/]")

# ─── Success & Utilities ────────────────────────────────────────────────────

def success_message(text):
    console.print(Panel(
        f"[{CLR_SUCCESS}]✓ MISSION COMPLETE[/]\n\n{text}",
        border_style=CLR_SUCCESS,
        padding=(1, 2)
    ))

def error_panel(title, error):
    console.print(Panel(
        f"[{CLR_ERROR}]{error}[/]",
        title=f"[{CLR_ERROR}] {title} [/]",
        border_style=CLR_ERROR,
        padding=(1, 2)
    ))

def info_panel(text):
    console.print(Panel(text, border_style=CLR_LIROX, padding=(1, 2)))

def confirm_prompt(message: str) -> bool:
    from rich.prompt import Confirm
    return Confirm.ask(f"[{CLR_WARN}]{message}[/]")

# ─── ASCII Art Fun ──────────────────────────────────────────────────────────

def show_completion_art():
    art = f"""
    [{CLR_SUCCESS}]      .
            .
      .  :  .
       : : :
     '.: : :.'
       ' : '
         ' [/]
    """
    console.print(art)
