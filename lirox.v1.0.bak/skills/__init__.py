"""
Lirox v1.0.0 — Skills Package

Skills are Python modules in data/mind/skills/ managed by SkillsRegistry.
Use /add-skill to create skills, /skills to list them.

BUG-10 FIX: Removed auto-discover at import time. bash_skill.py has been
deleted; importing from lirox.skills no longer triggers BashSkill loading.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any


class BaseSkill(ABC):
    """Abstract base class for user-defined skills."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def keywords(self) -> List[str]: ...

    @abstractmethod
    def run(self, query: str, context: dict = None) -> str: ...

    def score(self, query: str) -> float:
        text    = query.lower()
        matches = sum(1 for kw in self.keywords if kw in text)
        return matches / max(len(self.keywords), 1)


__all__ = ["BaseSkill"]
