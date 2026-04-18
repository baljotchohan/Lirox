"""Lirox v3.0 — Mind module singletons (simplified)."""
from __future__ import annotations
import threading

from lirox.mind.soul import LivingSoul
from lirox.mind.learnings import LearningsStore

_singleton_lock = threading.Lock()
_soul: LivingSoul = None
_learnings: LearningsStore = None


def get_soul() -> LivingSoul:
    global _soul
    with _singleton_lock:
        if _soul is None:
            _soul = LivingSoul()
    return _soul


def get_learnings() -> LearningsStore:
    global _learnings
    with _singleton_lock:
        if _learnings is None:
            _learnings = LearningsStore()
    return _learnings
