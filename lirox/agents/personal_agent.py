"""
Lirox v3.0 — PersonalAgent
The ONE agent. Everything lives here.

Capabilities:
  - File read/write/search/delete (safe paths only)
  - Shell command execution (whitelisted)
  - Web search + URL fetch
  - App and URL launching
  - Persistent memory of user facts and preferences
  - Chain-of-thought reasoning before every action
"""
from __future__ import annotations

import json as _json
import re
from typing import Generator, Dict, Any, Optional

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.memory.manager import MemoryManager
from lirox.thinking.scratchpad import Scratchpad
from lirox.utils.llm import generate_response
from lirox.utils.streaming import StreamingResponse
def _get_agent_system_prompt() -> str:
    from lirox.mind.agent import get_soul, get_learnings
    return get_soul().to_system_prompt(get_learnings().to_context_string())


def _extract_json(text: str) -> dict:
    """
    Extract the first complete JSON object from *text*.

    Uses bracket-counting rather than a greedy regex so that nested objects
    (e.g. {"key": {"inner": 1}}) are parsed correctly.  Falls back to the
    greedy-regex approach only when bracket counting finds nothing.

    Raises ValueError if no valid JSON object can be found.
    """
    # Bracket-counting pass — finds the first balanced { … }
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == "{":
            if start is None:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                candidate = text[start:i + 1]
                try:
                    return _json.loads(candidate)
                except _json.JSONDecodeError:
                    # Keep scanning — might be a false positive
                    start = None
                    depth = 0

    # Greedy-regex fallback: handles simple flat objects where bracket-counting
    # found no valid JSON (e.g. when the text contains unmatched braces in
    # surrounding prose but a simple flat JSON appears later in the text).
    m = re.search(r"\{[^{}]*\}", text)
    if m:
        return _json.loads(m.group())

    raise ValueError("No valid JSON object found in LLM response")


# ── Intent categories ─────────────────────────────────────────────────────────

FILE_SIGNALS = [
    "read file", "write file", "create file", "edit file", "delete file",
    "list files", "search files", "save to", "open file", "file contents",
    "show me", "what's in", "look at",
]

SHELL_SIGNALS = [
    "run command", "execute", "terminal", "bash", "shell", "git",
    "python script", "run python", "npm", "node", "docker",
]

WEB_SIGNALS = [
    "search for", "look up", "find information", "google", "fetch url",
    "browse to", "what is", "who is", "latest news", "wikipedia",
]


def classify_task(query: str) -> str:
    """
    Returns 'file', 'shell', 'web', or 'chat'.
    Used to decide which sub-handler to activate.
    """
    q = query.lower()
    if any(s in q for s in FILE_SIGNALS):
        return "file"
    if any(s in q for s in SHELL_SIGNALS):
        return "shell"
    if any(s in q for s in WEB_SIGNALS):
        return "web"
    return "chat"


class PersonalAgent(BaseAgent):
    """
    Single autonomous personal agent for Lirox v3.0.
    Handles all task types: file, shell, web, and chat.
    """

    @property
    def name(self) -> str:
        return "personal"

    @property
    def description(self) -> str:
        return "Autonomous personal agent — files, web, and conversation"

    def get_onboarding_message(self) -> str:
        return (
            "👋 Hi! I'm your **Personal Agent** — I can\n"
            "read and write files, run commands, search the web, and remember\n"
            "everything about you.\n\n"
            "Try: *'Create a Python script that...'* or *'Search for...'*"
        )

    # ── Main run ──────────────────────────────────────────────────────────────

    def run(
        self,
        query: str,
        system_prompt: str = "",
        context: str = "",
        mode: str = "complex",
    ) -> Generator[AgentEvent, None, None]:
        """
        Route the query to the appropriate sub-capability,
        then yield a stream of AgentEvent dicts.
        """
        from lirox.utils.structured_logger import get_logger
        import time

        logger = get_logger(f"lirox.agents.personal")
        start  = time.time()

        yield {"type": "agent_start", "message": "Analyzing task…"}

        # ── Memory context ────────────────────────────────────────────────────
        mem_ctx = self.memory.get_relevant_context(query)

        # ── Task classification ───────────────────────────────────────────────
        task_type = classify_task(query)

        # ── File operations ───────────────────────────────────────────────────
        if task_type == "file":
            yield from self._run_file_task(query, mem_ctx, context)

        # ── Shell execution ───────────────────────────────────────────────────
        elif task_type == "shell":
            yield from self._run_shell_task(query, mem_ctx, context)

        # ── Web search / fetch ────────────────────────────────────────────────
        elif task_type == "web":
            yield from self._run_web_task(query, mem_ctx, context)

        # ── Conversational / knowledge ────────────────────────────────────────
        else:
            yield from self._run_chat_task(query, mem_ctx, context, system_prompt)

        logger.info(
            f"PersonalAgent completed task_type={task_type} "
            f"in {(time.time()-start)*1000:.0f}ms"
        )

    # ── File sub-handler ──────────────────────────────────────────────────────

    def _run_file_task(
        self, query: str, mem_ctx: str, context: str
    ) -> Generator[AgentEvent, None, None]:
        """
        Ask LLM to plan a file operation, execute it, return results.
        """
        from lirox.tools.file_tools import (
            file_read, file_write, file_list, file_delete, file_search
        )

        yield {"type": "agent_progress", "message": "📁 Planning file operation…"}

        # Ask LLM what file action to take
        plan_prompt = (
            f"Task: {query}\n\n"
            f"Available file operations:\n"
            f"  read_file(path) — read file contents\n"
            f"  write_file(path, content, mode='w') — write file\n"
            f"  list_files(path, pattern='*') — list directory\n"
            f"  delete_file(path) — delete file\n"
            f"  search_files(root, query) — search file contents\n\n"
            f"Output ONLY valid JSON:\n"
            f'{{"op": "read_file|write_file|list_files|delete_file|search_files", '
            f'"path": "...", "content": "...", "pattern": "...", "query": "..."}}'
        )

        action_raw = generate_response(
            plan_prompt,
            provider="auto",
            system_prompt="You are a file operation planner. Output ONLY JSON.",
        )

        import json as _json
        result = ""
        try:
            op_dict = _extract_json(action_raw)
            op      = op_dict.get("op", "")
            path    = op_dict.get("path", "")
            content = op_dict.get("content", "")
            pattern = op_dict.get("pattern", "*")
            fquery  = op_dict.get("query", "")

            yield {"type": "tool_call", "message": f"📁 {op}: {path}"}

            if op == "read_file":
                result = file_read(path)
            elif op == "write_file":
                result = file_write(path, content)
            elif op == "list_files":
                result = file_list(path, pattern)
            elif op == "delete_file":
                result = file_delete(path)
            elif op == "search_files":
                result = file_search(path or ".", fquery)
            else:
                result = f"Unknown file op: {op}"

            yield {"type": "tool_result", "message": result[:300]}

        except Exception as e:
            result = f"File operation error: {e}"
            yield {"type": "tool_result", "message": result}

        # Synthesize final answer
        final = generate_response(
            f"Task: {query}\nResult of file operation:\n{result}\n\n"
            f"Provide a clear, concise summary of what was done and the results.",
            provider="auto",
            system_prompt=_get_agent_system_prompt(),
        )
        self.memory.save_exchange(query, final)

        # Stream the summary paragraph-by-paragraph
        for chunk in StreamingResponse().stream_in_paragraphs(final):
            yield {"type": "streaming", "message": chunk}

        yield {"type": "done", "answer": final}

    # ── Shell sub-handler ─────────────────────────────────────────────────────

    def _run_shell_task(
        self, query: str, mem_ctx: str, context: str
    ) -> Generator[AgentEvent, None, None]:
        from lirox.tools.file_tools import run_shell

        yield {"type": "agent_progress", "message": "💻 Planning shell command…"}

        plan_prompt = (
            f"Task: {query}\n\n"
            f"Determine the exact shell command to accomplish this task.\n"
            f"Output ONLY valid JSON:\n"
            f'{{"command": "exact shell command here", "reason": "why this command"}}'
        )

        action_raw = generate_response(
            plan_prompt,
            provider="auto",
            system_prompt="You are a shell command expert. Output ONLY JSON.",
        )

        import json as _json
        result = ""
        try:
            cmd_dict = _extract_json(action_raw)
            command  = cmd_dict.get("command", "")
            reason   = cmd_dict.get("reason", "")

            yield {"type": "tool_call", "message": f"$ {command}"}
            yield {"type": "agent_progress", "message": reason}

            result = run_shell(command)
            yield {"type": "tool_result", "message": result[:300]}

        except Exception as e:
            result = f"Shell planning error: {e}"
            yield {"type": "tool_result", "message": result}

        final = generate_response(
            f"Task: {query}\nCommand output:\n{result}\n\n"
            f"Summarize what happened and whether it succeeded.",
            provider="auto",
            system_prompt=_get_agent_system_prompt(),
        )
        self.memory.save_exchange(query, final)

        for chunk in StreamingResponse().stream_in_paragraphs(final):
            yield {"type": "streaming", "message": chunk}

        yield {"type": "done", "answer": final}

    # ── Web sub-handler ───────────────────────────────────────────────────────

    def _run_web_task(
        self, query: str, mem_ctx: str, context: str
    ) -> Generator[AgentEvent, None, None]:
        yield {"type": "agent_progress", "message": "🌐 Searching the web…"}

        # Try DuckDuckGo first
        search_results = ""
        try:
            from lirox.tools.search.duckduckgo import search_ddg
            search_results = search_ddg(query)
            yield {"type": "tool_result",
                   "message": f"Found: {str(search_results)[:200]}…"}
        except Exception as e:
            yield {"type": "tool_result", "message": f"Search: {e}"}

        # Synthesize answer
        final = generate_response(
            f"User query: {query}\n\nSearch results:\n{str(search_results)[:4000]}\n\n"
            f"Provide a comprehensive, well-structured answer based on these results.",
            provider="auto",
            system_prompt=_get_agent_system_prompt(),
        )
        self.memory.save_exchange(query, final)

        for chunk in StreamingResponse().stream_in_paragraphs(final):
            yield {"type": "streaming", "message": chunk}

        yield {"type": "done", "answer": final}

    # ── Chat sub-handler ──────────────────────────────────────────────────────

    def _run_chat_task(
        self, query: str, mem_ctx: str, context: str, system_prompt: str
    ) -> Generator[AgentEvent, None, None]:
        yield {"type": "agent_progress", "message": "Thinking…"}

        base_sys = system_prompt or _get_agent_system_prompt()
        prompt   = query
        if mem_ctx:
            prompt = f"{mem_ctx}\n\nUser: {query}"
        if context:
            prompt = f"Thinking:\n{context}\n\n{prompt}"

        # Get the full response without truncation
        answer = generate_response(prompt, provider="auto", system_prompt=base_sys)
        self.memory.save_exchange(query, answer)

        # Stream paragraph-by-paragraph for a live typing feel
        for chunk in StreamingResponse().stream_in_paragraphs(answer):
            yield {"type": "streaming", "message": chunk}

        yield {"type": "done", "answer": answer}
