"""Lirox v2.0.0 — UnifiedAgent

Single brain: think → plan → execute → respond.

BUG-4 FIX: /think now executes plans, not just returns text.
BUG-8 FIX: Sub-agents receive full conversation context.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Generator, List, Optional

from lirox.utils.llm import generate_response, DEFAULT_SYSTEM


class UnifiedAgent:
    """
    The core agent brain. Follows a four-phase pipeline:
      1. think(query)          — generate reasoning / chain-of-thought
      2. plan(query, thinking) — produce a structured action plan
      3. execute(plan)         — call tools, sub-agents, or shell
      4. respond(...)          — generate the final user-facing reply
    """

    def __init__(self, profile=None, learnings=None, memory=None, session_store=None):
        self.profile       = profile
        self.learnings     = learnings
        self.memory        = memory
        self.session_store = session_store

    # ── Phase 1: Think ────────────────────────────────────────────────────────

    def think(self, query: str) -> str:
        """Generate internal reasoning about the query."""
        context = ""
        if self.learnings:
            ctx = self.learnings.get_context_string()
            if ctx:
                context = f"\n\nUser knowledge base:\n{ctx}"

        prompt = (
            f"Think step-by-step about this request. Identify:\n"
            f"1. What the user really wants\n"
            f"2. What information or tools are needed\n"
            f"3. Any potential issues or edge cases\n"
            f"4. The best approach\n\n"
            f"Request: {query}"
            f"{context}"
        )
        return generate_response(prompt)

    # ── Phase 2: Plan ─────────────────────────────────────────────────────────

    def plan(self, query: str, thinking: str = "") -> List[Dict[str, Any]]:
        """
        Generate an action plan. Returns a list of step dicts:
        [{"action": "tool_name", "args": {...}, "description": "..."}]

        BUG-4 FIX: plan is actually executed, not just returned as text.
        """
        context_hint = f"\nThinking:\n{thinking[:1000]}" if thinking else ""
        prompt = (
            f"Create a concise action plan for this request.\n"
            f"Return ONLY a JSON array of steps. Each step has:\n"
            f"  action: one of [search, shell, file_read, file_write, llm, done]\n"
            f"  description: what this step does\n"
            f"  args: dict of arguments\n\n"
            f"Request: {query}"
            f"{context_hint}\n\n"
            f"Example:\n"
            f'[{{"action":"search","description":"Find info","args":{{"query":"..."}}}}, '
            f'{{"action":"done","description":"Respond","args":{{}}}}]'
        )
        raw = generate_response(prompt)
        from lirox.utils.llm import strip_code_fences
        raw = strip_code_fences(raw, "json")
        try:
            steps = json.loads(raw)
            if isinstance(steps, list):
                return steps
        except (json.JSONDecodeError, ValueError):
            pass
        # Fallback: single direct LLM step
        return [{"action": "done", "description": "Direct response", "args": {}}]

    # ── Phase 3: Execute ──────────────────────────────────────────────────────

    def execute(self, plan: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """
        Execute the plan steps. Returns list of result dicts.
        BUG-4 FIX: plans are actually executed here.
        """
        results = []
        for step in plan:
            action = step.get("action", "done")
            args   = step.get("args", {})
            desc   = step.get("description", "")

            if action == "done":
                results.append({"action": "done", "result": desc})

            elif action == "search":
                try:
                    from lirox.tools.search import web_search
                    result = web_search(args.get("query", query))
                    results.append({"action": "search", "result": result})
                except Exception as e:
                    results.append({"action": "search", "result": f"Search error: {e}"})

            elif action == "shell":
                try:
                    from lirox.tools.shell_ops import run_command
                    result = run_command(args.get("command", ""))
                    results.append({"action": "shell", "result": result})
                except Exception as e:
                    results.append({"action": "shell", "result": f"Shell error: {e}"})

            elif action == "file_read":
                try:
                    from lirox.tools.file_ops import read_file
                    result = read_file(args.get("path", ""))
                    results.append({"action": "file_read", "result": result})
                except Exception as e:
                    results.append({"action": "file_read", "result": f"File error: {e}"})

            elif action == "file_write":
                try:
                    from lirox.tools.file_ops import write_file
                    result = write_file(args.get("path", ""), args.get("content", ""))
                    results.append({"action": "file_write", "result": result})
                except Exception as e:
                    results.append({"action": "file_write", "result": f"File error: {e}"})

            elif action == "llm":
                try:
                    result = generate_response(args.get("prompt", query))
                    results.append({"action": "llm", "result": result})
                except Exception as e:
                    results.append({"action": "llm", "result": f"LLM error: {e}"})

            else:
                results.append({"action": action, "result": f"Unknown action: {action}"})

        return results

    # ── Phase 4: Respond ──────────────────────────────────────────────────────

    def respond(self, query: str, thinking: str = "",
                execution_results: List[Dict] = None,
                full_context: str = "") -> str:
        """Generate the final user-facing response."""
        # Build system prompt with learned context
        system = self._build_system_prompt()

        # Build the user prompt with gathered context
        parts = [f"Request: {query}"]

        if thinking:
            parts.append(f"\nInternal reasoning:\n{thinking[:500]}")

        if execution_results:
            tool_context = []
            for r in execution_results:
                action = r.get("action", "")
                result = r.get("result", "")
                if action not in ("done",) and result:
                    tool_context.append(f"[{action}]: {str(result)[:800]}")
            if tool_context:
                parts.append("\nTool results:\n" + "\n".join(tool_context))

        if full_context:
            parts.append(f"\nRecent conversation:\n{full_context[:2000]}")

        return generate_response("\n".join(parts), system_prompt=system)

    # ── Full Pipeline ─────────────────────────────────────────────────────────

    def run(self, query: str, deep: bool = False) -> Generator[Dict, None, None]:
        """
        Full think → plan → execute → respond pipeline.
        Yields dicts with type: "thinking" | "step" | "response" | "done" | "error"
        """
        try:
            # Get session context
            full_context = ""
            if self.session_store:
                full_context = self.session_store.get_context()

            # Phase 1: Think (for complex/deep requests)
            thinking = ""
            if deep or len(query) > 100:
                thinking = self.think(query)
                if thinking and not thinking.startswith("Error"):
                    yield {"type": "thinking", "content": thinking}

            # Phase 2: Plan
            steps = self.plan(query, thinking)
            has_real_steps = any(s.get("action") not in ("done", "llm")
                                 for s in steps)

            # Phase 3: Execute (only if there are real tool steps)
            execution_results = []
            if has_real_steps:
                execution_results = self.execute(steps, query)
                for r in execution_results:
                    if r.get("action") not in ("done",):
                        yield {"type": "step", "action": r["action"],
                               "result": str(r.get("result", ""))[:200]}

            # Phase 4: Respond
            response = self.respond(
                query, thinking, execution_results, full_context
            )
            yield {"type": "response", "content": response}
            yield {"type": "done", "response": response}

        except Exception as e:
            yield {"type": "error", "content": str(e)}

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        parts = [DEFAULT_SYSTEM]

        if self.profile:
            p = self.profile.data
            agent = p.get("agent_name", "Lirox")
            user  = p.get("user_name", "Operator")
            niche = p.get("niche", "Generalist")
            tone  = p.get("tone", "direct")
            parts.append(
                f"\nIdentity: You are {agent}, personal AI agent for {user}."
                f"\nUser's work: {niche}. Tone: {tone}."
            )

        if self.learnings:
            ctx = self.learnings.get_context_string()
            if ctx:
                parts.append(f"\nLearned knowledge about the user:\n{ctx}")

        return "\n".join(parts)
