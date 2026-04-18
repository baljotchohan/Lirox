"""Lirox v3.0 — Managed Thread Pool

A drop-in replacement for ``concurrent.futures.ThreadPoolExecutor`` that:
- Shuts down with ``wait=True`` so in-flight work is completed before the
  process exits (prevents resource / memory leaks on shutdown).
- Exposes explicit ``start()`` / ``stop()`` lifecycle helpers.
- Tracks whether the pool is still active so callers can guard submissions.
"""
from __future__ import annotations

import atexit
import concurrent.futures
import logging
import threading
from typing import Any, Callable, Optional

_logger = logging.getLogger("lirox.managed_pool")


class ManagedPool:
    """Thread pool with a safe lifecycle (no wait=False leaks)."""

    def __init__(self, max_workers: int = 5, name: str = "lirox-pool") -> None:
        self._max_workers = max_workers
        self._name = name
        self._lock = threading.Lock()
        self._pool: Optional[concurrent.futures.ThreadPoolExecutor] = None
        self._active = False
        self.start()
        atexit.register(self.stop)

    # ── Lifecycle ────────────────────────────────────────────────

    def start(self) -> None:
        with self._lock:
            if self._active:
                return
            self._pool = concurrent.futures.ThreadPoolExecutor(
                max_workers=self._max_workers,
                thread_name_prefix=self._name,
            )
            self._active = True
            _logger.debug("ManagedPool '%s' started (workers=%d)", self._name, self._max_workers)

    def stop(self, timeout: Optional[float] = None) -> None:
        """Shut down the pool, waiting for in-flight tasks to complete."""
        with self._lock:
            if not self._active or self._pool is None:
                return
            # Mark inactive while still holding the lock so concurrent
            # submit() calls will see _active=False and restart a fresh pool
            # rather than submitting to a pool that is shutting down.
            self._active = False
            pool = self._pool
            self._pool = None

        try:
            # wait=True ensures we don't leak threads / memory
            pool.shutdown(wait=True)
            _logger.debug("ManagedPool '%s' stopped cleanly", self._name)
        except Exception as exc:
            _logger.warning("ManagedPool '%s' shutdown error: %s", self._name, exc)

    # ── Public interface ─────────────────────────────────────────

    def submit(self, fn: Callable, *args: Any, **kwargs: Any) -> concurrent.futures.Future:
        """Submit *fn* for execution. Restarts the pool if it was stopped."""
        with self._lock:
            if not self._active:
                # Auto-restart if someone submits after a stop (e.g. in tests)
                self._pool = concurrent.futures.ThreadPoolExecutor(
                    max_workers=self._max_workers,
                    thread_name_prefix=self._name,
                )
                self._active = True
            return self._pool.submit(fn, *args, **kwargs)

    @property
    def active(self) -> bool:
        return self._active


# Module-level singleton used by llm.py
_default_pool: Optional[ManagedPool] = None
_pool_lock = threading.Lock()


def get_default_pool() -> ManagedPool:
    global _default_pool
    with _pool_lock:
        if _default_pool is None or not _default_pool.active:
            _default_pool = ManagedPool(max_workers=5, name="lirox-fallback")
    return _default_pool
