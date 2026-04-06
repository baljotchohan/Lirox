"""
Lirox — API Rate Limiter & Resource Monitor

Prevents API abuse and monitors system resources to ensure safe autonomous execution.
BUG-17 FIX: ResourceMonitor uses polling via check_resources() only (no background thread).
If a background monitor thread is ever needed, use threading.Event() stop flag.
"""

import time
import psutil
from typing import Dict
from datetime import datetime, timedelta


class RateLimiter:
    """Sliding-window rate limiter per provider."""

    def __init__(self):
        self.call_history: Dict[str, list] = {}  # {provider: [timestamps]}
        self.limits: Dict[str, int] = {
            "openai": 55,       # calls per minute
            "gemini": 55,
            "groq": 28,
            "anthropic": 45,
            "openrouter": 55,
            "deepseek": 55,
            "nvidia": 55,
            "default": 30,
        }

    def is_allowed(self, provider: str) -> bool:
        now = datetime.now()
        cutoff = now - timedelta(seconds=60)
        history = self.call_history.get(provider, [])
        # Prune old entries
        history = [ts for ts in history if ts > cutoff]
        self.call_history[provider] = history
        limit = self.limits.get(provider, self.limits["default"])
        return len(history) < limit

    def record_call(self, provider: str) -> None:
        if provider not in self.call_history:
            self.call_history[provider] = []
        self.call_history[provider].append(datetime.now())
        # Global cleanup: prune all providers older than 2 min
        cutoff = datetime.now() - timedelta(minutes=2)
        for key in list(self.call_history.keys()):
            self.call_history[key] = [
                ts for ts in self.call_history[key] if ts > cutoff
            ]


class ResourceMonitor:
    """
    Monitors CPU and RAM to prevent the agent from locking up the host.

    Thresholds are intentionally high (95% RAM, 95% CPU) because Ollama
    local models are large and will naturally consume significant RAM.
    The monitor logs a warning but NEVER blocks execution — the agent
    should always proceed even under high memory pressure.
    """

    def __init__(self, max_cpu_percent: float = 95.0, max_ram_percent: float = 95.0):
        self.max_cpu = max_cpu_percent
        self.max_ram = max_ram_percent
        self._warn_interval = 60  # seconds between repeated warnings
        self._last_warn_time = 0.0

    def check_resources(self) -> bool:
        """
        Always returns True (non-blocking). Logs a single warning if thresholds
        are exceeded, but does not pause or stall the agent.
        """
        import gc
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent

        now = time.time()
        if (cpu > self.max_cpu or ram > self.max_ram):
            if now - self._last_warn_time > self._warn_interval:
                label = "CPU" if cpu > self.max_cpu else "RAM"
                val = cpu if cpu > self.max_cpu else ram
                # Soft warning only — do not block
                import logging
                logging.getLogger("lirox.resources").warning(
                    f"{label} pressure high ({val:.0f}%) — running GC"
                )
                gc.collect()  # run garbage collector to free unreferenced objects
                self._last_warn_time = now

        return True  # always non-blocking


# Global instances
api_limiter = RateLimiter()
sys_monitor = ResourceMonitor()
