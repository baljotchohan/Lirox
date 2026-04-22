"""Lirox v1.0 — Learning Package

Public API for Lirox's self-learning system.
Wraps the internal mind/trainer and mind/learnings modules
and optionally persists facts to the SQLite database.
"""
from lirox.learning.manager import LearningManager
from lirox.learning.extractor import FactExtractor, ExtractedKnowledge

__all__ = [
    "LearningManager",
    "FactExtractor",
    "ExtractedKnowledge",
]
