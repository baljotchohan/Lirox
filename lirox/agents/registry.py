"""Agent Registry.

Dynamically registers and loads available agents.
"""
from typing import Dict, Type, Any, Optional

class AgentRegistry:
    """Registry for looking up available agents."""
    
    _agents: Dict[str, Type] = {}
    
    @classmethod
    def register(cls, name: str, agent_class: Type) -> None:
        """Register an agent class by name."""
        cls._agents[name.lower()] = agent_class
        
    @classmethod
    def get_agent_class(cls, name: str) -> Optional[Type]:
        """Get an agent class by name."""
        return cls._agents.get(name.lower())
        
    @classmethod
    def list_agents(cls) -> list[str]:
        """List registered agent names."""
        return list(cls._agents.keys())

def register_agent(name: str):
    """Decorator to register an agent."""
    def decorator(cls):
        AgentRegistry.register(name, cls)
        return cls
    return decorator
