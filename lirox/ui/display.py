"""
Lirox v0.5 — Professional Terminal UI (Lion Edition)

Aesthetic components for the command-line experience:
- Modern, hacker-ready terminal panels in Lion Yellow.
- Real-time spinners with dynamic message updates.
- System status cards with version v0.5.
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
from rich.box import ROUNDED
from lirox.config import APP_VERSION

console = Console()

# ─── Color Palette ──────────────────────────────────────────────────────────
# Lion Branding: Yellow (#FFC107) and Gold variants.

CLR_LIROX = "bold #FFC107"  # Official Lirox Yellow
CLR_ACCENT = "bold #FFD54F" # Amber Lite
CLR_SUCCESS = "bold #10b981" # Emerald Green
CLR_ERROR = "bold #ef4444"   # Rose Red
CLR_WARN = "bold #FFC107"    # Standard Yellow
CLR_DIM = "dim #94a3b8"      # Slate
CLR_WHITE = "bold #ffffff"
CLR_PURPLE = "bold #a855f7"

# ─── Logos & Branding ───────────────────────────────────────────────────────

LOGO = f"""
  [bold #FFB300]██╗     ██╗██████╗  ██████╗ ██╗  ██╗[/]
  [bold #FFC107]██║     ██║██╔══██╗██╔═══██╗╚██╗██╔╝[/]
  [bold #FFD54F]██║     ██║██████╔╝██║   ██║ ╚███╔╝ [/]
  [bold #FFC107]██║     ██║██╔══██╗██║   ██║ ██╔██╗ [/]
  [bold #FFB300]███████╗██║██║  ██║╚██████╔╝██╔╝ ██╗[/]
  [bold #FFA000]╚══════╝╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝[/]
  [{CLR_LIROX}]v{APP_VERSION} ✦ AUTONOMOUS KERNEL[/]
"""

def show_welcome():
    console.print(LOGO)

# ─── Status Cards ───────────────────────────────────────────────────────────

def show_status_card(profile_data, providers):
    table = Table(box=None, padding=(0, 2))
    table.add_column("Kernel Status", style=CLR_LIROX)
    table.add_column("Operator Domain", style=CLR_ACCENT)
    
    agent_name = profile_data.get("agent_name", "Lirox")
    user_name = profile_data.get("user_name", "Operator")
    niche = profile_data.get("niche", "Generalist")
    
    table.add_row(
        f"Designation: [white]{agent_name}[/]\nEngine: [white]v{APP_VERSION}[/]",
        f"Operator: [white]{user_name}[/]\nDomain: [white]{niche}[/]"
    )
    
    prov_str = ", ".join(available_styled_providers(providers))
    
    console.print(Panel(
        table,
        title=f"[{CLR_LIROX}] INITIALIZING CORE [/]",
        subtitle=f"[{CLR_DIM}] Channels: {prov_str or 'None'} [/]",
        border_style=CLR_LIROX,
        padding=(1, 2)
    ))

def available_styled_providers(providers):
    return [f"[bold green]{p}[/]" for p in providers[:5]]

# ─── Spinners & Live Updating ───────────────────────────────────────────────

class AgentSpinner:
    """Manages a persistent, updateable spinner for the terminal."""
    def __init__(self, message="Thinking..."):
        self.message = message
        self.spinner = Spinner("dots", style=CLR_LIROX)
        self.live = None

    def start(self):
        self.live = Live(self._render(), refresh_per_second=10, transient=True)
        self.live.start()

    def update_message(self, new_message: str):
        self.message = new_message
        if self.live:
            self.live.update(self._render())

    def stop(self):
        if self.live:
            self.live.stop()

    def _render(self):
        return Columns([self.spinner, Text(f" {self.message}", style=CLR_ACCENT)])


def thinking_panel(goal: str, thought_trace: str):
    """Render a sophisticated reasoning panel with phase-based layouts."""
    phases = {"PHASE 1": "", "PHASE 2": "", "PHASE 3": ""}
    current_phase = None

    for line in thought_trace.split("\n"):
        if "PHASE 1" in line.upper(): current_phase = "PHASE 1"
        elif "PHASE 2" in line.upper(): current_phase = "PHASE 2"
        elif "PHASE 3" in line.upper(): current_phase = "PHASE 3"
        elif current_phase:
            phases[current_phase] += line + "\n"

    # Fallback if no phases found
    if not any(phases.values()):
        phases["PHASE 1"] = thought_trace

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body")
    )
    layout["body"].split_row(
        Layout(Panel(phases["PHASE 1"].strip(), title="[bold]01 ANALYSIS", border_style=CLR_LIROX)),
        Layout(Panel(phases["PHASE 2"].strip(), title="[bold]02 LOGIC", border_style="#4ecdc4")),
        Layout(Panel(phases["PHASE 3"].strip(), title="[bold]03 RISK", border_style="#ff6b6b"))
    )

    header_text = Text.assemble(
        (" 🧠 INTERNAL REASONING ", "bold black on #FFC107"),
        (f"  Target: {goal[:50]}...", CLR_DIM)
    )
    layout["header"].update(header_text)

    console.print("\n")
    console.print(Panel(
        layout,
        border_style=CLR_LIROX,
        padding=(1, 1),
        height=18
    ))
    console.print("\n")

# ─── Execution Trace ────────────────────────────────────────────────────────

def show_plan_table(plan):
    table = Table(title="STRATEGIC DEPLOYMENT PLAN", border_style=CLR_DIM, header_style=CLR_LIROX)
    table.add_column("Phase", justify="center", width=6)
    table.add_column("Objective", style="white")
    table.add_column("Tools", justify="right", style=CLR_ACCENT)
    
    for i, step in enumerate(plan.get("steps", []), 1):
        tools = ", ".join(step.get("tools", ["llm"]))
        table.add_row(str(i), step["task"], tools)
    
    console.print(table)

def execute_panel(command):
    console.print(f"[{CLR_DIM}]DEPLOYING:[/] [bold white]{command}[/]")

def update_plan_step(step_id, task, status="waiting"):
    icon = "⏳" if status == "waiting" else "⚙️" if status == "progress" else "✅" if status == "success" else "❌"
    color = CLR_DIM if status == "waiting" else CLR_LIROX if status == "progress" else CLR_SUCCESS if status == "success" else CLR_ERROR
    
    console.print(f"  {icon} [italic {color}]Phase {step_id}: {task}[/]")

# ─── Success & Utilities ────────────────────────────────────────────────────

def success_message(text):
    console.print(Panel(
        f"[{CLR_SUCCESS}]✓ MISSION PROTOCOL COMPLETE[/]\n\n{text}",
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

def show_completion_art():
    # Subtle solar flare in yellow
    art = f"""
    [{CLR_LIROX}]      .
            .
      .  :  .
       : : :
     '.: : :.'
       ' : '
         ' [/]
    """
    console.print(art)
