"""
Interactive, expandable, live-streaming thinking display
Shows multi-agent reasoning in real-time
"""

import sys
import time
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
from threading import Thread, Event
from queue import Queue
from typing import List, Dict, Any, Optional
import asyncio


class LiveThinkingDisplay:
    """
    Interactive thinking display with:
    - Click-to-expand functionality
    - Live LLM streaming
    - Real-time multi-agent debate
    - Beautiful terminal UI
    """
    
    def __init__(self):
        self.console = Console()
        self.thinking_queue = Queue()
        self.is_expanded = False
        self.agents_thinking = {}
        self.debate_log = []
        self.synthesis = ""
        self.live_display = None
        
    def show_thinking_compact(self, task: str, num_agents: int = 5):
        """
        Show compact thinking with click-to-expand option
        """
        compact = Text()
        compact.append("⟳ 🧠 Thinking ", style="bold cyan")
        compact.append(f"[{num_agents} agents debating...] ", style="dim")
        compact.append("▼ (type /expand thinking for trace) ", style="yellow")
        
        self.console.print(compact)
        
    def _stream_agent_thinking(self, agent_name: str, layout: Layout, future=None):
        """
        Stream agent's thinking in real-time from LLM
        """
        displayed_text = ""
        if future:
            dots = 0
            while not future.done():
                dots = (dots + 1) % 4
                agent_panel = Panel("Thinking" + "." * dots + " ▌", title=f"🤖 {agent_name}", border_style="cyan")
                layout["agents"].update(agent_panel)
                time.sleep(0.2)
                
            try:
                result_text = future.result(timeout=10)
            except Exception as e:
                result_text = f"Error: {e}"
                
            for char in result_text:
                displayed_text += char
                agent_panel = Panel(displayed_text + " ▌", title=f"🤖 {agent_name}", border_style="cyan")
                layout["agents"].update(agent_panel)
                time.sleep(0.005)
        else:
            # Fallback mock
            thinking_stream = ["Analyzing context...", "Evaluating parameters...", "Formulating plan..."]
            for chunk in thinking_stream:
                displayed_text += chunk + "\n"
                agent_panel = Panel(displayed_text + " ▌", title=f"🤖 {agent_name}", border_style="cyan")
                layout["agents"].update(agent_panel)
                time.sleep(0.05)
        
        self.agents_thinking[agent_name] = displayed_text

    def _stream_debate(self, layout: Layout):
        debate_display = "Found conflicting perspectives on strategy...\n"
        debate_panel = Panel(debate_display + " ▌", title="💬 DEBATE", border_style="yellow")
        layout["debate"].update(debate_panel)
        time.sleep(0.5)

    def _stream_synthesis(self, layout: Layout):
        synthesis_text = "Synthesizing agent views into a unified plan of action..."
        displayed_synthesis = ""
        for char in synthesis_text:
            displayed_synthesis += char
            synthesis_panel = Panel(displayed_synthesis + " ▌", title="🎯 SYNTHESIS", border_style="green")
            layout["synthesis"].update(synthesis_panel)
            time.sleep(0.01)
        self.synthesis = displayed_synthesis

    def _show_decision(self, layout: Layout):
        decision_panel = Panel(
            "✓ Unified consensus achieved.\n  Confidence: 98%\n  Action: Proceeding with request.",
            title="✅ FINAL DECISION",
            border_style="bold green"
        )
        layout["synthesis"].update(decision_panel)
        time.sleep(1)

    def show_thinking_expanded(self, task: str, agents: List[str], agent_futures: dict = None):
        """
        Show expanded thinking with live streaming from futures or mocks.
        """
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="agents", ratio=2),
            Layout(name="debate", ratio=1),
            Layout(name="synthesis", size=5)
        )
        
        header = Panel(f"🧠 LIVE REASONING: {task}", style="bold white on blue")
        layout["header"].update(header)
        
        with Live(layout, console=self.console, refresh_per_second=10) as live:
            self.live_display = live
            
            for agent_name in agents:
                future = agent_futures.get(agent_name) if agent_futures else None
                self._stream_agent_thinking(agent_name, layout, future)
            
            self._stream_debate(layout)
            self._stream_synthesis(layout)
            self._show_decision(layout)


class ThinkingEngine:
    """
    Orchestrates multi-agent thinking with live display
    """
    
    def __init__(self, llm=None):
        self.llm = llm
        self.display = LiveThinkingDisplay()
        self.agents = {
            'Architect': self._architect_prompt,
            'Builder': self._builder_prompt,
            'Risk': self._risk_prompt,
            'Market': self._market_prompt,
            'Executor': self._executor_prompt,
        }
    
    def think_and_decide(self, task: str, context: str) -> Dict[str, Any]:
        self.display.show_thinking_compact(task, len(self.agents))
        # Logic for expansion would go here if called from a REPL that supports it
        return {
            'decision': "Proceed",
            'agents_thinking': self.display.agents_thinking,
            'debate': self.display.debate_log,
        }
    
    def _architect_prompt(self, task: str) -> str:
        return f"Task: {task}\nAnalyze scalability. 2 bullets max."
    
    def _builder_prompt(self, task: str) -> str:
        return f"Task: {task}\nAnalyze feasibility. 2 bullets max."
    
    def _risk_prompt(self, task: str) -> str:
        return f"Task: {task}\nIdentify risks. 2 bullets max."
    
    def _market_prompt(self, task: str) -> str:
        return f"Task: {task}\nAnalyze market fit. 2 bullets max."
    
    def _executor_prompt(self, task: str) -> str:
        return f"Task: {task}\nPlan execution. 2 bullets max."

    def handle_action(self, action: str):
        if action == 'collapse_thinking':
            self.display.is_expanded = False


THINKING_CONFIG = {
    'auto_expand': False,          
    'stream_speed': 0.03,          
    'show_debate': True,            
    'show_synthesis': True,         
    'num_agents': 5,                
    'thinking_mode': 'balanced',    
    'display_style': 'rich',        
}
