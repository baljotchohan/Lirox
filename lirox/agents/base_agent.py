"""Base Agent — all agents implement this."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any, Generator
from lirox.memory.manager import MemoryManager

AgentEvent = Dict[str, Any]


class BaseAgent(ABC):
    def __init__(self, memory: MemoryManager = None, profile_data: Dict[str, Any] = None):
        self.memory       = memory or MemoryManager(agent_name="base")
        self.profile_data = profile_data or {}
        
        # Lirox Unicorn Phase 1: Cryptographic Identity
        from lirox.agents.agent_manager import AgentManager
        # We use a safe property getter or fallback if name is not accessible yet
        _agent_name = getattr(self.__class__, 'name', getattr(self, '__class__').__name__.lower())
        if isinstance(_agent_name, property):
            # Fallback for abstract property before subclass init finishes
            _agent_name = self.__class__.__name__.lower()
            
        try:
            self._identity = AgentManager().create_or_load_identity(_agent_name)
        except Exception as e:
            # Fallback for systems lacking cryptography library during early boot
            import logging
            logging.getLogger("lirox.agents").warning("Could not initialize AgentIdentity: %s", e)
            self._identity = None

    @property
    def identity(self):
        """Returns the cryptographic identity of this agent."""
        return self._identity

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def run(self, query: str, system_prompt: str = "",
            context: str = "", mode: str = "auto") -> Generator[AgentEvent, None, None]: ...
