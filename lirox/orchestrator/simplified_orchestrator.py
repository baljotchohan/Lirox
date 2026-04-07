"""Simplified Lirox — 2 Agents Only: Research + Code"""
from enum import Enum
from typing import Dict, Any, Generator

class SimpleAgentType(Enum):
    RESEARCH = "research"  # Web search, analysis
    CODE = "code"          # Write, debug, execute, desktop control
    CHAT = "chat"          # Default conversation


class SimplifiedOrchestrator:
    """Minimal orchestrator: just Research, Code, and Chat."""
    
    def __init__(self, profile_data: Dict[str, Any] = None):
        self.profile_data = profile_data or {}
        self.current_agent = SimpleAgentType.CHAT
        self.session_memory = {}
    
    def set_agent(self, agent_name: str) -> bool:
        """Only allow 3 agents."""
        mapping = {
            "research": SimpleAgentType.RESEARCH,
            "code": SimpleAgentType.CODE,
            "chat": SimpleAgentType.CHAT,
        }
        if agent_name.lower() in mapping:
            self.current_agent = mapping[agent_name.lower()]
            return True
        return False
    
    def classify_intent(self, query: str) -> SimpleAgentType:
        """Simpler intent detection — only 2 specialists + chat."""
        q = query.lower()
        
        # Code intent signals
        code_signals = [
            "write", "create", "build", "fix", "debug", "run", "execute",
            "open", "click", "screenshot", "desktop", "terminal",
            "code", "script", "python", "javascript", "file",
        ]
        
        # Research intent signals  
        research_signals = [
            "search", "find", "research", "look up", "investigate",
            "what is", "who is", "trending", "news", "information",
        ]
        
        # Check for code intent
        if any(sig in q for sig in code_signals):
            return SimpleAgentType.CODE
        
        # Check for research intent
        if any(sig in q for sig in research_signals):
            return SimpleAgentType.RESEARCH
        
        # Default to chat
        return SimpleAgentType.CHAT
    
    def run(self, query: str, agent_override: str = None) -> Generator:
        """Run query with appropriate agent."""
        
        # Determine agent
        if agent_override:
            if not self.set_agent(agent_override):
                yield {"type": "error", "message": f"Unknown agent: {agent_override}"}
                return
            agent_type = self.current_agent
        else:
            agent_type = self.classify_intent(query)
        
        # Route to agent
        if agent_type == SimpleAgentType.CODE:
            yield {"type": "agent_start", "agent": "code"}
            # Call code agent...
        elif agent_type == SimpleAgentType.RESEARCH:
            yield {"type": "agent_start", "agent": "research"}
            # Call research agent...
        else:
            yield {"type": "agent_start", "agent": "chat"}
            # Direct LLM response
