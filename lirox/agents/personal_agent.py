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
        task_type = classify_task(query)
        dispatch  = {"self": self._self, "code": self._code,
                     "file": self._file, "shell": self._shell,
                     "web": self._web, "chat": self._chat}
        yield from dispatch.get(task_type, self._chat)(query, mem_ctx, context, system_prompt)
        logger.info(f"PersonalAgent {task_type} {(time.time()-start)*1000:.0f}ms")

    # ── Self ──────────────────────────────────────────────────────────────
    def _self(self, query, mem_ctx, context, sp=""):
        from lirox.config import PROJECT_ROOT
        from lirox.autonomy.self_improver import SelfImprover
        from lirox.autonomy.code_executor import CodeExecutor

        q_lower = query.lower()
        lirox_dir = Path(PROJECT_ROOT) / "lirox"

        # Self-improvement / scanning branch
        if any(kw in q_lower for kw in ("improve", "fix", "scan", "analyse", "analyze", "bugs")):
            yield {"type": "agent_progress", "message": "🔍 Performing deep codebase analysis…"}
            improver = SelfImprover()
            yield from improver.analyse_and_stream(str(lirox_dir))
            summary = improver.get_improvement_summary(str(lirox_dir))
            self.memory.save_exchange(query, summary)
            for chunk in _STREAMER.stream_in_paragraphs(summary):
                yield {"type": "streaming", "message": chunk}
            yield {"type": "done", "answer": summary}
            return

        # Execution branch — run a code snippet found in the query
        if any(kw in q_lower for kw in ("execute", "run", "test")) and "```" in query:
            executor = CodeExecutor()
            code_match = re.search(r"```(?:python)?\n?([\s\S]+?)```", query)
            if code_match:
                yield {"type": "agent_progress", "message": "⚙️  Executing provided code…"}
                yield from executor.run_and_stream(code_match.group(1))
                yield {"type": "done", "answer": "Code executed."}
                return

        # Default: read own source and answer the query
        yield {"type": "agent_progress", "message": "📖 Reading own source code…"}
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
        from lirox.config import PROJECT_ROOT
        from lirox.autonomy.code_generator import CodeGenerator
        from lirox.autonomy.code_executor import CodeExecutor

        yield {"type": "agent_progress", "message": "💻 Writing code…"}

        # Determine if a save path was requested
        save_path = ""
        for pat in [r"(?:save|write|create|store)(?:\s+\w+)?\s+(?:to|in|as|at)\s+([~/\w.\-/]+)",
                    r"in\s+(?:my\s+)?([~/\w\-]+(?:/[~/\w.\-]+)*\.[a-z]+)"]:
            m = re.search(pat, query, re.IGNORECASE)
            if m:
                save_path = str(Path(m.group(1)).expanduser())
                break

        generator = CodeGenerator()
        for event in generator.generate_and_stream(
            query, root=str(Path(PROJECT_ROOT) / "lirox"),
            save_path=save_path, validate=True
        ):
            if event.get("type") == "streaming":
                # The generator already emits the final code as a streaming chunk
                answer = event.get("message", "")
                self.memory.save_exchange(query, answer)
                for chunk in _STREAMER.stream_in_paragraphs(answer):
                    yield {"type": "streaming", "message": chunk}
            else:
                yield event

        yield {"type": "done", "answer": "Code generation complete."}

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
