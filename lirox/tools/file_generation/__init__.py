"""lirox.tools.file_generation

Production-grade file generation engine with real design thinking.

Components:
- DesignEngine: Topic-aware design strategy system
- ContentStrategist: Rich, audience-aware content generator
"""
from lirox.tools.file_generation.design_engine import DesignEngine, DesignPlan
from lirox.tools.file_generation.content_strategist import ContentStrategist

__all__ = ["DesignEngine", "DesignPlan", "ContentStrategist"]
