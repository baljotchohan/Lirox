"""
Lirox v0.6 — API Rate Limiter & Resource Monitor

Prevents API abuse and monitors system resources to ensure safe autonomous execution.
"""

import time
import psutil
from typing import Dict
from lirox.ui.display import error_panel


class RateLimiter:
    """Tracks API calls to prevent rate limits and ballooning costs."""
    
    def __init__(self, rpm_limit: int = 50, rpd_limit: int = 500):
        self.rpm_limit = rpm_limit
        self.rpd_limit = rpd_limit
        self.calls: Dict[int, int] = {}  # timestamp -> count
        self.total_today = 0
        self.last_reset = time.time()
    
    def _cleanup_old_calls(self):
        """Remove calls older than 60 seconds."""
        current = time.time()
        self.calls = {t: c for t, c in self.calls.items() if current - t < 60}
        
        # Reset daily limit if 24h passed
        if current - self.last_reset > 86400:
            self.total_today = 0
            self.last_reset = current
    
    def check_limit(self) -> bool:
        """Check if we can make an API call."""
        self._cleanup_old_calls()
        
        calls_last_minute = sum(self.calls.values())
        
        if calls_last_minute >= self.rpm_limit:
            error_panel("RATE LIMIT (RPM)", f"Exceeded {self.rpm_limit} requests per minute. Pausing...")
            return False
            
        if self.total_today >= self.rpd_limit:
            error_panel("RATE LIMIT (RPD)", f"Exceeded {self.rpd_limit} requests per day. Safety stop.")
            return False
            
        return True
    
    def record_call(self):
        """Record an API call."""
        current = int(time.time())
        self.calls[current] = self.calls.get(current, 0) + 1
        self.total_today += 1
    
    def wait_if_needed(self):
        """Block execution until a call is permitted."""
        while not self.check_limit():
            if self.total_today >= self.rpd_limit:
                raise Exception(f"Daily rate limit of {self.rpd_limit} reached.")
            time.sleep(5)


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
