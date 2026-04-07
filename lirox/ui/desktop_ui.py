"""Live desktop screen UI with real-time rendering"""
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.table import Table
import time

console = Console()


def show_desktop_task_live(task_description: str, screenshot_func, interval: float = 1.0):
    """
    Display live desktop task with real-time screen updates.
    
    Args:
        task_description: What the agent is doing
        screenshot_func: Function that returns PIL Image
        interval: Update frequency (seconds)
    """
    
    task_start = time.time()
    
    with Live(console=console, refresh_per_second=1) as live:
        step = 0
        while True:
            # Take screenshot
            screenshot = screenshot_func(annotate=True)
            elapsed = time.time() - task_start
            
            # Build display table
            table = Table(title="⚡ Lirox Desktop Control")
            table.add_column("Task", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Time", style="yellow")
            table.add_column("Step", style="magenta")
            
            status = "🟢 ACTIVE" if elapsed < 300 else "🟡 TIMEOUT"
            table.add_row(
                task_description[:50],
                status,
                f"{elapsed:.1f}s",
                f"{step}",
            )
            
            # Create display panel with screenshot metadata
            display_text = Text()
            display_text.append("Screen: ", style="bold cyan")
            display_text.append(f"{1920}x{1080}\n", style="green")
            display_text.append(f"Updated: {time.strftime('%H:%M:%S')}\n", style="dim")
            
            panel = Panel(
                table,
                title="[bold cyan]Live Desktop Stream[/]",
                border_style="cyan",
                padding=(1, 2),
            )
            
            live.update(panel)
            step += 1
            time.sleep(interval)


def show_desktop_results(workspace_path: str, files_created: list, validation: str):
    """Display desktop task results."""
    
    panel = Panel(
        f"✅ Desktop Task Complete\n\n"
        f"Workspace: {workspace_path}\n"
        f"Files: {len(files_created)}\n\n"
        f"Validation:\n{validation}",
        title="[bold green]Results[/]",
        border_style="green",
    )
    
    console.print(panel)
