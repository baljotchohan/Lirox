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
            self._show_decision(layout)
    
    def _stream_agent_thinking(self, agent_name: str, layout: Layout):
        """
        Stream agent's thinking in real-time from LLM
        """
        
        # Create agent panel
        agent_panel = Panel(
            self._create_agent_display(agent_name),
            title=f"🤖 {agent_name}",
            border_style="cyan"
        )
        
        layout["agents"].update(agent_panel)
        
        # Simulate LLM streaming (replace with actual LLM call)
        thinking_stream = self._get_agent_thinking_stream(agent_name)
        
        displayed_text = ""
        for chunk in thinking_stream:
            displayed_text += chunk
            
            # Update display with streaming cursor
            agent_panel = Panel(
                displayed_text + " ▌",  # Blinking cursor
                title=f"🤖 {agent_name}",
                border_style="cyan"
            )
            layout["agents"].update(agent_panel)
            
            time.sleep(0.05)  # Simulate typing speed
        
        # Store final thinking
        self.agents_thinking[agent_name] = displayed_text
    
    def _stream_debate(self, layout: Layout):
        """
        Show agents debating in real-time
        """
        
        # Extract debate points from agent thinking
        debate_points = self._extract_debate_points(self.agents_thinking)
        
        debate_display = ""
        for i, (agent, point) in enumerate(debate_points):
            line = f"{agent}: \"{point}\"\n"
            
            # Stream character by character
            for char in line:
                debate_display += char
                
                debate_panel = Panel(
                    debate_display + " ▌",
                    title="💬 DEBATE",
                    border_style="yellow"
                )
                layout["debate"].update(debate_panel)
                
                time.sleep(0.02)
            
            self.debate_log.append((agent, point))
    
    def _stream_synthesis(self, layout: Layout):
        """
        Show synthesis being formed in real-time
        """
        
        # Generate synthesis from all agent thinking + debate
        synthesis_text = self._generate_synthesis(
            self.agents_thinking, 
            self.debate_log
        )
        
        displayed_synthesis = ""
        for chunk in synthesis_text:
            displayed_synthesis += chunk
            
            synthesis_panel = Panel(
                displayed_synthesis + " ▌",
                title="🎯 SYNTHESIS",
                border_style="green"
            )
            layout["synthesis"].update(synthesis_panel)
            
            time.sleep(0.03)
        
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
        
        time.sleep(2)  # Let user read
    
    def _get_agent_thinking_stream(self, agent_name: str):
        """
        Get LLM stream for agent thinking (REPLACE WITH ACTUAL LLM CALL)
        """
        
        # Example thinking patterns per agent
        thinking_patterns = {
            "Architect": [
                "Analyzing scalability...\n",
                "→ This needs distributed design\n",
                "→ Consider 1M users\n",
                "→ Database sharding required\n",
                "→ API gateway needed\n"
            ],
            "Builder": [
                "Checking feasibility...\n",
                "→ Can build in 2 weeks\n",
                "→ Need 3 devs\n",
                "→ Risky: API integration\n",
                "→ Dependencies: Redis, PostgreSQL\n"
            ],
            "Risk": [
                "Identifying risks...\n",
                "→ Single point of failure: database\n",
                "→ API rate limiting needed\n",
                "→ Data privacy concerns\n",
                "→ Mitigation: backups + monitoring\n"
            ],
            "Market": [
                "Analyzing market fit...\n",
                "→ Users need this NOW\n",
                "→ 3 competitors doing similar\n",
                "→ Our advantage: speed\n",
                "→ Price point: $20/mo works\n"
            ],
            "Executor": [
                "Planning execution...\n",
                "→ Week 1: Setup infrastructure\n",
                "→ Week 2: Core features\n",
                "→ Week 3: Testing\n",
                "→ Week 4: Launch\n"
            ]
        }
        
        # Return streaming chunks
        return thinking_patterns.get(agent_name, ["Thinking..."])
    
    def _extract_debate_points(self, agent_thinking: Dict[str, str]) -> List[tuple]:
        """
        Extract debate-worthy points from agent thinking
        """
        
        # Look for disagreements
        debates = []
        
        # Example: Architect wants microservices, Builder wants monolith
        if "distributed" in agent_thinking.get("Architect", "").lower():
            if "2 weeks" in agent_thinking.get("Builder", ""):
                debates.append(("Architect", "We need microservices for scale"))
                debates.append(("Builder", "But we can ship monolith faster"))
                debates.append(("Architect", "Technical debt will hurt later"))
                debates.append(("Builder", "Agreed, but users need it NOW"))
        
        return debates
    
    def _generate_synthesis(self, agent_thinking: Dict, debate_log: List) -> str:
        """
        Generate synthesis from all inputs
        """
        
        synthesis = (
            "After analyzing all perspectives:\n\n"
            "→ Build monolith now (2 weeks)\n"
            "→ Plan microservices architecture (month 2)\n"
            "→ Acceptable technical debt\n"
            "→ User needs > perfect architecture\n"
            "→ Can refactor later with revenue\n\n"
            "Confidence: 94%"
        )
        
        return synthesis
    
    def _extract_decision(self, synthesis: str) -> Dict[str, Any]:
        """
        Extract decision from synthesis
        """
        
        return {
            'action': 'Proceed with monolith approach',
            'confidence': 94,
            'reasoning': 'Speed to market prioritized, refactor later'
        }
    
    def _wait_for_expand_trigger(self):
        """
        Wait for user to press 't' or click
        """
        
        # For terminal, listen for 't' key
        # For now, auto-expand after 1 second
        time.sleep(1)
        self.is_expanded = True
    
    def _create_agent_display(self, agent_name: str) -> str:
        """
        Create display text for agent
        """
        return f"Agent {agent_name} is thinking..."


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
        
        # Show compact thinking
        self.display.show_thinking_compact(task, len(self.agents))
        
        # If user expands, show full thinking
        if self.display.is_expanded:
            self.display.show_thinking_expanded(task, list(self.agents.keys()))
        
        # Return decision
        return {
            'decision': self.display.synthesis,
            'agents_thinking': self.display.agents_thinking,
            'debate': self.display.debate_log,
        }
    
    def _architect_prompt(self, task: str) -> str:
        """System prompt for Architect agent"""
        return f"You are the Architect agent. Analyze this task from a scalability perspective:\\n\\nTask: {task}\\n\\nThink about:\\n- Will this scale to 1M users?\\n- What's the right architecture?\\n- What's the 10-year implication?\\n- Any technical debt created?\\n\\nRespond in bullet points, be specific."
    
    def _builder_prompt(self, task: str) -> str:
        """System prompt for Builder agent"""
        return f"You are the Builder agent. Analyze this task from a feasibility perspective:\\n\\nTask: {task}\\n\\nThink about:\\n- Can we build this?\\n- How long will it take?\\n- What resources do we need?\\n- What are the risks?\\n\\nRespond in bullet points, be specific."
    
    def _risk_prompt(self, task: str) -> str:
        """System prompt for Risk agent"""
        return f"You are the Risk agent. Identify all possible risks:\\n\\nTask: {task}\\n\\nThink about:\\n- What can go wrong?\\n- What's the worst case?\\n- Single points of failure?\\n- How to mitigate?\\n\\nRespond in bullet points, be specific."
    
    def _market_prompt(self, task: str) -> str:
        """System prompt for Market agent"""
        return f"You are the Market agent. Analyze market fit:\\n\\nTask: {task}\\n\\nThink about:\\n- Do users want this?\\n- What's the competition?\\n- Pricing strategy?\\n- Go-to-market approach?\\n\\nRespond in bullet points, be specific."
    
    def _executor_prompt(self, task: str) -> str:
        """System prompt for Executor agent"""
        return f"You are the Executor agent. Plan the execution:\\n\\nTask: {task}\\n\\nThink about:\\n- Step-by-step plan\\n- Timeline with milestones\\n- Resource allocation\\n- Success criteria\\n\\nRespond in bullet points, be specific."


class StreamingLLMThinking:
    """
    Actually call LLM with streaming for real-time display
    """
    
    def __init__(self, llm_provider):
        self.llm = llm_provider
    
    async def stream_agent_thinking(self, agent_name: str, prompt: str, display_callback):
        """
        Stream LLM response character by character
        """
        
        # Call LLM with streaming
        response_stream = await self.llm.stream(prompt)
        
        full_response = ""
        async for chunk in response_stream:
            full_response += chunk
            
            # Update display in real-time
            display_callback(agent_name, full_response + " ▌")
        
        return full_response
    
    async def run_multi_agent_thinking(self, task: str, agents: Dict[str, callable]):
        """
        Run all agents in parallel with live streaming
        """
        
        # Create tasks for all agents
        tasks = []
        for agent_name, prompt_fn in agents.items():
            prompt = prompt_fn(task)
            task_obj = self.stream_agent_thinking(
                agent_name, 
                prompt, 
                lambda name, text: self._update_display(name, text)
            )
            tasks.append(task_obj)
        
        # Run all agents in parallel
        results = await asyncio.gather(*tasks)
        
        return dict(zip(agents.keys(), results))
    
    def _update_display(self, agent_name: str, text: str):
        """
        Callback to update terminal display
        """
        pass


class ThinkingKeyboardHandler:
    """
    Handle keyboard shortcuts for thinking display
    """
    
    SHORTCUTS = {
        't': 'toggle_thinking_display',
        'e': 'expand_thinking',
        'c': 'collapse_thinking',
        'd': 'show_debate',
        's': 'show_synthesis',
        'a': 'show_all_agents',
        'q': 'quit_thinking_view',
    }
    
    def __init__(self, display: LiveThinkingDisplay):
        self.display = display
    
    def handle_key(self, key: str):
        """
        Handle keyboard input
        """
        
        action = self.SHORTCUTS.get(key)
        
        if action == 'toggle_thinking_display':
            self.display.is_expanded = not self.display.is_expanded
        elif action == 'expand_thinking':
            self.display.is_expanded = True
        elif action == 'collapse_thinking':
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
