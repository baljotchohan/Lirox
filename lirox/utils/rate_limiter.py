"""
Lirox v0.6 — API Rate Limiter & Resource Monitor

Prevents API abuse and monitors system resources to ensure safe autonomous execution.
"""

import time
import psutil
from typing import Dict, Optional
from datetime import datetime, timedelta
from lirox.ui.display import error_panel


class RateLimiter:
    """Rate limit requests per provider and domain."""
    
    def __init__(self):
        self.call_history: Dict[str, list] = {}  # {key: [timestamps]}
        self.limits: Dict[str, int] = {
            "openai": 3500,      # tokens per minute
            "gemini": 10000,
            "groq": 25000,
            "anthropic": 50000,
            "default": 5000
        }
    
    def is_allowed(self, provider: str, tokens: int = 100) -> bool:
        """Check if request is allowed under rate limits."""
        key = f"{provider}_{datetime.now().minute}"
        if key not in self.call_history:
            self.call_history[key] = []
        
        # Clean old entries (older than 1 minute)
        cutoff = datetime.now() - timedelta(minutes=1)
        self.call_history[key] = [
            ts for ts in self.call_history[key]
            if ts > cutoff
        ]
        
        limit = self.limits.get(provider, self.limits["default"])
        total_tokens = sum(1 for _ in self.call_history[key]) * tokens
        
        return total_tokens < limit
    
    def record_call(self, provider: str) -> None:
        """Record a provider call."""
        key = f"{provider}_{datetime.now().minute}"
        if key not in self.call_history:
            self.call_history[key] = []
        self.call_history[key].append(datetime.now())


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
