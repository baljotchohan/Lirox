"""
Lirox v2.0 — Browser CDP Bridge

Chrome DevTools Protocol (CDP) communication primitives.
"""

from __future__ import annotations

from typing import Any, Dict


class CDPError(Exception):
    """
    Exception raised when a CDP command returns an error response.

    Attributes:
        code:   CDP error code (int).
        message: Human-readable error description.
        method: CDP method that caused the error (empty string if unknown).
        params: Parameters that were sent with the command.
    """

    def __init__(
        self,
        code: int,
        message: str,
        method: str = "",
        params: Dict[str, Any] = None,
    ):
        self.code    = code
        self.message = message
        self.method  = method
        self.params  = params or {}
        super().__init__(self._format())

    def _format(self) -> str:
        parts = [f"CDPError({self.code}): {self.message}"]
        if self.method:
            parts.append(f"method={self.method}")
        return " | ".join(parts)

    def __str__(self) -> str:
        return self._format()
