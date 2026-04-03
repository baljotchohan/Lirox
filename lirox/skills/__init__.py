"""
Lirox v1.0 — Skill System

Inspired by claw-code's tool architecture:
- Each skill is a self-contained unit with name, description, risk level
- Skills register themselves into a global pool
- The router picks the best skill for each query
- Users can enable/disable skills
- Developers can add custom skills by dropping a file in skills/
"""

import os
import json
import importlib
import pkgutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from pathlib import Path
from lirox.config import PROJECT_ROOT


class RiskLevel(Enum):
    SAFE = "safe"           # No side effects (LLM reasoning, code explanation)
    LOW = "low"             # Read-only (file read, web search)
    MEDIUM = "medium"       # Creates files, fetches URLs
    HIGH = "high"           # Terminal commands, file edits, destructive ops


@dataclass
class SkillResult:
    """Standard result from any skill execution."""
    success: bool
    output: str
    skill_name: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    sources: List[Dict] = field(default_factory=list)
    confidence: float = 1.0
    error: str = ""


class BaseSkill(ABC):
    """
    Base class for all Lirox skills.
    
    To create a new skill:
    1. Create a file in lirox/skills/
    2. Subclass BaseSkill
    3. Implement name, description, risk_level, keywords, execute()
    4. It auto-registers when the skills package loads
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique skill identifier (e.g., 'bash', 'file_read')."""
        ...
    
    @property
    @abstractmethod
    def description(self) -> str:
        """What this skill does, shown to user in /skills."""
        ...
    
    @property
    @abstractmethod
    def risk_level(self) -> RiskLevel:
        """Risk classification for permission checks."""
        ...
    
    @property
    @abstractmethod
    def keywords(self) -> List[str]:
        """Keywords that trigger this skill during routing."""
        ...
    
    @abstractmethod
    def execute(self, query: str, context: Dict[str, Any] = None) -> SkillResult:
        """Execute the skill with the given query."""
        ...
    
    def can_handle(self, query: str) -> Tuple[bool, float]:
        """
        Check if this skill can handle the query.
        Returns (can_handle, confidence_score).
        """
        q_lower = query.lower()
        score = 0.0
        
        for keyword in self.keywords:
            if keyword in q_lower:
                score += 1.0
        
        # Normalize
        if self.keywords:
            score = min(1.0, score / max(len(self.keywords) * 0.3, 1))
        
        return score > 0.1, score


# ─── SKILL REGISTRY ─────────────────────────────────────────────────────────

class SkillRegistry:
    """
    Global registry of available skills.
    Inspired by claw-code's ToolPool + ExecutionRegistry pattern.
    """
    
    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}
        self._enabled: Dict[str, bool] = {}
        self._config_file = os.path.join(PROJECT_ROOT, "skills_config.json")
        self._load_config()
    
    def register(self, skill: BaseSkill):
        """Register a skill in the pool."""
        self._skills[skill.name] = skill
        if skill.name not in self._enabled:
            self._enabled[skill.name] = True  # Enabled by default
    
    def get(self, name: str) -> Optional[BaseSkill]:
        """Get a skill by name."""
        return self._skills.get(name)
    
    def get_enabled(self) -> List[BaseSkill]:
        """Get all enabled skills."""
        return [s for s in self._skills.values() if self._enabled.get(s.name, True)]
    
    def get_all(self) -> List[BaseSkill]:
        """Get all registered skills."""
        return list(self._skills.values())
    
    def enable(self, name: str):
        """Enable a skill."""
        self._enabled[name] = True
        self._save_config()
    
    def disable(self, name: str):
        """Disable a skill."""
        self._enabled[name] = False
        self._save_config()
    
    def is_enabled(self, name: str) -> bool:
        return self._enabled.get(name, True)
    
    def route(self, query: str) -> Optional[BaseSkill]:
        """
        Route a query to the best matching skill.
        Returns the highest-confidence enabled skill.
        """
        best_skill = None
        best_score = 0.0
        
        for skill in self.get_enabled():
            can_handle, score = skill.can_handle(query)
            if can_handle and score > best_score:
                best_score = score
                best_skill = skill
        
        return best_skill
    
    def route_with_scores(self, query: str, limit: int = 5) -> List[Tuple[BaseSkill, float]]:
        """Route and return all matching skills with scores."""
        matches = []
        for skill in self.get_enabled():
            can_handle, score = skill.can_handle(query)
            if can_handle:
                matches.append((skill, score))
        
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:limit]
    
    def _load_config(self):
        """Load skill enable/disable state from disk."""
        if os.path.exists(self._config_file):
            try:
                with open(self._config_file, "r") as f:
                    self._enabled = json.load(f)
            except Exception:
                pass
    
    def _save_config(self):
        """Persist skill config."""
        try:
            with open(self._config_file, "w") as f:
                json.dump(self._enabled, f, indent=2)
        except Exception:
            pass
    
    def summary(self) -> str:
        """Human-readable skill pool summary."""
        lines = []
        for skill in sorted(self._skills.values(), key=lambda s: s.name):
            status = "ON" if self._enabled.get(skill.name, True) else "OFF"
            risk = skill.risk_level.value.upper()
            lines.append(f"  [{status}] {skill.name.ljust(15)} {risk.ljust(8)} {skill.description}")
        return "\n".join(lines)


# Global registry instance
registry = SkillRegistry()


def auto_discover_skills():
    """
    Auto-discover and register all skills in the lirox/skills/ directory.
    Any file ending with _skill.py that defines a class inheriting BaseSkill
    will be automatically registered.
    """
    skills_dir = Path(__file__).parent
    
    for module_info in pkgutil.iter_modules([str(skills_dir)]):
        if module_info.name.endswith("_skill"):
            try:
                module = importlib.import_module(f"lirox.skills.{module_info.name}")
                # Find all BaseSkill subclasses in the module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, BaseSkill) and 
                        attr is not BaseSkill):
                        try:
                            instance = attr()
                            registry.register(instance)
                        except Exception:
                            pass
            except Exception as e:
                pass  # Skip broken skill files silently


# Auto-discover on import
auto_discover_skills()
