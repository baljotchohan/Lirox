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

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def run(self, query: str, system_prompt: str = "",
            context: str = "", mode: str = "auto") -> Generator[AgentEvent, None, None]: ...
