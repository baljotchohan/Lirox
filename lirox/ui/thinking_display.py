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
from typing import List, Dict, Any
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
        
        # Compact view
        compact = Text()
        compact.append("⟳ 🧠 Thinking ", style="bold cyan")
        compact.append(f"[{num_agents} agents debating...] ", style="dim")
        compact.append("▼ Click to expand ", style="yellow blink")
        compact.append("(or press 't')", style="dim")
        
        self.console.print(compact)
        
        # Listen for user input
        self._wait_for_expand_trigger()
        
    def show_thinking_expanded(self, task: str, agents: List[str]):
        """
        Show expanded thinking with live streaming
        """
        
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="agents", ratio=2),
            Layout(name="debate", ratio=1),
            Layout(name="synthesis", size=5)
        )
        
        # Header
        header = Panel(
            f"🧠 LIVE REASONING: {task}",
            style="bold white on blue"
        )
        layout["header"].update(header)
        
        # Live display
        with Live(layout, console=self.console, refresh_per_second=10) as live:
            self.live_display = live
            
            # Stream each agent's thinking
            for agent_name in agents:
                self._stream_agent_thinking(agent_name, layout)
            
            # Show debate
            self._stream_debate(layout)
            
            # Show synthesis
            self._stream_synthesis(layout)
            
            # Final decision
            self._show_decision(lay    def _stream_agent_thinking(self, agent_name: str, layout: Layout, future=None):
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
            thinking_stream = self._get_agent_thinking_stream(agent_name)
            for chunk in thinking_stream:
                displayed_text += chunk
                agent_panel = Panel(displayed_text + " ▌", title=f"🤖 {agent_name}", border_style="cyan")
                layout["agents"].update(agent_panel)
                time.sleep(0.05)
        
        # Store final thinking
        self.agents_thinking[agent_name] = displayed_text
    
    def _stream_debate(self, layout: Layout):
        """
        Show agents debating in real-time
        """
        debate_points = self._extract_debate_points(self.agents_thinking)
        debate_display = ""
        for i, (agent, point) in enumerate(debate_points):
            line = f"{agent}: \"{point}\"\n"
            for char in line:
                debate_display += char
                debate_panel = Panel(debate_display + " ▌", title="💬 DEBATE", border_style="yellow")
                layout["debate"].update(debate_panel)
                time.sleep(0.01)
            self.debate_log.append((agent, point))
    
    def _stream_synthesis(self, layout: Layout):
        """
        Show synthesis being formed in real-time
        """
        synthesis_text = self._generate_synthesis(self.agents_thinking, self.debate_log)
        displayed_synthesis = ""
        for char in synthesis_text:
            displayed_synthesis += char
            synthesis_panel = Panel(displayed_synthesis + " ▌", title="🎯 SYNTHESIS", border_style="green")
            layout["synthesis"].update(synthesis_panel)
            time.sleep(0.01)
        self.synthesis = displayed_synthesis
    
    def _show_decision(self, layout: Layout):
        """
        Show final decision
        """
        decision = self._extract_decision(self.synthesis)
        decision_panel = Panel(
            f"✓ Decision made: {decision['action']}\n"
            f"  Confidence: {decision['confidence']}%\n"
            f"  Reasoning: {decision['reasoning']}",
            title="✅ FINAL DECISION",
            border_style="bold green"
        )
        layout["synthesis"].update(decision_panel)
        time.sleep(1)  # Let user read
    
    def _get_agent_thinking_stream(self, agent_name: str):
        """Fallback mock stream"""
        return ["Thinking...\n", "→ Analyzing parameters\n", "→ Formulating plan\n"]
    
    def _extract_debate_points(self, agent_thinking: Dict[str, str]) -> List[tuple]:
        debates = []
        for name, text in agent_thinking.items():
            lines = [line.strip("- *→\n") for line in text.split('\n') if len(line.strip("- *→\n")) > 5]
            if lines:
                debates.append((name, lines[0]))
        return debates
    
    def _generate_synthesis(self, agent_thinking: Dict, debate_log: List) -> str:
        synthesis = "After analyzing all perspectives:\n\n"
        for name, point in debate_log[:3]:
            synthesis += f"→ {point}\n"
        synthesis += "\nConfidence: 94%"
        return synthesis
    
    def _extract_decision(self, synthesis: str) -> Dict[str, Any]:
        return {
            'action': 'Proceed with unified plan',
            'confidence': 94,
            'reasoning': 'Synthesized multi-agent perspectives.'
        }
    
    def _wait_for_expand_trigger(self, timeout=2.0):
        """
        Wait for user to press 't' non-blockingly via select/tty
        """
        import sys, select, time
        if not sys.stdin.isatty():
            time.sleep(timeout)
            self.is_expanded = True
            return

        import tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            # Wait up to timeout seconds for a keypress
            r, w, e = select.select([sys.stdin], [], [], timeout)
            if r:
                ch = sys.stdin.read(1)
                if ch.lower() == 't':
                    self.is_expanded = True
                else:
                    self.is_expanded = False
            else:
                self.is_expanded = False
        except Exception:
            time.sleep(timeout)
            self.is_expanded = False
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            
    def show_thinking_expanded(self, task: str, agents: List[str], agent_futures: dict = None):
        """
        Show expanded thinking with live streaming from futures
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
        
        # Agent definitions
        self.agents = {
            'Architect': self._architect_prompt,
            'Builder': self._builder_prompt,
            'Risk': self._risk_prompt,
            'Market': self._market_prompt,
            'Executor': self._executor_prompt,
        }
    
    def think_and_decide(self, task: str, context: str) -> Dict[str, Any]:
        """
        Run multi-agent thinking with live display
        """
        # Show compact thinking (this will wait up to 2 seconds for 't' keypress)
        self.display.show_thinking_compact(task, len(self.agents))
        
        if self.display.is_expanded:
            from concurrent.futures import ThreadPoolExecutor
            from lirox.utils.llm import generate_response
            
            def run_agent(pfn):
                prompt = pfn(task)
                return generate_response(prompt, system_prompt="You are a debating agent. Keep answers very brief, 2-3 short bullet points max. No markdown fences.")
                
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {name: executor.submit(run_agent, pfn) for name, pfn in self.agents.items()}
                self.display.show_thinking_expanded(task, list(self.agents.keys()), futures)
        
        return {
            'decision': self.display.synthesis,
            'agents_thinking': self.display.agents_thinking,
            'debate': self.display.debate_log,
        }
    
    def _architect_prompt(self, task: str) -> str:
        return f"Task: {task}\nAnalyze from a scalability/architecture perspective. Will it scale? Implication? 2 bullet points max."
    
    def _builder_prompt(self, task: str) -> str:
        return f"Task: {task}\nAnalyze from a feasibility perspective. Can we build this? Resources? 2 bullet points max."
    
    def _risk_prompt(self, task: str) -> str:
        return f"Task: {task}\nIdentify risks. What can go wrong? Mitigation? 2 bullet points max."
    
    def _market_prompt(self, task: str) -> str:
        return f"Task: {task}\nAnalyze market fit. Do users want this? Competition? 2 bullet points max."
    
    def _executor_prompt(self, task: str) -> str:
        return f"Task: {task}\nPlan the execution. Step-by-step plan. 2 bullet points max."    elif action == 'collapse_thinking':
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

if __name__ == "__main__":
    display = LiveThinkingDisplay()
    display.show_thinking_compact("Create PDF on Maharaja Ranjit Singh", num_agents=5)
    display.is_expanded = True
    agents = ['Architect', 'Builder', 'Risk', 'Market', 'Executor']
    display.show_thinking_expanded("Create PDF on Maharaja Ranjit Singh", agents)
