"""Lirox v1.1 — Robust LLM JSON Extraction

Root-cause fix (C-02): the previous implementation had an O(n²) bracket-
matching loop — for every '{' in the input it restarted a full scan of the
remaining text.  This allows a malicious or malformed LLM response to cause
quadratic CPU usage (DoS).

This module provides:
    extract_json(text)  — O(n) single-pass scanner with hard input limits.

Design goals
------------
1. **O(n) time** — single pass over the input; no nested restarts.
2. **DoS protection** — hard cap on input length before scanning begins.
3. **Correct backslash handling** — escaped quotes inside strings are
   tracked without re-scanning preceding characters.
4. **Graceful degradation** — raises ValueError (not crashes) if no JSON
   object is found.
5. **Fenced block fast-path** — ```json ... ``` blocks are tried first
   with a compiled regex, short-circuiting the scan for typical LLM output.
"""
from __future__ import annotations

import json
import re
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum number of characters accepted for JSON scanning.
# LLM responses exceeding this are almost certainly not a single JSON object
# and scanning them would be wasteful or dangerous.
_MAX_INPUT_CHARS: int = 32_768  # 32 KiB

# Pre-compiled regex for the ```json ... ``` fast-path.
_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)

# Regex for a bare JSON object not wrapped in code fences.
# Used as a lightweight pre-filter before the full O(n) scan.
_BARE_JSON_HINT = re.compile(r"\{", re.DOTALL)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_json(text: str, max_chars: int = _MAX_INPUT_CHARS):
    """Extract the first JSON object OR array from text."""
    text = (text or "").strip()
    if len(text) > max_chars:
        text = text[:max_chars]

    # Fast-path: fenced ```json ... ``` block
    m = _FENCE_RE.search(text)
    if m:
        candidate = m.group(1)
        parsed = _try_parse(candidate)
        if parsed is not None:
            return parsed

    # Try scanning for a JSON object {...}
    result = _scan_for_object(text)
    if result is not None:
        return result

    # Try scanning for a JSON array [...]
    result = _scan_for_array(text)
    if result is not None:
        return result

    raise ValueError("No valid JSON found in LLM response")


def try_extract_json(text: str, max_chars: int = _MAX_INPUT_CHARS) -> Optional[dict]:
    """Like :func:`extract_json` but returns *None* instead of raising."""
    try:
        return extract_json(text, max_chars=max_chars)
    except (ValueError, RecursionError):
        return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _try_parse(candidate: str):
    """Attempt json.loads; return dict or list, or None on error."""
    try:
        result = json.loads(candidate)
        if isinstance(result, (dict, list)):
            return result
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def _scan_for_object(text: str) -> Optional[dict]:
    """Single O(n) pass that locates the outermost {...} JSON object.

    The scanner maintains:
    - ``depth``       — brace nesting level (0 = outside any object)
    - ``in_string``   — whether we are inside a JSON string literal
    - ``escaped``     — whether the immediately preceding character was an
                        unescaped backslash (toggle, not a counter)
    - ``start``       — character index of the opening '{' at depth==1

    Because we track the ``escaped`` flag as a single boolean (toggled on
    each '\\' when in a string), we handle arbitrarily long runs of
    backslashes in O(1) per character — no backward scanning.
    """
    n = len(text)
    depth = 0
    in_string = False
    escaped = False
    start = -1

    i = 0
    while i < n:
        ch = text[i]

        if in_string:
            if escaped:
                # Previous char was '\\'; this char is consumed as the escape target.
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
                escaped = False
            elif ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}" and depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    candidate = text[start : i + 1]
                    parsed = _try_parse(candidate)
                    if parsed is not None:
                        return parsed
                    # The outer braces matched but JSON was invalid
                    # (e.g. trailing comma, single quotes).  Keep scanning
                    # for another object after this position.
                    start = -1

        i += 1

    return None

def _scan_for_array(text: str):
    """Single O(n) pass that locates the outermost [...] JSON array."""
    n = len(text)
    depth = 0
    in_string = False
    escaped = False
    start = -1

    i = 0
    while i < n:
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
                escaped = False
            elif ch == "[":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "]" and depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    candidate = text[start : i + 1]
                    parsed = _try_parse(candidate)
                    if parsed is not None:
                        return parsed
                    start = -1
        i += 1
    return None
