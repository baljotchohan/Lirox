"""Robust code editor — fuzzy search-replace with graceful degradation.

Research-grounded design (Aider unified-diff study, Cline "Improving Diff
Edits by 10%", Diff-XYZ benchmark, Morph "string not found" post-mortem):

  * Search-replace is the most reliable *generation* format for capable models,
    but the naive "byte-exact match or fail" applier is the #1 source of agent
    failures ("String to replace not found", infinite retry loops, cost blowups).
  * The fix is a tolerant applier: try exact, then whitespace-normalised, then
    line-trimmed, then anchored fuzzy matching — and only then give up.
  * Ambiguity (multiple matches) must be reported, not silently applied to the
    first hit.

This module implements that ladder. It returns a :class:`FileReceipt` whose
``verified`` flag is only set once the change is confirmed on disk.
"""
from __future__ import annotations

import difflib
import logging
from typing import List, Optional, Tuple

from lirox.verify.receipt import FileReceipt

_logger = logging.getLogger("lirox.agentic.editor")

# A fuzzy match below this ratio is rejected as "not found".
_FUZZY_THRESHOLD = 0.85


def _norm_ws(s: str) -> str:
    """Collapse each line's internal whitespace and strip trailing space —
    used to compare snippets that differ only by formatting/indentation."""
    return "\n".join(" ".join(line.split()) for line in s.splitlines())


def _find_exact(haystack: str, needle: str) -> List[int]:
    """All start offsets of an exact substring match."""
    out, start = [], 0
    while True:
        i = haystack.find(needle, start)
        if i == -1:
            break
        out.append(i)
        start = i + 1
    return out


def _find_line_block(hay_lines: List[str], needle_lines: List[str],
                     transform) -> Optional[Tuple[int, int]]:
    """Find a run of lines in ``hay_lines`` matching ``needle_lines`` after
    applying ``transform`` to every line. Returns (start_line, end_line) or
    None. Requires a unique match."""
    n = len(needle_lines)
    if n == 0:
        return None
    t_needle = [transform(x) for x in needle_lines]
    matches = []
    for i in range(0, len(hay_lines) - n + 1):
        if [transform(x) for x in hay_lines[i:i + n]] == t_needle:
            matches.append((i, i + n))
    if len(matches) == 1:
        return matches[0]
    return None  # 0 or ambiguous


def _fuzzy_line_block(hay_lines: List[str], needle_lines: List[str]) -> Optional[Tuple[int, int, float]]:
    """Slide a window over the file and score similarity; return the best
    window (start, end, ratio) if above threshold and clearly unique-ish."""
    n = len(needle_lines)
    if n == 0 or n > len(hay_lines):
        return None
    needle = "\n".join(needle_lines)
    best = (0, 0, 0.0)
    for i in range(0, len(hay_lines) - n + 1):
        window = "\n".join(hay_lines[i:i + n])
        ratio = difflib.SequenceMatcher(None, _norm_ws(window), _norm_ws(needle)).ratio()
        if ratio > best[2]:
            best = (i, i + n, ratio)
    if best[2] >= _FUZZY_THRESHOLD:
        return best
    return None


def apply_edit(original: str, search: str, replace: str) -> Tuple[Optional[str], str, str]:
    """Pure function: apply a search→replace to ``original`` text.

    Returns ``(new_text_or_None, strategy, note)``. When new_text is None the
    edit could not be applied and ``note`` explains why.
    """
    if not search:
        return None, "none", "empty search snippet"

    # 1. Exact match.
    hits = _find_exact(original, search)
    if len(hits) == 1:
        i = hits[0]
        return original[:i] + replace + original[i + len(search):], "exact", ""
    if len(hits) > 1:
        return None, "ambiguous", (
            f"snippet occurs {len(hits)} times — add more surrounding context "
            "to make it unique")

    hay_lines = original.splitlines()
    needle_lines = search.splitlines()

    # 2. Whitespace-normalised, line-anchored match (unique only).
    for label, transform in (("trim", str.strip), ("normws", _norm_ws)):
        block = _find_line_block(hay_lines, needle_lines, transform)
        if block:
            s, e = block
            new_lines = hay_lines[:s] + replace.splitlines() + hay_lines[e:]
            trailing = "\n" if original.endswith("\n") else ""
            return "\n".join(new_lines) + trailing, f"ws-{label}", ""

    # 3. Fuzzy sliding window.
    fz = _fuzzy_line_block(hay_lines, needle_lines)
    if fz:
        s, e, ratio = fz
        new_lines = hay_lines[:s] + replace.splitlines() + hay_lines[e:]
        trailing = "\n" if original.endswith("\n") else ""
        return "\n".join(new_lines) + trailing, "fuzzy", f"matched at {ratio:.0%} similarity"

    return None, "not_found", "search snippet not found (even fuzzily)"


def edit_file(path: str, search: str, replace: str) -> FileReceipt:
    """Apply a fuzzy search-replace to a file on disk, going through Lirox's
    verified writer so all safety checks + audit apply. Verifies the change
    landed before reporting success."""
    from lirox.tools.file_tools import file_read_verified, file_write_verified

    read = file_read_verified(path, max_chars=1_000_000)
    if not read.ok:
        return FileReceipt(tool="edit_file", ok=False, operation="patch", path=path,
                           error=f"Could not read file: {read.error or 'unknown'}")

    original = read.details.get("content", "") if read.details else ""
    if not original and getattr(read, "message", ""):
        # Some readers stash content in message; fall back to a fresh read.
        try:
            with open(_resolve(path), "r", encoding="utf-8", errors="replace") as fh:
                original = fh.read()
        except Exception:  # noqa: BLE001
            pass

    new_text, strategy, note = apply_edit(original, search, replace)
    if new_text is None:
        return FileReceipt(tool="edit_file", ok=False, operation="patch", path=path,
                           error=f"Edit failed ({strategy}): {note}")

    if new_text == original:
        return FileReceipt(tool="edit_file", ok=True, verified=True, operation="patch",
                           path=path, message="No change needed (already matches).")

    write = file_write_verified(path, new_text)
    if not write.ok:
        return write
    msg = f"Edited {path} via {strategy} strategy"
    if note:
        msg += f" ({note})"
    write.message = msg
    write.operation = "patch"
    return write


def _resolve(path: str) -> str:
    """Best-effort path resolution mirroring file_tools, for the fallback read."""
    import os
    from lirox.config import WORKSPACE_DIR
    p = os.path.expanduser(path)
    if not os.path.isabs(p):
        p = os.path.join(os.getenv("LIROX_WORKSPACE", WORKSPACE_DIR), p)
    return p
