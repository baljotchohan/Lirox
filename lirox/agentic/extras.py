"""Advanced agentic capabilities: browser, sub-agent delegation, and a critic.

These layer on top of the core loop to close the remaining gaps versus SOTA
agents (OpenHands browser + critic model, Claude Code sub-agent delegation).

  * Browser tool — headless page fetch/read via Playwright when available, with
    a dependency-free HTTP+readability fallback so it works out of the box.
  * Sub-agent delegation — spawn a fresh AgentLoop with an isolated transcript
    for a focused sub-task; only a summary returns to the parent (the pattern
    that keeps the parent context small).
  * Critic / inference-time verification — score a finished trajectory and, for
    important tasks, run N attempts and keep the best (OpenHands' approach,
    approximated with an LLM critic instead of a trained reward model).
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional

from lirox.verify.receipt import ExecutionReceipt

_logger = logging.getLogger("lirox.agentic.extras")


# ══════════════════════════════════════════════════════════════════════════
# Browser tool
# ══════════════════════════════════════════════════════════════════════════

def _browse_playwright(url: str, wait_ms: int) -> Optional[str]:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception:  # noqa: BLE001
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(int(wait_ms))
            text = page.inner_text("body")
            browser.close()
            return text
    except Exception as exc:  # noqa: BLE001
        _logger.debug("Playwright browse failed: %s", exc)
        return None


def _browse_http(url: str) -> str:
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Lirox agent)"})
    with urllib.request.urlopen(req, timeout=25) as resp:  # noqa: S310 — user-driven fetch
        raw = resp.read().decode("utf-8", errors="replace")
    # crude readability: strip scripts/styles/tags, collapse whitespace
    raw = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", raw)
    text = re.sub(r"(?s)<[^>]+>", " ", raw)
    text = re.sub(r"&[a-z]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def browse(url: str, wait_ms: int = 800) -> ExecutionReceipt:
    """Fetch a page and return readable text. Uses Playwright for JS-heavy pages
    when installed; otherwise a lightweight HTTP+strip fallback."""
    if not re.match(r"^https?://", url):
        url = "https://" + url
    try:
        text = _browse_playwright(url, wait_ms)
        engine = "playwright"
        if text is None:
            text = _browse_http(url)
            engine = "http-fallback"
        text = (text or "")[:8000]
        return ExecutionReceipt(tool="browse", ok=True, verified=True,
                                message=text or "(empty page)",
                                details={"engine": engine, "url": url})
    except Exception as exc:  # noqa: BLE001
        return ExecutionReceipt(tool="browse", ok=False, error=str(exc),
                                details={"url": url})


def register_browser_tool(registry) -> None:
    from lirox.agentic.tools import DANGER_NETWORK
    registry.add(
        "browse", "Open a web page and return its readable text content.",
        {"url": {"type": "string", "description": "Page URL."},
         "wait_ms": {"type": "int", "description": "Extra render wait (JS pages).", "required": False}},
        browse, danger=DANGER_NETWORK,
    )


# ══════════════════════════════════════════════════════════════════════════
# Sub-agent delegation
# ══════════════════════════════════════════════════════════════════════════

def delegate(task: str, mode: str = "default", max_steps: int = 12,
             provider: str = "auto") -> ExecutionReceipt:
    """Run a focused sub-task in a fresh, isolated AgentLoop and return only its
    final summary — keeping the parent's context small."""
    from lirox.agentic.loop import AgentLoop
    from lirox.agentic.permissions import PermissionManager, PermissionMode
    from lirox.agentic.tools import default_registry

    sub = AgentLoop(
        registry=default_registry(),
        permissions=PermissionManager(PermissionMode.coerce(mode)),
        agent_name="Lirox-sub",
        provider=provider,
        max_steps=int(max_steps),
    )
    final, observations = "", 0
    for step in sub.run(task):
        if step.kind == "final":
            final = step.text
        elif step.kind == "observation":
            observations += 1
        elif step.kind == "error" and not final:
            final = f"(sub-agent did not finish cleanly: {step.text})"
    return ExecutionReceipt(
        tool="delegate", ok=bool(final), verified=bool(final),
        message=final or "sub-agent produced no summary",
        details={"observations": observations},
    )


def register_delegate_tool(registry) -> None:
    from lirox.agentic.tools import DANGER_SHELL
    registry.add(
        "delegate",
        "Delegate a focused sub-task to a fresh sub-agent; returns its summary. "
        "Use for self-contained chunks of work to keep your own context clean.",
        {"task": {"type": "string", "description": "Precise sub-task description."},
         "max_steps": {"type": "int", "description": "Sub-agent step budget.", "required": False}},
        delegate, danger=DANGER_SHELL,
    )


# ══════════════════════════════════════════════════════════════════════════
# Critic / inference-time verification
# ══════════════════════════════════════════════════════════════════════════

_CRITIC_SYSTEM = (
    "You are a strict QA critic. Given a TASK and an agent's TRANSCRIPT of "
    "actions and observations, judge whether the task was actually and "
    "correctly completed. Be skeptical: unverified claims of success count as "
    "incomplete. Respond with JSON only: "
    '{\"score\": <0-100 integer>, \"complete\": <true|false>, '
    '\"reason\": \"<one sentence>\"}'
)


def critique(task: str, transcript: str, provider: str = "auto") -> Dict[str, Any]:
    """LLM critic that scores whether a trajectory truly completed the task."""
    from lirox.utils.llm import generate_response
    from lirox.agentic.loop import _extract_action  # reuse robust JSON parsing
    prompt = f"TASK:\n{task}\n\nTRANSCRIPT:\n{transcript[:8000]}\n\nJSON verdict only."
    try:
        reply = generate_response(prompt, provider=provider,
                                  system_prompt=_CRITIC_SYSTEM + "\nOutput ONLY JSON.")
    except Exception as exc:  # noqa: BLE001
        return {"score": 0, "complete": False, "reason": f"critic error: {exc}"}
    obj = _extract_action(reply.replace('"action"', '"_action"')) or {}
    # _extract_action expects an "action" key; parse directly instead.
    import json
    for cand in (reply, _json_span(reply)):
        if not cand:
            continue
        try:
            data = json.loads(cand)
            return {
                "score": int(data.get("score", 0)),
                "complete": bool(data.get("complete", False)),
                "reason": str(data.get("reason", "")),
            }
        except Exception:  # noqa: BLE001
            continue
    return {"score": 0, "complete": False, "reason": "unparseable critic reply"}


def _json_span(text: str) -> Optional[str]:
    from lirox.agentic.loop import _largest_json_span
    return _largest_json_span(text or "")
