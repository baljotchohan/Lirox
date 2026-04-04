"""
Lirox v2.0 — API Rate Limiter & Resource Monitor

Prevents API abuse and monitors system resources to ensure safe autonomous execution.
"""

import time
import psutil
from typing import Dict, Optional
from datetime import datetime, timedelta
from lirox.ui.display import error_panel


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
    """Monitors CPU and RAM to prevent the agent from locking up the host."""
    
    def __init__(self, max_cpu_percent: float = 90.0, max_ram_percent: float = 85.0):
        self.max_cpu = max_cpu_percent
        self.max_ram = max_ram_percent
    
    def check_resources(self) -> bool:
        """Return True if system is healthy, False if overloaded."""
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent
        
        if cpu > self.max_cpu:
            error_panel("RESOURCE WARNING", f"CPU load critically high ({cpu}%). Pausing agent...")
            return False
            
        if ram > self.max_ram:
            error_panel("RESOURCE WARNING", f"RAM usage critically high ({ram}%). Pausing agent...")
            return False
            
        return True


# Global instances
api_limiter = RateLimiter()
sys_monitor = ResourceMonitor()
