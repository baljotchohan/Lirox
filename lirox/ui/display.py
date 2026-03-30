"""
Lirox v0.3 — Terminal Display System

Premium terminal rendering using Rich:
- Dark hacker aesthetic with amber/gold accents
- Structured plan display with tool icons
- Execution trace and reasoning panels
- Interactive confirmation prompts
"""

import time
import sys
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.theme import Theme
from rich.status import Status
from rich.box import ROUNDED
from rich.table import Table
from rich.prompt import Confirm

# Custom Theme: Dark hacker aesthetic with amber/gold accents
custom_theme = Theme({
    "agent": "bold #f5a623",   # Amber
    "user_input": "#7eb8f7",   # Light Blue
    "info": "#4a4845",         # Muted gray
    "success": "#4caf50",      # Green
    "warning": "#ff9800",      # Orange
    "error": "#f44336",        # Red
    "background": "#0a0a0a",
    "text": "#e8e6d9",         # Warm off-white
    "cyan": "#00bcd4",         # Cyan accent
    "purple": "#9c27b0",       # Purple accent
})

console = Console(theme=custom_theme)


def print_logo():
    logo = """
    ██╗     ██╗██████╗  ██████╗ ██╗  ██╗
    ██║     ██║██╔══██╗██╔═══██╗╚██╗██╔╝
    ██║     ██║██████╔╝██║   ██║ ╚███╔╝ 
    ██║     ██║██╔══██╗██║   ██║ ██╔██╗ 
    ███████╗██║██║  ██║╚██████╔╝██╔╝ ██╗
    ╚══════╝╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝
    """
    console.print(Panel(Text(logo, justify="center", style="agent"), border_style="agent", box=ROUNDED))
    console.print(Text("         Personal AI Agent OS • v0.3", justify="center", style="info"))
    console.print("")


def boot_animation():
    steps = [
        ("Initialising memory system...", 0.3),
        ("Loading user profile...", 0.3),
        ("Calibrating LLM router...", 0.2),
        ("Initialising planning engine...", 0.2),
        ("Loading browser & file tools...", 0.2),
        ("Starting reasoning loop...", 0.1),
        ("Agent online.", 0.1)
    ]

    with Progress(
        SpinnerColumn(spinner_name="dots", style="agent"),
        BarColumn(bar_width=20, style="info", complete_style="agent"),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task("Booting...", total=len(steps))
        for step_text, delay in steps:
            time.sleep(delay)
            progress.update(task, advance=1, description=step_text)


def show_status_card(agent_name, user_name, goals, provider, memory_count):
    goal_text = goals[0] if goals else "None set"
    content = Text.assemble(
        ("Agent: ", "info"), (f"{agent_name}", "agent"), ("  •  ", "info"),
        ("User: ", "info"), (f"{user_name}", "text"), ("\n", ""),
        ("Goal:  ", "info"), (f"{goal_text}", "text"), ("\n", ""),
        ("Model: ", "info"), (f"{provider}", "agent"), ("  •  ", "info"),
        ("Memory: ", "info"), (f"{memory_count} exchanges", "text"), ("\n", ""),
        ("Version: ", "info"), ("v0.3 — Autonomous Agent", "agent")
    )
    console.print(Panel(content, border_style="agent", box=ROUNDED, width=60))


def agent_panel(text, agent_name="Lirox"):
    console.print(Panel(Text(text, style="text"), title=f" {agent_name} ", border_style="agent", box=ROUNDED, title_align="left"))


def execute_panel(command):
    console.print(Panel(Text(f"$ {command}", style="text"), title=" Executing ", border_style="info", box=ROUNDED, title_align="left"))


# ─── v0.2 plan display (kept for backward compat) ────────────────────────────

def plan_panel(steps):
    """v0.2 style plan display — flat list."""
    console.print("\n[agent]Planning...[/agent]\n")
    for i, step in enumerate(steps, 1):
        console.print(f"  {i} [info]○[/info] {step}")


# ─── v0.3 Plan Display ───────────────────────────────────────────────────────

# Tool icons for display
TOOL_ICONS = {
    "terminal": "🖥️",
    "browser": "🌐",
    "file_io": "📁",
    "llm": "🧠",
}


def plan_panel_v3(plan):
    """
    Display a structured v0.3 plan with tool icons and metadata.
    """
    goal = plan.get("goal", "Unknown goal")
    steps = plan.get("steps", [])
    est_time = plan.get("estimated_time", "Unknown")
    tools = plan.get("tools_required", [])

    console.print("")
    console.print(Panel(
        Text(f"📋 PLAN: {goal}", style="agent"),
        border_style="agent", box=ROUNDED, title_align="left"
    ))

    # Tools summary
    tool_str = "  ".join(f"{TOOL_ICONS.get(t, '🔧')} {t}" for t in tools)
    console.print(f"  [info]Tools: {tool_str}  •  Est. time: {est_time}[/info]")
    console.print("")

    # Steps
    for step in steps:
        step_id = step.get("id", "?")
        task = step.get("task", "Unknown")
        step_tools = step.get("tools", ["llm"])
        tool_icons = " ".join(TOOL_ICONS.get(t, "🔧") for t in step_tools)
        deps = step.get("depends_on", [])
        dep_str = f" (after step {', '.join(str(d) for d in deps)})" if deps else ""

        console.print(f"  [info]{step_id}[/info] [info]○[/info] {task}")
        console.print(f"    {tool_icons}{dep_str}")

    console.print("")


def update_plan_step(index, step, status="success"):
    """Update a plan step's display with status icon."""
    symbols = {
        "success": ("✓", "success"),
        "progress": ("◷", "warning"),
        "failed": ("✗", "error"),
        "skipped": ("⊘", "info"),
        "pending": ("○", "info"),
    }
    symbol, style = symbols.get(status, ("○", "info"))
    console.print(f"  {index} [{style}]{symbol}[/{style}] {step}")


def reasoning_panel(reasoning_text):
    """Display the reasoning summary in a styled panel."""
    console.print(Panel(
        Text(reasoning_text, style="text"),
        title=" 💭 Reasoning ",
        border_style="cyan",
        box=ROUNDED,
        title_align="left"
    ))


def trace_panel(trace_text):
    """Display the execution trace in a styled panel."""
    console.print(Panel(
        Text(trace_text, style="text"),
        title=" 🔍 Execution Trace ",
        border_style="purple",
        box=ROUNDED,
        title_align="left"
    ))


def confirm_execute():
    """Ask user to confirm plan execution. Returns True/False."""
    try:
        return Confirm.ask("  Execute plan?", default=True, console=console)
    except (EOFError, KeyboardInterrupt):
        return False


def show_status_bar(provider, memory_count, agent_name, user_name):
    bar = f" Provider: {provider}  •  Memory: {memory_count} msg  •  Profile: {agent_name}/{user_name}  •  /help for commands"
    console.print(f"\n[info]{bar}[/info]")


def error_panel(message):
    console.print(Panel(Text(message, style="text"), title=" Error ", border_style="error", box=ROUNDED))


class AgentSpinner:
    def __init__(self, agent_name="Lirox"):
        self.status = Status(f" {agent_name} is thinking...", spinner="dots", spinner_style="agent")
        self._running = False

    def __enter__(self):
        self._running = True
        self.status.start()
        return self

    def stop(self):
        """Idempotent stop."""
        if self._running:
            self.status.stop()
            self._running = False

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
