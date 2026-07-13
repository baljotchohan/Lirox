"""Transcript condenser — keeps long agent runs within context limits.

OpenHands' Condenser compresses older conversation history via an LLM summary
once a threshold is crossed, rather than crude truncation, so long-running
tasks don't lose earlier decisions. This is a lightweight equivalent: once the
transcript exceeds a size threshold, the middle portion (everything except the
original task and the most recent steps) is summarized into a compact bullet
list and spliced back in.

Falls back to a crude head/tail trim if the LLM call fails — condensation must
never crash the agent loop.
"""
from __future__ import annotations

import logging
from typing import List

_logger = logging.getLogger("lirox.agentic.condenser")

_SUMMARY_SYSTEM = (
    "Summarize this slice of an autonomous coding agent's transcript into a "
    "compact bullet list of: what was tried, what succeeded, what failed and "
    "why, and any facts learned about the codebase/environment. Be terse — "
    "this summary replaces the original steps in the agent's working memory. "
    "Output ONLY the bullet list, no preamble."
)


def _crude_trim(transcript: List[str], keep_recent: int) -> List[str]:
    if len(transcript) <= keep_recent + 1:
        return transcript
    head = transcript[:1]
    tail = transcript[-keep_recent:]
    return head + ["… (earlier steps condensed) …"] + tail


def condense(
    transcript: List[str],
    *,
    threshold: int = 40,
    keep_recent: int = 20,
    provider: str = "auto",
) -> List[str]:
    """Condense ``transcript`` in place-equivalent (returns a new list) once it
    grows past ``threshold`` entries. The first entry (the task) and the last
    ``keep_recent`` entries are always preserved verbatim."""
    if len(transcript) <= threshold:
        return transcript

    task = transcript[0]
    recent = transcript[-keep_recent:]
    middle = transcript[1:-keep_recent]
    if not middle:
        return transcript

    try:
        from lirox.utils.llm import generate_response
        joined = "\n".join(middle)[:12000]
        summary = generate_response(
            f"TRANSCRIPT SLICE:\n{joined}",
            provider=provider,
            system_prompt=_SUMMARY_SYSTEM,
        )
        if not summary or not summary.strip():
            raise ValueError("empty summary")
        return [task, f"EARLIER STEPS (condensed):\n{summary.strip()}"] + recent
    except Exception as exc:  # noqa: BLE001
        _logger.debug("LLM condensation failed, falling back to crude trim: %s", exc)
        return _crude_trim(transcript, keep_recent)
