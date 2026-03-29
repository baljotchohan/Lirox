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

# Custom Theme: Dark hacker aesthetic with amber/gold accents
custom_theme = Theme({
    "agent": "bold #f5a623", # Amber
    "user_input": "#7eb8f7", # Light Blue
    "info": "#4a4845",       # Muted gray
    "success": "#4caf50",    # Green
    "warning": "#ff9800",    # Orange
    "error": "#f44336",      # Red
    "background": "#0a0a0a",
    "text": "#e8e6d9",       # Warm off-white
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
    console.print(Text("         Personal AI Agent OS • v0.2", justify="center", style="info"))
    console.print("\n")

def boot_animation():
    steps = [
        ("Initialising memory system...", 0.3),
        ("Loading user profile...", 0.4),
        ("Calibrating LLM router...", 0.2),
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
        ("Memory: ", "info"), (f"{memory_count} exchanges", "text")
    )
    console.print(Panel(content, border_style="agent", box=ROUNDED, width=60))

def agent_panel(text, agent_name="Lirox"):
    console.print(Panel(Text(text, style="text"), title=f" {agent_name} ", border_style="agent", box=ROUNDED, title_align="left"))

def execute_panel(command):
    console.print(Panel(Text(f"$ {command}", style="text"), title=" Executing ", border_style="info", box=ROUNDED, title_align="left"))

def plan_panel(steps):
    console.print("\n[agent]Planning...[/agent]\n")
    for i, step in enumerate(steps, 1):
        console.print(f"  {i} [info]○[/info] {step}")

def update_plan_step(index, step, status="success"):
    # Clear line and rewrite with status
    symbol = "✓" if status == "success" else "◷" if status == "progress" else "○"
    style = "success" if status == "success" else "warning" if status == "progress" else "info"
    console.print(f"  {index} [{style}]{symbol}[/{style}] {step}")

def show_status_bar(provider, memory_count, agent_name, user_name):
    bar = f" Provider: {provider}  •  Memory: {memory_count} msg  •  Profile: {agent_name}/{user_name}  •  /help for commands"
    console.print(f"\n[info]{bar}[/info]")

def error_panel(message):
    console.print(Panel(Text(message, style="text"), title=" Error ", border_style="error", box=ROUNDED))

class AgentSpinner:
    def __init__(self, agent_name="Lirox"):
        self.status = Status(f" {agent_name} is thinking...", spinner="dots", spinner_style="agent")
    
    def __enter__(self):
        self.status.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.status.stop()
