"""Base Agent Protocol — all agents implement this."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any, Generator

from lirox.memory.manager import MemoryManager
from lirox.thinking.scratchpad import Scratchpad

AgentEvent = Dict[str, Any]


class BaseAgent(ABC):
    def __init__(self, memory: MemoryManager = None, scratchpad: Scratchpad = None):
        self.memory = memory or MemoryManager()
        self.scratchpad = scratchpad or Scratchpad()

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    def run(
        self, query: str, system_prompt: str = "", context: str = ""
    ) -> Generator[AgentEvent, None, None]: ...
