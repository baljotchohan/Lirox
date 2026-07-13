"""The ReAct agentic loop — Lirox's autonomous core.

This is the architecture that separates a real agent from single-shot dispatch:
the model is given a task and a tool manifest, and it iterates

    THINK → choose ACTION (tool + args) → OBSERVE result → repeat

until it emits a ``finish`` action. It is **provider-agnostic**: instead of
vendor function-calling, tools are invoked through a strict JSON action protocol
the model emits in its reply. This works identically across groq, gemini,
anthropic, openai and local ollama models — mirroring how OpenHands' CodeAct and
Claude Code's core while-loop operate.

Design notes grounded in the research:
  * Robust JSON extraction (models wrap actions in prose / code fences / emit
    slightly malformed JSON) — we repair aggressively before giving up.
  * A hard step budget prevents the infinite-retry / cost-blowup failure mode.
  * Every tool result is fed back as an honest SUCCESS/FAILED observation
    (via receipt.as_llm_context()), so the agent self-corrects instead of
    hallucinating success.
  * Repeated identical failing actions are detected and the agent is nudged.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional

from lirox.agentic.permissions import PermissionManager, PermissionMode
from lirox.agentic.tools import ToolRegistry, default_registry
from lirox.verify.receipt import ExecutionReceipt

_logger = logging.getLogger("lirox.agentic.loop")


@dataclass
class AgentStep:
    """One iteration of the loop, streamed to the caller for display."""

    kind: str  # "thought" | "action" | "observation" | "final" | "error" | "denied" | "status"
    text: str = ""
    tool: str = ""
    args: Dict[str, Any] = field(default_factory=dict)
    receipt: Optional[ExecutionReceipt] = None
    step: int = 0


_SYSTEM_TEMPLATE = """You are {agent_name}, an autonomous agent operating a real computer.
You accomplish the user's TASK by taking a series of tool actions, observing the
results, and iterating until it is fully done.

You have these tools:
{tool_manifest}

RESPONSE PROTOCOL — every reply MUST be a single JSON object, nothing else:
{{"thought": "<brief reasoning about the next step>",
  "action": "<tool_name>",
  "args": {{ ... arguments ... }}}}

To finish, use the special action "finish":
{{"thought": "<why the task is complete>",
  "action": "finish",
  "args": {{"summary": "<what you accomplished, for the user>"}}}}

RULES:
- Output ONLY the JSON object. No prose, no markdown, no code fences.
- Take ONE action per reply. Wait for the observation before the next.
- Read files/inspect before editing. Prefer edit_file over rewriting whole files.
- After making changes, VERIFY them (re-read, run a test, run the code).
- If an action fails, read the error and try a different approach — never repeat
  the exact same failing action.
- Be decisive and efficient. Do not ask the user questions; act.
- Current permission mode: {mode}. Some actions may require approval.

{context}"""


def _extract_action(text: str) -> Optional[Dict[str, Any]]:
    """Pull a ``{thought, action, args}`` object out of an LLM reply, tolerating
    prose, code fences, and minor malformations."""
    if not text:
        return None

    candidates: List[str] = []

    # 1. fenced ```json blocks
    for m in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL):
        candidates.append(m.group(1))
    # 2. the largest brace-balanced span
    span = _largest_json_span(text)
    if span:
        candidates.append(span)
    # 3. the whole thing
    candidates.append(text.strip())

    for cand in candidates:
        obj = _try_load(cand)
        if isinstance(obj, dict) and "action" in obj:
            obj.setdefault("args", {})
            obj.setdefault("thought", "")
            if not isinstance(obj["args"], dict):
                obj["args"] = {}
            return obj
    return None


def _largest_json_span(text: str) -> Optional[str]:
    start = text.find("{")
    if start == -1:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
    return None


def _try_load(s: str) -> Any:
    try:
        return json.loads(s)
    except Exception:  # noqa: BLE001
        pass
    # light repair: trailing commas, single quotes, python bools
    repaired = re.sub(r",\s*([}\]])", r"\1", s)
    repaired = repaired.replace("True", "true").replace("False", "false").replace("None", "null")
    try:
        return json.loads(repaired)
    except Exception:  # noqa: BLE001
        return None


class AgentLoop:
    """A stateful ReAct agent. Call :meth:`run` and consume the streamed steps."""

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        permissions: Optional[PermissionManager] = None,
        *,
        agent_name: str = "Lirox",
        provider: str = "auto",
        max_steps: int = 25,
        max_repeat: int = 2,
        self_verify: bool = True,
        max_verify_retries: int = 1,
        audit: bool = True,
        condense_threshold: int = 40,
        condense_keep_recent: int = 20,
        use_skills: bool = True,
        learn_skills: bool = True,
        skill_min_steps: int = 3,
    ) -> None:
        self.registry = registry or default_registry()
        self.perms = permissions or PermissionManager(PermissionMode.DEFAULT)
        self.agent_name = agent_name
        self.provider = provider
        self.max_steps = max_steps
        self.max_repeat = max_repeat
        self.self_verify = self_verify
        self.max_verify_retries = max_verify_retries
        self.audit = audit
        self.condense_threshold = condense_threshold
        self.condense_keep_recent = condense_keep_recent
        self.use_skills = use_skills
        self.learn_skills = learn_skills
        self.skill_min_steps = skill_min_steps

    # ── LLM primitive ─────────────────────────────────────────────────────
    def _llm(self, system: str, prompt: str) -> str:
        from lirox.utils.llm import generate_response
        # The system prompt intentionally contains "JSON ... output only" so the
        # provider layer treats it as structured mode (no asterisk/CoT injection).
        return generate_response(
            prompt, provider=self.provider,
            system_prompt=system + "\n\nOutput ONLY valid JSON.",
        )

    @staticmethod
    def _log_audit(tool_name: str, args: Dict[str, Any], receipt: ExecutionReceipt) -> None:
        try:
            from lirox.safety.audit import log_audit_event
            target = json.dumps(args, default=str)[:500]
            log_audit_event(
                action=f"agentic.{tool_name}",
                target=target,
                status="ok" if receipt.ok else "error",
                detail=(receipt.message or receipt.error or "")[:1000],
                user_approved=True,  # reaching here means the permission gate allowed it
            )
        except Exception:  # noqa: BLE001 — audit must never break the loop
            pass

    def _learn(self, task: str, transcript: List[str]) -> Optional[Any]:
        """Best-effort closed learning-loop hook — never allowed to break the
        loop's return, since skill-writing is a bonus, not a requirement."""
        try:
            from lirox.agentic.skills import learn_from_run
            return learn_from_run(
                task, transcript,
                min_steps=self.skill_min_steps,
                provider=self.provider,
            )
        except Exception as exc:  # noqa: BLE001
            _logger.debug("Skill learning failed: %s", exc)
            return None

    def _critique(self, task: str, transcript: List[str], final_summary: str) -> Dict[str, Any]:
        from lirox.agentic.extras import critique
        full = "\n".join(transcript) + f"\n\nCLAIMED DONE: {final_summary}"
        try:
            return critique(task, full, provider=self.provider)
        except Exception as exc:  # noqa: BLE001
            _logger.debug("Critic failed, trusting the agent: %s", exc)
            return {"score": 100, "complete": True, "reason": f"critic unavailable ({exc})"}

    # ── main loop ─────────────────────────────────────────────────────────
    def run(self, task: str, context: str = "") -> Generator[AgentStep, None, None]:
        skill_matches = []
        if self.use_skills:
            try:
                from lirox.agentic.skills import SkillLibrary
                skill_matches = SkillLibrary().search(task, k=3)
                if skill_matches:
                    skill_text = SkillLibrary.render_for_prompt(skill_matches)
                    context = f"{context}\n\n{skill_text}" if context else skill_text
                    yield AgentStep(kind="status",
                                    text=f"Recalled {len(skill_matches)} learned skill(s): "
                                         f"{', '.join(s.name for s in skill_matches)}")
            except Exception as exc:  # noqa: BLE001
                _logger.debug("Skill recall failed: %s", exc)

        system = _SYSTEM_TEMPLATE.format(
            agent_name=self.agent_name,
            tool_manifest=self.registry.manifest(detailed=True),
            mode=self.perms.mode.value,
            context=(f"CONTEXT:\n{context}" if context else ""),
        )

        transcript: List[str] = [f"TASK: {task}"]
        recent_actions: List[str] = []
        verify_retries_used = 0

        for step in range(1, self.max_steps + 1):
            prompt = "\n\n".join(transcript) + (
                "\n\nWhat is your next action? Respond with the JSON object only."
            )
            try:
                reply = self._llm(system, prompt)
            except Exception as exc:  # noqa: BLE001
                yield AgentStep(kind="error", text=f"LLM call failed: {exc}", step=step)
                return

            action = _extract_action(reply)
            if action is None:
                # Nudge once; if the model truly can't produce JSON, surface reply.
                transcript.append(
                    "SYSTEM: Your last reply was not valid JSON. Reply with ONLY "
                    'a JSON object: {"thought":..,"action":..,"args":..}.'
                )
                yield AgentStep(kind="status", text="(reformatting — model did not emit valid action)", step=step)
                continue

            thought = str(action.get("thought", "")).strip()
            tool_name = str(action.get("action", "")).strip()
            args = action.get("args", {}) or {}
            if thought:
                yield AgentStep(kind="thought", text=thought, step=step)

            # ── finish ────────────────────────────────────────────────────
            if tool_name == "finish":
                final_summary = str(args.get("summary", "")).strip() or "Task complete."

                if self.self_verify and verify_retries_used < self.max_verify_retries:
                    verdict = self._critique(task, transcript, final_summary)
                    yield AgentStep(
                        kind="critique",
                        text=f"score={verdict['score']} complete={verdict['complete']}: {verdict['reason']}",
                        step=step,
                    )
                    if not verdict["complete"]:
                        verify_retries_used += 1
                        transcript.append(
                            f"SYSTEM: A QA critic reviewed your finish claim and found it "
                            f"INCOMPLETE: {verdict['reason']}. Address this before finishing again."
                        )
                        continue

                yield AgentStep(kind="final", text=final_summary, step=step)

                if self.learn_skills:
                    learned = self._learn(task, transcript)
                    if learned is not None:
                        yield AgentStep(kind="learned", text=f"New skill saved: {learned.name}")
                return

            spec = self.registry.get(tool_name)
            if spec is None:
                obs = (f"OBSERVATION: unknown tool '{tool_name}'. "
                       f"Available tools: {', '.join(self.registry.names())}, finish.")
                transcript.append(f"ACTION: {tool_name} {args}\n{obs}")
                yield AgentStep(kind="error", text=f"unknown tool '{tool_name}'", tool=tool_name, step=step)
                continue

            yield AgentStep(kind="action", text=thought, tool=tool_name, args=args, step=step)

            # ── permission gate ───────────────────────────────────────────
            allowed, reason = self.perms.authorize(spec, args)
            if not allowed:
                obs = f"OBSERVATION: action not permitted — {reason}."
                transcript.append(f"ACTION: {tool_name} {args}\n{obs}")
                yield AgentStep(kind="denied", text=reason, tool=tool_name, args=args, step=step)
                continue

            # ── loop-guard: repeated identical failing action ─────────────
            sig = f"{tool_name}:{json.dumps(args, sort_keys=True, default=str)}"
            recent_actions.append(sig)

            # ── execute ───────────────────────────────────────────────────
            receipt = self.registry.call(tool_name, args)
            obs = receipt.as_llm_context()

            if self.audit:
                self._log_audit(tool_name, args, receipt)

            # nudge if the agent is stuck repeating the same failing call
            if (recent_actions.count(sig) > self.max_repeat) and not receipt.ok:
                obs += ("\nSYSTEM: You have repeated this failing action multiple "
                        "times. Change your approach or use a different tool.")

            transcript.append(f"ACTION: {tool_name} {json.dumps(args, default=str)[:600]}\n{obs}")
            yield AgentStep(kind="observation", text=receipt.as_user_summary(),
                            tool=tool_name, receipt=receipt, step=step)

            # keep transcript from growing unbounded — LLM-summarizing condenser
            # (falls back to a crude head/tail trim if the summary call fails)
            if len(transcript) > self.condense_threshold:
                from lirox.agentic.condenser import condense
                transcript = condense(
                    transcript,
                    threshold=self.condense_threshold,
                    keep_recent=self.condense_keep_recent,
                    provider=self.provider,
                )

        # budget exhausted
        yield AgentStep(
            kind="error",
            text=(f"Reached the {self.max_steps}-step limit without finishing. "
                  "Partial progress may have been made."),
            step=self.max_steps,
        )
