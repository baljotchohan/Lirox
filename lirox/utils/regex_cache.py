"""Lirox v1.1 — Compiled Regex Cache

Pre-compiles and caches frequently used regex patterns so they are not
recompiled on every call.  Using a compiled pattern is typically 10-100×
faster for patterns that are matched repeatedly.
"""
from __future__ import annotations

import re
from typing import Optional

_cache: dict[tuple[str, int], re.Pattern] = {}


def get(pattern: str, flags: int = 0) -> re.Pattern:
    """Return a compiled pattern, compiling and caching on first use."""
    key = (pattern, flags)
    compiled = _cache.get(key)
    if compiled is None:
        compiled = re.compile(pattern, flags)
        _cache[key] = compiled
    return compiled


# ── Pre-compiled patterns used across the codebase ───────────────

# JSON extraction: fenced block  (```json ... ```)
JSON_FENCE = get(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)

# Shell variable assignment  (e.g. VAR=value)
SHELL_VAR_ASSIGN = get(r"^[A-Za-z_][A-Za-z0-9_]*=")

# Shell chain / pipe delimiters
SHELL_CHAIN = get(r"\s*&&\s*|\s*\|\|\s*|\s*;\s*|\s*\|\s*")
