"""Lirox v1.0.0 — PersonalAgent: files, shell, web, code, self-awareness"""
from __future__ import annotations
import json as _json
import os
import re
from pathlib import Path
from typing import Generator, Dict, Any

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.memory.manager import MemoryManager
from lirox.thinking.scratchpad import Scratchpad
from lirox.utils.llm import generate_response
from lirox.utils.streaming import StreamingResponse

_STREAMER = StreamingResponse()

_SYSTEM_RULES = (
    "\n\nCRITICAL EXECUTION RULES:\n"
    "• You have FULL filesystem access. NEVER say you cannot access it.\n"
    "• When asked to create/write/edit files — DO IT directly. Do not describe how.\n"
    "• When writing code — write the COMPLETE implementation. All imports. All logic. Never truncate.\n"
    "• When executing a task — EXECUTE it. Do not explain it.\n"
    "• Always address the user by name when you know it.\n"
    "• Think like a system architect: file task→use tools, shell→run command, "
    "web→search, code→write complete code, knowledge→answer from memory.\n"
)


def _get_sys(profile_data: dict = None) -> str:
    try:
        from lirox.mind.agent import get_soul, get_learnings
        base = get_soul().to_system_prompt(get_learnings().to_context_string())
    except Exception:
        base = "You are Lirox, an autonomous personal AI agent."
    if profile_data:
        lines = [f"• {lbl}: {profile_data.get(k,'')}"
                 for k, lbl in [("user_name","User name"),("niche","Their work"),
                                 ("current_project","Current project")]
                 if profile_data.get(k)]
        if lines and "USER PROFILE" not in base:
            base += "\n\nUSER PROFILE:\n" + "\n".join(lines)
    return base + _SYSTEM_RULES


def _extract_json(text: str) -> dict:
    depth = 0; start = None
    for i, ch in enumerate(text):
        if ch == "{":
            if start is None: start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    return _json.loads(text[start:i+1])
                except _json.JSONDecodeError:
                    start = None; depth = 0
    m = re.search(r"\{[^{}]*\}", text)
    if m:
        return _json.loads(m.group())
    raise ValueError("No JSON in LLM response")


FILE_SIGNALS  = ["read file","write file","create file","edit file","delete file",
                 "list files","search files","save to","open file","file contents",
                 "show me","what's in","look at","create a","make a","build a",
                 "generate a","write to","save as","in my ","in the ","folder",
                 "directory","pdf","csv","txt","json","markdown",".py",".js",
                 ".md","readme","file in","add to","put in","store","add details",
                 "read my","read the"]
SHELL_SIGNALS = ["run command","execute","terminal","bash","shell","git",
                 "python script","run python","npm","node","docker","pip install",
                 "run tests","git status","git commit","git push","git pull",
                 "start server","check port","ls ","pwd","build and run"]
WEB_SIGNALS   = ["search for","look up","find information","google","fetch url",
                 "browse to","what is","who is","latest news","wikipedia",
                 "research","find out about","current price","news about"]
CODE_SIGNALS  = ["write a","create a","build a","code for","function that",
                 "class that","script that","program that","implement","refactor",
                 "fix the bug","debug","add feature","api that","test for",
                 "algorithm","data structure","test api","llm api","python code",
                 "write code","write me a"]
SELF_SIGNALS  = ["your code","your source","how do you work","your architecture",
                 "your files","read your","understand yourself","lirox code",
                 "improve yourself","fix yourself"]

# Signals indicating the query requires the autonomy subsystem
AUTONOMY_SIGNALS = [
    "analyze my code", "analyse my code", "fix bugs", "scan codebase",
    "improve your code", "audit code", "self-improve",
    "generate code for", "create a caching", "build a", "implement a",
    "decompose", "break down", "step by step plan",
    "need permission", "ask permission",
]

# Signals that need advanced deep thinking
DEEP_THINK_SIGNALS = [
    "complex", "architecture", "design", "refactor", "best approach",
    "trade-off", "trade off", "pros and cons", "compare options",
    "which is better", "strategy",
]


def requires_autonomy(query: str) -> bool:
    q = query.lower()
    return any(s in q for s in AUTONOMY_SIGNALS)


def requires_deep_thinking(query: str) -> bool:
    q = query.lower()
    return any(s in q for s in DEEP_THINK_SIGNALS)


def classify_task(query: str) -> str:
    q = query.lower()
    if any(s in q for s in SELF_SIGNALS):  return "self"
    # Explicit file-path indicators take priority over generic "create a" phrases
    _file_path_signals = ["in my ", "in the ", "file", "folder", "directory",
                          ".py", ".js", ".txt", ".json", ".csv", ".pdf", ".md",
                          "save to", "write to", "add to", "store", "add details",
                          "file in", "put in"]
    if any(s in q for s in _file_path_signals) and any(s in q for s in FILE_SIGNALS):
        return "file"
    if any(s in q for s in CODE_SIGNALS):  return "code"
    if any(s in q for s in FILE_SIGNALS):  return "file"
    if any(s in q for s in SHELL_SIGNALS): return "shell"
    if any(s in q for s in WEB_SIGNALS):   return "web"
    return "chat"


class PersonalAgent(BaseAgent):
    @property
    def name(self) -> str: return "personal"
    @property
    def description(self) -> str: return "Autonomous personal agent"

    def run(self, query: str, system_prompt: str = "",
            context: str = "", mode: str = "complex") -> Generator[AgentEvent, None, None]:
        from lirox.utils.structured_logger import get_logger
        import time
        logger    = get_logger("lirox.agents.personal")
        start     = time.time()
        mem_ctx   = self.memory.get_relevant_context(query)

        # ── Autonomy subsystem intercept ──────────────────────────────────
        if requires_autonomy(query):
            yield from self._autonomy(query, mem_ctx, context, system_prompt)
            logger.info(f"PersonalAgent autonomy {(time.time()-start)*1000:.0f}ms")
            return

        task_type = classify_task(query)
        dispatch  = {"self": self._self, "code": self._code,
                     "file": self._file, "shell": self._shell,
                     "web": self._web, "chat": self._chat}

        # ── Deep thinking for complex queries ─────────────────────────────
        if requires_deep_thinking(query) and not context:
            try:
                from lirox.thinking.chain_of_thought import ThinkingEngine
                deep_trace = ThinkingEngine().reason_deep(query)
                if deep_trace:
                    yield {"type": "deep_thinking", "message": deep_trace[:600]}
                    context = deep_trace
            except Exception:
                pass

        yield from dispatch.get(task_type, self._chat)(query, mem_ctx, context, system_prompt)
        logger.info(f"PersonalAgent {task_type} {(time.time()-start)*1000:.0f}ms")

    # ── Autonomy ───────────────────────────────────────────────────────────
    def _autonomy(self, query, mem_ctx, context, sp=""):
        """Route the query through the autonomy subsystem."""
        from lirox.autonomy.autonomous_resolver import AutonomousResolver
        from lirox.autonomy.permission_system import PermissionTier

        yield {"type": "agent_progress", "message": "🤖 Activating autonomy subsystem…"}

        # Try to get the shared permission system from the orchestrator
        permissions = getattr(self, "_permissions", None)
        resolver = AutonomousResolver(permission_system=permissions)

        q = query.lower()

        # Self-improvement path
        if any(s in q for s in ["improve your code", "improve yourself", "self-improve",
                                 "fix yourself", "audit code", "scan codebase"]):
            if not resolver.permissions.has_permission(PermissionTier.SELF_MODIFY):
                yield {
                    "type":    "permission_request",
                    "message": (
                        "🔬 Self-modification requires TIER 5 permission.\n"
                        "  Reason : To scan and improve the Lirox codebase\n"
                        "  Action : Read all .py files, detect issues, generate patches"
                    ),
                    "data": {
                        "request": type("Req", (), {
                            "tier": PermissionTier.SELF_MODIFY,
                            "reason": "Scan and improve the Lirox codebase",
                            "action": "Read all .py files, detect issues, generate patches",
                            "alternatives": ["Use /improve command for the standard audit flow"],
                        })(),
                    },
                }
                answer = (
                    "Self-modification requires TIER 5 permission.\n"
                    "Use `/ask-permission 5` to grant it, then try again.\n"
                    "Alternatively, use `/improve` for the standard audit workflow."
                )
                self.memory.save_exchange(query, answer)
                for chunk in _STREAMER.stream_in_paragraphs(answer):
                    yield {"type": "streaming", "message": chunk}
                yield {"type": "done", "answer": answer}
                return

            for ev in resolver.resolve_self_improvement():
                yield ev
            return

        # Code analysis path
        if any(s in q for s in ["analyze my code", "analyse my code", "fix bugs",
                                 "scan", "find issues"]):
            if not resolver.permissions.has_permission(PermissionTier.FILE_READ):
                yield {
                    "type":    "permission_request",
                    "message": (
                        "📖 Code analysis requires TIER 1 (File Read) permission.\n"
                        "  Reason : I need to read your project files to analyse them.\n"
                        "  Action : Scan all Python files for issues"
                    ),
                    "data": {
                        "request": type("Req", (), {
                            "tier": PermissionTier.FILE_READ,
                            "reason": "Read project files to analyse them",
                            "action": "Scan all Python files for issues",
                            "alternatives": ["Describe the issue and I'll advise without file access"],
                        })(),
                    },
                }
                answer = (
                    "Code analysis requires TIER 1 (File Read) permission.\n"
                    "Use `/ask-permission 1` to grant it, then try again."
                )
                self.memory.save_exchange(query, answer)
                for chunk in _STREAMER.stream_in_paragraphs(answer):
                    yield {"type": "streaming", "message": chunk}
                yield {"type": "done", "answer": answer}
                return

            # Permission is available — run analysis
            from lirox.autonomy.code_intelligence import CodeIntelligence
            yield {"type": "code_analysis", "message": "📖 Scanning project…"}
            ci      = CodeIntelligence()
            summary = ci.summary()
            yield {"type": "code_analysis", "message": summary}
            answer  = generate_response(
                f"Query: {query}\n\nProject analysis:\n{summary}\n\n"
                "Provide actionable insights and suggestions.",
                provider="auto",
                system_prompt=_get_sys(self.profile_data),
            )
            self.memory.save_exchange(query, answer)
            for chunk in _STREAMER.stream_in_paragraphs(answer):
                yield {"type": "streaming", "message": chunk}
            yield {"type": "done", "answer": answer}
            return

        # Advanced code generation path
        if any(s in q for s in ["generate code for", "create a caching", "build a", "implement a"]):
            # Problem decomposition
            yield {"type": "deep_thinking", "message": "Breaking down the problem…"}
            from lirox.thinking.problem_decomposer import ProblemDecomposer
            steps = ProblemDecomposer().decompose(query)
            if steps:
                step_text = "\n".join(f"  {i}. {s}" for i, s in enumerate(steps, 1))
                yield {"type": "deep_thinking", "message": f"Steps:\n{step_text}"}

            for ev in resolver.resolve_code_generation(query):
                yield ev
            return

        # General fallback — use the standard code path with deep thinking context
        yield {"type": "deep_thinking", "message": "Applying deep reasoning…"}
        try:
            from lirox.thinking.chain_of_thought import ThinkingEngine
            trace = ThinkingEngine().reason_deep(query)
            if trace:
                yield {"type": "deep_thinking", "message": trace[:400]}
                context = trace
        except Exception:
            pass

        yield from self._code(query, mem_ctx, context, sp)

    # ── Self ──────────────────────────────────────────────────────────────
    def _self(self, query, mem_ctx, context, sp=""):
        from lirox.config import PROJECT_ROOT
        yield {"type": "agent_progress", "message": "📖 Reading own source code…"}
        lirox_dir = Path(PROJECT_ROOT) / "lirox"
        file_map  = {str(p.relative_to(PROJECT_ROOT)): p.read_text(errors="replace")[:2000]
                     for p in sorted(lirox_dir.rglob("*.py"))
                     if "__pycache__" not in str(p)}
        summary   = "\n".join(f"### {k}\n```python\n{v[:400]}\n```"
                               for k, v in list(file_map.items())[:12])
        answer    = generate_response(
            f"Query: {query}\n\nSource:\n{summary}\n\nAnswer based on actual code.",
            provider="auto", system_prompt=_get_sys(self.profile_data))
        self.memory.save_exchange(query, answer)
        for chunk in _STREAMER.stream_in_paragraphs(answer):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    # ── Code ──────────────────────────────────────────────────────────────
    def _code(self, query, mem_ctx, context, sp=""):
        yield {"type": "agent_progress", "message": "💻 Writing code…"}
        sys_p = _get_sys(self.profile_data) + (
            "\n\nCODE RULES: Write COMPLETE code. All imports. Error handling. "
            "`if __name__ == '__main__':` example. NEVER truncate. NEVER use '...'.")
        prompt = (f"Context:\n{mem_ctx}\n\nTask: {query}" if mem_ctx else query)
        if context:
            prompt = f"Thinking:\n{context[:2000]}\n\n{prompt}"
        answer = generate_response(prompt, provider="auto", system_prompt=sys_p)
        self._maybe_save(query, answer)
        self.memory.save_exchange(query, answer)
        for chunk in _STREAMER.stream_in_paragraphs(answer):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    def _maybe_save(self, query: str, answer: str):
        from lirox.tools.file_tools import file_write
        for pat in [r"(?:save|write|create|store)(?:\s+\w+)?\s+(?:to|in|as|at)\s+([~/\w.\-/]+)",
                    r"in\s+(?:my\s+)?([~/\w\-]+(?:/[~/\w.\-]+)*\.[a-z]+)"]:
            m = re.search(pat, query, re.IGNORECASE)
            if m:
                path = m.group(1).replace("~", str(Path.home()))
                cm   = re.search(r"```(?:\w+)?\n([\s\S]+?)```", answer)
                if cm:
                    try:
                        result = file_write(path, cm.group(1))
                        if result.startswith("❌") or "error" in result.lower():
                            from lirox.utils.structured_logger import get_logger
                            get_logger("lirox.personal_agent").warning(
                                f"_maybe_save failed for path '{path}': {result}"
                            )
                    except Exception as e:
                        from lirox.utils.structured_logger import get_logger
                        get_logger("lirox.personal_agent").warning(
                            f"_maybe_save exception: {e}"
                        )
                break

    # ── File ──────────────────────────────────────────────────────────────
    def _file(self, query, mem_ctx, context, sp=""):
        from lirox.tools.file_tools import file_read, file_write, file_list, file_delete, file_search
        yield {"type": "agent_progress", "message": "📁 Planning file operation…"}

        plan_prompt = (
            f"Task: {query}\n\nDetermine file operation. For write/create: include COMPLETE content.\n"
            f'Output ONLY JSON: {{"op":"read_file|write_file|list_files|delete_file|search_files",'
            f'"path":"...","content":"complete content","pattern":"*","query":"..."}}'
        )
        raw = generate_response(plan_prompt, provider="auto",
                                system_prompt="File operation planner. Output ONLY JSON.")
        result = ""
        try:
            d  = _extract_json(raw)
            if not isinstance(d, dict): d = {}
            op = d.get("op", "").lower()
            if not op:
                q2 = query.lower()
                if any(w in q2 for w in ["create","write","make","generate","save","add"]): op = "write_file"
                elif any(w in q2 for w in ["read","show","open","what's in","look"]): op = "read_file"
                elif any(w in q2 for w in ["list","ls","directory","folder"]): op = "list_files"
                else:
                    yield {"type": "tool_result", "message": "Could not determine file operation."}
                    yield from self._synth(query, "Could not determine file operation.")
                    return

            path    = str(Path(d.get("path","")).expanduser()) if d.get("path") else ""
            content = d.get("content","")
            pattern = d.get("pattern","*")
            fquery  = d.get("query","")

            yield {"type": "tool_call", "message": f"📁 {op}: {path}"}

            if op == "read_file":
                result = file_read(path)
            elif op == "write_file":
                if not content:
                    content = generate_response(
                        f"Generate complete file content for: {query}",
                        provider="auto", system_prompt="Write complete file content only.")
                result = file_write(path, content)
            elif op == "list_files":
                result = file_list(path, pattern)
            elif op == "delete_file":
                result = file_delete(path)
            elif op == "search_files":
                result = file_search(path or ".", fquery)
            else:
                result = f"Unknown op: {op}"

            yield {"type": "tool_result", "message": str(result)[:300]}
        except Exception as e:
            result = f"File error: {e}"
            yield {"type": "tool_result", "message": result}

        yield from self._synth(query, result)

    # ── Shell ─────────────────────────────────────────────────────────────
    def _shell(self, query, mem_ctx, context, sp=""):
        from lirox.tools.file_tools import run_shell
        yield {"type": "agent_progress", "message": "💻 Planning shell command…"}
        raw = generate_response(
            f"Task: {query}\nOutput ONLY JSON: "
            f'{{"command":"exact command","reason":"why"}}',
            provider="auto", system_prompt="Shell expert. Output ONLY JSON.")
        result = ""
        try:
            d       = _extract_json(raw)
            command = d.get("command","").strip()
            if not command:   # FIX: guard empty command
                yield {"type": "tool_result", "message": "Could not determine command."}
                yield from self._synth(query, "Could not determine command.")
                return
            reason = d.get("reason","")
            yield {"type": "tool_call", "message": f"$ {command}"}
            if reason: yield {"type": "agent_progress", "message": reason}
            result = run_shell(command)
            yield {"type": "tool_result", "message": str(result)[:300]}
        except Exception as e:
            result = f"Shell error: {e}"
            yield {"type": "tool_result", "message": result}
        yield from self._synth(query, result)

    # ── Web ───────────────────────────────────────────────────────────────
    def _web(self, query, mem_ctx, context, sp=""):
        yield {"type": "agent_progress", "message": "🌐 Searching the web…"}
        search_results = ""
        try:
            from lirox.tools.search.duckduckgo import search_ddg
            search_results = search_ddg(query)
            yield {"type": "tool_result", "message": f"Results for: {query[:80]}"}
        except Exception as e:
            yield {"type": "tool_result", "message": f"Search error: {e}"}
            search_results = f"Search failed: {e}"
        final = generate_response(
            f"Query: {query}\nResults:\n{str(search_results)[:6000]}\nComprehensive answer:",
            provider="auto", system_prompt=_get_sys(self.profile_data))
        self.memory.save_exchange(query, final)
        for chunk in _STREAMER.stream_in_paragraphs(final):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": final}

    # ── Chat ──────────────────────────────────────────────────────────────
    def _chat(self, query, mem_ctx, context, system_prompt=""):
        base_sys = system_prompt or _get_sys(self.profile_data)
        prompt   = (f"{mem_ctx}\n\nUser: {query}" if mem_ctx else query)
        if context: prompt = f"Thinking:\n{context[:2000]}\n\n{prompt}"
        answer = generate_response(prompt, provider="auto", system_prompt=base_sys)
        self.memory.save_exchange(query, answer)
        for chunk in _STREAMER.stream_in_paragraphs(answer):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    # ── Synth ─────────────────────────────────────────────────────────────
    def _synth(self, query, result):
        final = generate_response(
            f"Task: {query}\nResult: {result}\n\n"
            f"Summarize what was done. If file created confirm it. If command ran show output.",
            provider="auto", system_prompt=_get_sys(self.profile_data))
        self.memory.save_exchange(query, final)
        for chunk in _STREAMER.stream_in_paragraphs(final):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": final}
