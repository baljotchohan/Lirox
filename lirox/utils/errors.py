"""
Lirox v1.1 — Error Handling & Recovery Framework

Provides base exceptions, retryable error detection, and retry utilities
used across all agent components (executor, browser, file_io, etc.).
"""

import time
import functools


# ─── Base Exceptions ──────────────────────────────────────────────────────────

class LiroxError(Exception):
    """Base exception for all Lirox errors."""
    pass


class ToolExecutionError(LiroxError):
    """Raised when a tool (terminal, browser, file_io) fails."""
    def __init__(self, tool_name, error, is_retryable=False):
        self.tool_name = tool_name
        self.error = error
        self.is_retryable = is_retryable
        super().__init__(f"[{tool_name}] {error}")


class PlanExecutionError(LiroxError):
    """Raised when plan-level execution fails."""
    def __init__(self, step_id, message):
        self.step_id = step_id
        super().__init__(f"Step {step_id}: {message}")


class PlanValidationError(LiroxError):
    """Raised when a plan dict has invalid structure."""
    pass


# ─── Browser-Specific Errors (v2.0) ──────────────────────────────────────────

from enum import Enum

class BrowserErrorType(Enum):
    """Categorize browser errors for proper recovery routing."""
    NAVIGATION_FAILED = "navigation_failed"
    SELECTOR_NOT_FOUND = "selector_not_found"
    TIMEOUT = "timeout"
    JAVASCRIPT_ERROR = "javascript_error"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    NETWORK_ERROR = "network_error"
    BROWSER_CRASHED = "browser_crashed"
    SESSION_ENDED = "session_ended"
    INVALID_INPUT = "invalid_input"


class BrowserException(LiroxError):
    """Base exception for all browser operations."""
    def __init__(self, error_type: BrowserErrorType, message: str, url: str = None):
        self.error_type = error_type
        self.message = message
        self.url = url
        self.is_retryable = error_type in (
            BrowserErrorType.TIMEOUT,
            BrowserErrorType.NETWORK_ERROR,
            BrowserErrorType.BROWSER_CRASHED,
            BrowserErrorType.SESSION_ENDED,
        )
        super().__init__(f"[{error_type.value}] {message}")


class NavigationError(BrowserException):
    """Raised when navigation fails or times out."""
    def __init__(self, url: str, reason: str, http_status: int = None):
        super().__init__(BrowserErrorType.NAVIGATION_FAILED, reason, url)
        self.http_status = http_status


class BrowserTimeoutError(BrowserException):
    """Raised when browser fetching times out."""
    def __init__(self, operation: str, url: str):
        super().__init__(BrowserErrorType.TIMEOUT, f"Timeout during {operation}", url)



class SelectorError(BrowserException):
    """Raised when CSS/XPath selector not found."""
    def __init__(self, selector: str, waited: bool = False):
        reason = f"Selector not found: {selector}"
        if waited:
            reason += " (waited and timed out)"
        super().__init__(BrowserErrorType.SELECTOR_NOT_FOUND, reason)
        self.selector = selector


class JavaScriptError(BrowserException):
    """Raised when JavaScript evaluation fails."""
    def __init__(self, script_preview: str, error: str):
        super().__init__(BrowserErrorType.JAVASCRIPT_ERROR, error)
        self.script_preview = script_preview[:200]


class BrowserCrashError(BrowserException):
    """Raised when browser process crashes."""
    def __init__(self, session_id: str):
        super().__init__(
            BrowserErrorType.BROWSER_CRASHED,
            f"Browser crashed for session {session_id}"
        )
        self.session_id = session_id


class DataValidationError(LiroxError):
    """Raised when extracted data fails validation."""
    pass


# ─── Retry Logic ──────────────────────────────────────────────────────────────

# Patterns that indicate a transient, retryable failure
RETRYABLE_PATTERNS = [
    "timeout",
    "timed out",
    "rate limit",
    "rate_limit",
    "429",
    "503",
    "connection",
    "temporary",
    "temporarily",
    "try again",
    "server error",
    "internal server error",
]


def should_retry(error):
    """
    Determine if an error is transient and worth retrying.
    Checks both the error message and ToolExecutionError.is_retryable flag.
    """
    if isinstance(error, ToolExecutionError) and error.is_retryable:
        return True

    error_str = str(error).lower()
    return any(pattern in error_str for pattern in RETRYABLE_PATTERNS)


def with_retry(func, max_retries=3, backoff=1.0):
    """
    Execute a function with exponential backoff retry on transient errors.
    
    Args:
        func: Callable to execute (no args — use lambda/partial if needed)
        max_retries: Maximum number of retry attempts
        backoff: Base backoff time in seconds (doubles each retry)
    
    Returns:
        The function's return value on success
    
    Raises:
        The last exception if all retries are exhausted or error is non-retryable
    """
    last_error = None
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_error = e
            if not should_retry(e) or attempt == max_retries - 1:
                raise
            wait_time = backoff * (2 ** attempt)
            time.sleep(wait_time)
    raise last_error  # Should not reach here, but safety net


def retry_decorator(max_retries=3, backoff=1.0):
    """
    Decorator version of with_retry for cleaner usage on methods.
    
    Usage:
        @retry_decorator(max_retries=3)
        def my_flaky_function(self, arg):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return with_retry(
                lambda: func(*args, **kwargs),
                max_retries=max_retries,
                backoff=backoff
            )
        return wrapper
    return decorator
