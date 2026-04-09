"""
Lirox v1.0.0 — Desktop Controller
Main engine that orchestrates vision, actions, and overlay for
full computer-use capability.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Generator, List, Optional


class DesktopController:
    """
    High-level desktop control engine.

    Provides a perception-action loop:
    1. Capture screen via :class:`DesktopVision`
    2. Analyse what's visible and determine next action
    3. Execute action via :class:`DesktopActions`
    4. Optionally display feedback via :class:`DesktopOverlay`
    5. Repeat until the task is complete or max steps reached

    Usage::

        ctrl = DesktopController()
        for event in ctrl.execute("Open Firefox and search for Python"):
            print(event)
    """

    def __init__(self, max_steps: int = 40, action_delay: float = 0.6) -> None:
        """
        Initialise the desktop controller.

        Parameters
        ----------
        max_steps:
            Maximum number of perception-action iterations before stopping.
        action_delay:
            Seconds to wait between actions so the UI has time to settle.
        """
        self.max_steps    = max_steps
        self.action_delay = action_delay

    # ── Public API ────────────────────────────────────────────────────────────

    def execute(
        self, task: str, *, verbose: bool = False
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Run the perception-action loop for *task*.

        Yields event dicts with keys ``type`` and ``message``.

        Parameters
        ----------
        task:
            Natural-language description of what the agent should do.
        verbose:
            If *True*, yield extra debug events.
        """
        from lirox.desktop.vision   import DesktopVision
        from lirox.desktop.actions  import DesktopActions
        from lirox.desktop.overlay  import DesktopOverlay
        from lirox.utils.llm        import generate_response

        vision  = DesktopVision()
        actions = DesktopActions(action_delay=self.action_delay)
        overlay = DesktopOverlay()

        yield {"type": "agent_start", "message": f"🖥️  Desktop task: {task}"}
        overlay.show_status(f"Task: {task}")

        step    = 0
        history: List[str] = []

        while step < self.max_steps:
            step += 1

            # ── 1. Capture screen ─────────────────────────────────────────────
            screenshot_b64, description = vision.capture_and_describe()
            if verbose:
                yield {"type": "agent_progress", "message": f"Step {step}: {description[:120]}"}

            # ── 2. Plan next action ───────────────────────────────────────────
            history_ctx = "\n".join(history[-6:])
            prompt = (
                f"TASK: {task}\n\n"
                f"SCREEN: {description}\n\n"
                f"HISTORY (recent actions):\n{history_ctx}\n\n"
                f"What is the single best next action to make progress on the task?\n"
                f"Reply with ONLY a JSON object:\n"
                f'{{"action": "click|type|key|scroll|open|done|failed", '
                f'"target": "...", "text": "...", "key": "...", "reason": "..."}}'
            )

            try:
                raw = generate_response(
                    prompt,
                    provider="auto",
                    system_prompt=(
                        "You are a desktop automation agent. "
                        "Analyse the screen description and choose the single best next action. "
                        "Output ONLY valid JSON."
                    ),
                )
                import json as _json
                act = _json.loads(raw) if raw.strip().startswith("{") else {}
            except Exception as e:
                yield {"type": "agent_progress", "message": f"Planning error: {e}"}
                break

            action = act.get("action", "")
            reason = act.get("reason", "")

            # ── 3. Terminate conditions ───────────────────────────────────────
            if action == "done":
                overlay.clear()
                yield {"type": "done", "answer": f"✅ Task complete: {task}\n\n{reason}"}
                return

            if action == "failed":
                overlay.clear()
                yield {"type": "done", "answer": f"❌ Could not complete task: {reason}"}
                return

            # ── 4. Execute action ─────────────────────────────────────────────
            result = self._execute_action(actions, act)
            history.append(f"Step {step}: {action} — {result}")
            yield {"type": "tool_call", "message": f"🖱️  {action}: {act.get('target', act.get('text', act.get('key', '')))}"}

            overlay.show_step(step, action, act.get("target", ""))
            time.sleep(self.action_delay)

        overlay.clear()
        yield {
            "type": "done",
            "answer": f"⚠️  Reached max steps ({self.max_steps}) without completing task.",
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _execute_action(
        self, actions: "DesktopActions", act: Dict[str, Any]
    ) -> str:
        """Dispatch a single action dict to :class:`DesktopActions`."""
        action = act.get("action", "")
        target = act.get("target", "")
        text   = act.get("text", "")
        key    = act.get("key", "")

        try:
            if action == "click":
                return actions.click(target)
            elif action == "type":
                return actions.type_text(text)
            elif action == "key":
                return actions.press_key(key)
            elif action == "scroll":
                return actions.scroll(target, act.get("direction", "down"))
            elif action == "open":
                return actions.open_app(target)
            else:
                return f"Unknown action: {action}"
        except Exception as e:
            return f"Action error: {e}"
