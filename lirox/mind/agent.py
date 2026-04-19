"""Lirox v1.1 — Mind module singletons."""
from __future__ import annotations
import threading

from lirox.mind.soul import LivingSoul
from lirox.mind.learnings import LearningsStore

_singleton_lock = threading.Lock()
_soul: LivingSoul = None
_learnings: LearningsStore = None


def get_soul() -> LivingSoul:
    global _soul
    if _soul is None:  # fast path — avoids lock acquisition once initialised
        with _singleton_lock:
            if _soul is None:  # second check while holding the lock
                _soul = LivingSoul()
    return _soul


def get_learnings() -> LearningsStore:
    global _learnings
    if _learnings is None:  # fast path — avoids lock acquisition once initialised
        with _singleton_lock:
            if _learnings is None:  # second check while holding the lock
                _learnings = LearningsStore()
    return _learnings
