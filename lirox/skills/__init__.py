"""
Lirox v2.0 — Skills System

Skills are modular capabilities the agent can use. This package provides:
  - BaseSkill: Abstract base class for all skills
  - SkillRegistry: Manages skill registration, routing, enable/disable
  - A default `registry` instance pre-loaded with built-in skills
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple


# ─── Base Skill ───────────────────────────────────────────────────────────────

class BaseSkill(ABC):
    """Abstract base class for all Lirox skills."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique skill identifier (lowercase, no spaces)."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this skill does."""
        ...

    @property
    @abstractmethod
    def keywords(self) -> List[str]:
        """Keywords used to route queries to this skill."""
        ...

    @abstractmethod
    def run(self, query: str, context: dict = None) -> str:
        """Execute the skill with the given query."""
        ...

    def score(self, query: str) -> float:
        """Return a relevance score for this skill given the query."""
        text = query.lower()
        matches = sum(1 for kw in self.keywords if kw in text)
        return matches / max(len(self.keywords), 1)


# ─── Skill Registry ───────────────────────────────────────────────────────────

class SkillRegistry:
    """Manages skill registration, routing, and enable/disable state."""

    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}
        self._enabled: Dict[str, bool] = {}

    def register(self, skill: BaseSkill) -> None:
        """Register a skill."""
        self._skills[skill.name] = skill
        self._enabled[skill.name] = True

    def get(self, name: str) -> Optional[BaseSkill]:
        """Get a skill by name."""
        return self._skills.get(name)

    def get_all(self) -> List[BaseSkill]:
        """Return all registered skills."""
        return list(self._skills.values())

    def get_enabled(self) -> List[BaseSkill]:
        """Return all currently enabled skills."""
        return [s for name, s in self._skills.items() if self._enabled.get(name, True)]

    def enable(self, name: str) -> None:
        """Enable a skill by name."""
        if name in self._skills:
            self._enabled[name] = True

    def disable(self, name: str) -> None:
        """Disable a skill by name."""
        if name in self._skills:
            self._enabled[name] = False

    def is_enabled(self, name: str) -> bool:
        """Check if a skill is enabled."""
        return self._enabled.get(name, False)

    def route(self, query: str) -> Optional[BaseSkill]:
        """Route a query to the best matching enabled skill."""
        best_skill = None
        best_score = 0.0
        for skill in self.get_enabled():
            s = skill.score(query)
            if s > best_score:
                best_score = s
                best_skill = skill
        return best_skill if best_score > 0 else None

    def route_with_scores(self, query: str) -> List[Tuple[float, BaseSkill]]:
        """Return list of (score, skill) tuples for all enabled skills, sorted desc."""
        scored = []
        for skill in self.get_enabled():
            s = skill.score(query)
            if s > 0:
                scored.append((s, skill))
        return sorted(scored, key=lambda x: x[0], reverse=True)

    def summary(self) -> str:
        """Return a summary string of all registered skills."""
        if not self._skills:
            return "No skills registered."
        lines = ["Registered Skills:"]
        for name, skill in self._skills.items():
            status = "enabled" if self._enabled.get(name, True) else "disabled"
            lines.append(f"  • {name} ({status}): {skill.description}")
        return "\n".join(lines)


# ─── Auto-Discovery & Default Registry ───────────────────────────────────────

def _auto_discover() -> SkillRegistry:
    """Create a registry pre-loaded with all built-in skills."""
    reg = SkillRegistry()
    try:
        from lirox.skills.bash_skill import BashSkill
        reg.register(BashSkill())
    except Exception:
        pass
    return reg


# Module-level default registry (auto-populated)
registry: SkillRegistry = _auto_discover()

__all__ = ["BaseSkill", "SkillRegistry", "registry"]
