"""
Display REAL thinking from REAL LLM calls
Stream actual responses, not fake data
"""

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
import time


class RealThinkingDisplay:
    """
    Display thinking from REAL LLM responses
    """
    
    def __init__(self):
        self.console = Console()
        self.is_expanded = False
    
    def show_thinking_compact(self, task: str, num_agents: int = 5):
        """
        Compact view with expand option
        """
        compact = Text()
        compact.append("⟳ ", style="cyan")
        compact.append("Thinking ", style="bold cyan")
        compact.append(f"({num_agents} agents) ", style="dim")
        compact.append("· ", style="dim")
        compact.append("Press /expand for details", style="yellow")
        
        self.console.print(compact)
    
    def show_thinking_expanded(self, result: dict):
        """
        Show REAL thinking results (not fake)
        
        Args:
            result: Output from RealThinkingEngine.think_and_decide()
        """
        
        # Show each agent's REAL view
        self.console.print("\n[bold cyan]🧠 MULTI-AGENT REASONING[/bold cyan]\n")
        
        for agent_name, view in result['agent_views'].items():
            panel = Panel(
                f"[bold]{view['summary']}[/bold]\n\n"
                f"{view.get('analysis', '')}\n\n"
                f"[dim]Concerns: {view.get('concerns', 'None')}[/dim]",
                title=f"🤖 {agent_name}",
                border_style="cyan"
            )
            self.console.print(panel)
        
        # Show REAL debate (if any)
        if result['debate']['conflicts']:
            self.console.print("\n[bold yellow]💬 DEBATE[/bold yellow]\n")
            
            for conflict in result['debate']['conflicts']:
                self.console.print(
                    f"  {conflict['agent_a']} vs {conflict['agent_b']}: "
                    f"{conflict['conflict']}\n"
                    f"  → Resolved: {conflict['resolution']}\n"
                )
        
        # Show REAL synthesis
        self.console.print("\n[bold green]🎯 SYNTHESIS[/bold green]\n")
        
        synth = result['synthesis']
        panel = Panel(
            f"[bold]{synth['final_decision']}[/bold]\n\n"
            f"{synth['reasoning']}\n\n"
            f"Confidence: {synth['confidence']}% | "
            f"Time: {result['time_taken']}s",
            border_style="green"
        )
        self.console.print(panel)
