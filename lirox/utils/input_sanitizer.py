"""Lirox v3.0 — Input Sanitizer

Sanitizes user input before it is forwarded to an LLM:
- Removes ASCII control characters (except normal whitespace)
- Strips null bytes
- Enforces a maximum length
- Detects obvious prompt-injection prefixes and neutralises them
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

# Maximum number of characters accepted from the user
MAX_INPUT_CHARS = 12_000

# Patterns that could hijack the system prompt if injected verbatim.
# We don't block these — we escape the leading marker so the LLM treats
# them as data rather than instructions.
_INJECTION_MARKERS = re.compile(
    r"^\s*(?:"
    r"system\s*:|"
    r"<\s*/?system\s*>|"
    r"<\s*/?instructions?\s*>|"
    r"\[\s*system\s*\]|"
    r"###\s*system|"
    r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?|"
    r"disregard\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?"
    r")",
    re.IGNORECASE | re.MULTILINE,
)

# Control characters to strip (keep \t, \n, \r)
_CTRL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize(text: str, max_chars: int = MAX_INPUT_CHARS) -> str:
    """Return a sanitized copy of *text* safe to embed in an LLM prompt.

    Steps:
    1. Truncate to *max_chars*
    2. Strip null bytes and control characters (preserving tabs and newlines)
    3. Normalize unicode to NFC
    4. Escape prompt-injection markers by prepending a zero-width space
    """
    if not text:
        return ""

    # 1. Truncate
    text = text[:max_chars]

    # 2. Strip control characters
    text = _CTRL_CHARS.sub("", text)

    # 3. Normalize unicode
    text = unicodedata.normalize("NFC", text)

    # 4. Neutralise injection markers (prefix each match with a sentinel)
    text = _INJECTION_MARKERS.sub(lambda m: "\u200b" + m.group(), text)

    return text


def sanitize_path(path: str) -> str:
    """Light sanitization for paths provided by the user.

    Removes null bytes and control characters.  Actual path-traversal
    checks are performed in file_tools._is_safe_path(); this is just a
    first-pass clean-up.
    """
    if not path:
        return ""
    path = _CTRL_CHARS.sub("", path).replace("\x00", "")
    return path[:4096]


def is_safe_input(text: str) -> tuple[bool, Optional[str]]:
    """Return (True, None) if *text* is acceptable, or (False, reason) otherwise."""
    if not text:
        return False, "Empty input"
    if len(text) > MAX_INPUT_CHARS:
        return False, f"Input exceeds {MAX_INPUT_CHARS} characters"
    if "\x00" in text:
        return False, "Null byte detected"
    return True, None
