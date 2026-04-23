"""UI Components for Displaying Thinking Process."""
from rich.console import Console
from rich.panel import Panel
from rich.markup import escape

console = Console()

class ThinkingDisplay:
    """Display agent thinking to user"""
    
    @staticmethod
    def show_thinking_process(thinking_data: dict):
        """Show what agents thought and debated"""
        console.print("\n[bold #a78bfa]⟳ Thinking (5 agents debating)...[/]")
        
        console.print(f"  [bold #FFC107]ARCHITECT:[/] [dim]{escape(thinking_data.get('architect_said', ''))}[/]")
        console.print(f"  [bold #10b981]BUILDER:[/] [dim]{escape(thinking_data.get('builder_said', ''))}[/]")
        console.print(f"  [bold #3b82f6]RESEARCHER:[/] [dim]{escape(thinking_data.get('researcher_said', ''))}[/]")
        
        debate = thinking_data.get('debate')
        if debate and debate != "All agents are aligned on the execution plan.":
            console.print(f"\n  [bold #ef4444]DEBATE:[/]")
            for line in debate.split('\n'):
                console.print(f"    [dim]{escape(line)}[/]")
                
        console.print(f"\n  [bold #f472b6]SYNTHESIS:[/] [dim]{escape(thinking_data.get('final_decision', ''))}[/]\n")

    @staticmethod
    def show_complete_flow(task: str, result: dict):
        """Show user the complete thinking, debate, verification flow"""
        console.print(f"\n[bold #FFD700][Task][/] {escape(task)}")
        time_taken = result.get('time_taken', 0.0)
        console.print(f"[bold #a78bfa]⟳ Thinking · medium complexity · 3 steps · {time_taken}s[/]")
        
        if result.get('thinking'):
            console.print(f"\n[bold #FFD700][Thinking Process][/]")
            t = result['thinking']
            console.print(f"  [bold #FFC107]Architect:[/] [dim]{escape(t.get('architect_said', '')[:100])}...[/]")
            console.print(f"  [bold #10b981]Builder:[/] [dim]{escape(t.get('builder_said', '')[:100])}...[/]")
            if t.get('debate'):
                console.print(f"  [bold #ef4444]Debate:[/] [dim]{escape(t.get('debate', '')[:100])}...[/]")
                
        if result.get('steps'):
            console.print(f"\n[bold #FFD700][Execution][/]")
            for step in result['steps']:
                console.print(f"  [bold #10b981]✓[/] [dim]{escape(step)}[/]")
                
        if result.get('verification'):
            console.print(f"\n[bold #FFD700][Verification][/]")
            for check in result['verification']:
                console.print(f"  [bold #10b981]✓[/] [dim]{escape(check)}[/]")
                
        if result.get('output'):
            console.print(f"\n[bold #FFD700]⚡ Response:[/]")
            console.print(escape(result['output']))
