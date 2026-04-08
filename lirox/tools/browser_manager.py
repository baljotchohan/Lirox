"""
Lirox v2.0 — Browser Manager (Async Bridge)

Provides a synchronous bridge for running async coroutines in
environments that may not have an active event loop.
"""

from __future__ import annotations

import asyncio
from typing import Any, Coroutine, Optional


class AsyncBridge:
    """
    Runs async coroutines synchronously with optional timeout.

    Usage:
        bridge = AsyncBridge(timeout=30)
        result = bridge.run(some_coroutine())
    """

    def __init__(self, timeout: float = 30.0):
        self.default_timeout = timeout

    def run(self, coro: Coroutine, timeout: Optional[float] = None) -> Any:
        """
        Execute an async coroutine synchronously.

        Args:
            coro: The coroutine to run.
            timeout: Seconds before raising TimeoutError.
                     Defaults to the bridge's default_timeout.

        Returns:
            The coroutine's return value.

        Raises:
            TimeoutError: If the coroutine exceeds the timeout.
            Any exception raised inside the coroutine.
        """
        effective_timeout = timeout if timeout is not None else self.default_timeout

        async def _run_with_timeout():
            return await asyncio.wait_for(coro, timeout=effective_timeout)

        try:
            # Try to get the running loop (in case we're already in async context)
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside a running loop — use a new thread-based loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, _run_with_timeout())
                    return future.result()
            else:
                return loop.run_until_complete(_run_with_timeout())
        except asyncio.TimeoutError as e:
            raise TimeoutError(
                f"Async operation timed out after {effective_timeout}s"
            ) from e
