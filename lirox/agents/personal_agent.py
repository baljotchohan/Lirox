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
    """
    Build the full system prompt. Profile data always takes priority for
    identity — the soul adds personality and learnings on top.
    This prevents the agent from forgetting its name or role.
    """
    profile_data = profile_data or {}

    # ── Identity anchors (from profile — always authoritative) ────────────────────────
    agent_name = profile_data.get("agent_name", "Lirox")
    user_name  = profile_data.get("user_name", "")

    # ── Soul + learnings (personality and user knowledge) ───────────────────────
    try:
        from lirox.mind.agent import get_soul, get_learnings
        soul = get_soul()
        # Ensure soul knows the correct name from profile
        if soul.get_name() != agent_name:
            soul.set_name(agent_name)
        base = soul.to_system_prompt(get_learnings().to_context_string())
    except Exception:
        base = (
            f"You are {agent_name}, a personal AI agent "
            f"{'for ' + user_name if user_name else ''}. "
            "You are direct, capable, and deeply personalized."
        )

    # ── Profile context ────────────────────────────────────────────────────────────────
    profile_lines = []
    for key, label in [
        ("user_name", "User's name"),
        ("niche", "Their work"),
        ("current_project", "Current project"),
        ("profession", "Profession"),
    ]:
        val = profile_data.get(key, "")
        if val and val not in ("Operator", "Generalist"):
            profile_lines.append(f"• {label}: {val}")

    if profile_lines and "USER PROFILE" not in base:
        base += "\n\nUSER PROFILE:\n" + "\n".join(profile_lines)

    # ── Goals ────────────────────────────────────────────────────────────────────────────────
    goals = profile_data.get("goals", [])
    if goals:
        base += "\n\nUSER'S GOALS:\n" + "\n".join(f"• {g}" for g in goals[:5])

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

# Signals that benefit from advanced deep thinking
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

    # Memory/history queries — handle with actual stored data
    MEMORY_SIGNALS = [
        "last conversation", "previous conversation", "what did we discuss",
        "what did we talk about", "what have you learned", "what do you know about me",
        "our history", "remember when", "last time", "you told me", "i told you",
        "what's my name", "who am i", "what are my", "tell me about yourself",
        "who are you", "what are you", "introduce yourself"
    ]
    if any(s in q for s in MEMORY_SIGNALS): return "memory"

    # File path indicators take priority
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
        dispatch  = {
            "self":   self._self,
            "code":   self._code,
            "file":   self._file,
            "shell":  self._shell,
            "web":    self._web,
            "chat":   self._chat,
            "memory": self._memory,   # NEW — handles identity/history queries
        }

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
        from lirox.autonomy.permission_system import PermissionTier, PermissionRequest

        yield {"type": "agent_progress", "message": "🤖 Activating autonomy subsystem…"}

        # Try to get the shared permission system from the orchestrator
        permissions = getattr(self, "_permissions", None)
        resolver    = AutonomousResolver(permission_system=permissions)

        q = query.lower()

        # Self-improvement path
        if any(s in q for s in ["improve your code", "improve yourself", "self-improve",
                                 "fix yourself", "audit code", "scan codebase"]):
            if not resolver.permissions.has_permission(PermissionTier.SELF_MODIFY):
                req = PermissionRequest(
                    tier=PermissionTier.SELF_MODIFY,
                    reason="Scan and improve the Lirox codebase",
                    action="Read all .py files, detect issues, generate patches",
                    alternatives=["Use /improve command for the standard audit flow"],
                )
                yield {
                    "type":    "permission_request",
                    "message": (
                        "🔬 Self-modification requires TIER 5 permission.\n"
                        "  Reason : To scan and improve the Lirox codebase\n"
                        "  Action : Read all .py files, detect issues, generate patches"
                    ),
                    "data": {"request": req},
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

            yield from resolver.resolve_self_improvement()
            return

        # Code analysis path
        if any(s in q for s in ["analyze my code", "analyse my code", "fix bugs",
                                 "scan", "find issues"]):
            if not resolver.permissions.has_permission(PermissionTier.FILE_READ):
                req = PermissionRequest(
                    tier=PermissionTier.FILE_READ,
                    reason="Read project files to analyse them",
                    action="Scan all Python files for issues",
                    alternatives=["Describe the issue and I'll advise without file access"],
                )
                yield {
                    "type":    "permission_request",
                    "message": (
                        "📖 Code analysis requires TIER 1 (File Read) permission.\n"
                        "  Reason : I need to read your project files to analyse them.\n"
                        "  Action : Scan all Python files for issues"
                    ),
                    "data": {"request": req},
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

            # Permission available — run analysis
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
        if any(s in q for s in ["generate code for", "create a caching",
                                 "build a", "implement a"]):
            yield {"type": "deep_thinking", "message": "Breaking down the problem…"}
            try:
                from lirox.thinking.problem_decomposer import ProblemDecomposer
                steps = ProblemDecomposer().decompose(query)
                if steps:
                    step_text = "\n".join(f"  {i}. {s}" for i, s in enumerate(steps, 1))
                    yield {"type": "deep_thinking", "message": f"Steps:\n{step_text}"}
            except Exception:
                pass

            yield from resolver.resolve_code_generation(query)
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
        from lirox.autonomy.self_improver import SelfImprover
        from lirox.autonomy.code_executor import CodeExecutor

        q_lower = query.lower()
        lirox_dir = Path(PROJECT_ROOT) / "lirox"

        # Self-improvement / scanning branch
        if any(kw in q_lower for kw in ("improve", "fix", "scan", "analyse", "analyze", "bugs")):
            yield {"type": "agent_progress", "message": "🔍 Performing deep codebase analysis…"}
            improver = SelfImprover(str(lirox_dir))
            yield from improver.analyse_and_stream()
            summary = improver.get_improvement_summary()
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

    # ── Code ─────────────────────────────────────────────────────────────────────────────
    def _code(self, query, mem_ctx, context, sp=""):
        """Generate code AND optionally execute it to verify it works."""
        yield {"type": "agent_progress", "message": "💻 Writing code…"}

        sys_p = _get_sys(self.profile_data) + (
            "\n\nCODE RULES:\n"
            "• Write COMPLETE code. ALL imports. Error handling. Never truncate.\n"
            "• Include a `if __name__ == '__main__':` demo section.\n"
            "• Add docstrings and type hints.\n"
            "• NEVER use '...' or placeholders."
        )

        prompt = f"Context:\n{mem_ctx}\n\nTask: {query}" if mem_ctx else query
        if context:
            prompt = f"Thinking:\n{context[:2000]}\n\n{prompt}"

        # Generate the code
        raw_answer = generate_response(prompt, provider="auto", system_prompt=sys_p)

        # Extract code block if present
        code_match = re.search(r"```(?:python)?\n?([\s\S]+?)```", raw_answer)
        code_block = code_match.group(1).strip() if code_match else ""

        # Auto-execute if it's a short script and user asked to run it
        should_execute = (
            code_block and
            len(code_block) < 5000 and
            any(kw in query.lower() for kw in ["run", "execute", "test", "try", "demo", "show me"])
        )

        # Check for save path request
        save_path = ""
        for pat in [r"(?:save|write|create|store)(?:\s+\w+)?\s+(?:to|in|as|at)\s+([~/\w.\-/]+)",
                    r"in\s+(?:my\s+)?([~/\w\-]+(?:/[~/\w.\-]+)*\.[a-z]+)"]:
            m = re.search(pat, query, re.IGNORECASE)
            if m:
                save_path = str(Path(m.group(1)).expanduser())
                break

        # Save if requested
        if save_path and code_block:
            from lirox.tools.file_tools import file_write
            save_result = file_write(save_path, code_block)
            yield {"type": "tool_result", "message": save_result}

        # Execute if appropriate
        if should_execute and code_block:
            yield {"type": "agent_progress", "message": "⚙️ Running code to verify it works…"}
            try:
                from lirox.autonomy.code_executor import CodeExecutor
                executor = CodeExecutor(timeout=15)
                exec_result = executor.execute(code_block)
                if exec_result.success:
                    yield {"type": "tool_result", "message": "✅ Executed successfully"}
                    if exec_result.stdout:
                        yield {"type": "tool_result", "message": f"Output:\n{exec_result.stdout[:500]}"}
                    raw_answer += f"\n\n**Execution output:**\n```\n{exec_result.stdout[:300]}\n```"
                else:
                    yield {"type": "tool_result",
                           "message": f"⚠ Execution failed: {exec_result.error or exec_result.stderr[:200]}"}
            except Exception:
                pass  # execution is best-effort

        self.memory.save_exchange(query, raw_answer)
        for chunk in _STREAMER.stream_in_paragraphs(raw_answer):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": raw_answer}

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

    # ── File (upgraded) ───────────────────────────────────────────────────────────────────────
    def _file(self, query, mem_ctx, context, sp=""):
        from lirox.tools.file_tools import (
            file_read, file_write, file_list, file_delete,
            file_search, file_patch, file_read_lines,
            create_directory, file_append, list_directory_tree
        )
        yield {"type": "agent_progress", "message": "📁 Planning file operation…"}

        plan_prompt = (
            f"Task: {query}\n\n"
            f"Determine the EXACT file operation needed. For write/create: include COMPLETE file content.\n\n"
            f'Output ONLY JSON:\n'
            f'{{"op":"read_file|read_lines|write_file|append_file|patch_file|list_files|'
            f'tree|delete_file|search_files|create_dir",'
            f'"path":"absolute or ~/relative path",'
            f'"content":"complete file content if writing",'
            f'"old_text":"exact text to replace (for patch)",'
            f'"new_text":"replacement text (for patch)",'
            f'"start_line":1,"end_line":50,'
            f'"pattern":"*","query":"search term"}}'
        )
        raw = generate_response(plan_prompt, provider="auto",
                                system_prompt="File operation planner. Output ONLY valid JSON. No explanation.")
        result = ""
        try:
            d = _extract_json(raw)
            if not isinstance(d, dict):
                d = {}
            op = d.get("op", "").lower()

            if not op:
                q2 = query.lower()
                if any(w in q2 for w in ["create","write","make","generate","save","add"]): op = "write_file"
                elif any(w in q2 for w in ["read","show","open","what's in","look","see"]): op = "read_file"
                elif any(w in q2 for w in ["list","ls","directory","folder","files in"]): op = "list_files"
                elif any(w in q2 for w in ["tree","structure","overview"]): op = "tree"
                elif any(w in q2 for w in ["patch","replace","fix","change","edit"]): op = "patch_file"
                elif any(w in q2 for w in ["append","add to","insert"]): op = "append_file"
                elif any(w in q2 for w in ["mkdir","create folder","create dir"]): op = "create_dir"
                else:
                    yield {"type": "tool_result", "message": "Could not determine file operation."}
                    yield from self._synth(query, "Could not determine file operation.")
                    return

            path    = str(Path(d.get("path","")).expanduser()) if d.get("path") else ""
            content = d.get("content", "")
            pattern = d.get("pattern", "*")
            fquery  = d.get("query", "")
            old_text = d.get("old_text", "")
            new_text = d.get("new_text", "")
            start_line = d.get("start_line", 1)
            end_line   = d.get("end_line", None)

            yield {"type": "tool_call", "message": f"📁 {op}: {path}"}

            if op == "read_file":
                result = file_read(path)
            elif op == "read_lines":
                result = file_read_lines(path, start_line, end_line)
            elif op == "write_file":
                if not content:
                    content = generate_response(
                        f"Generate COMPLETE file content for: {query}",
                        provider="auto",
                        system_prompt="Write complete file content only. No explanation. No markdown fences.")
                result = file_write(path, content)
            elif op == "append_file":
                result = file_append(path, content)
            elif op == "patch_file":
                if old_text and new_text:
                    result = file_patch(path, old_text, new_text)
                else:
                    result = "❌ patch_file requires old_text and new_text"
            elif op == "list_files":
                result = file_list(path or ".", pattern)
            elif op == "tree":
                result = list_directory_tree(path or ".")
            elif op == "delete_file":
                result = file_delete(path)
            elif op == "search_files":
                result = file_search(path or ".", fquery)
            elif op == "create_dir":
                result = create_directory(path)
            else:
                result = f"Unknown op: {op}"

            yield {"type": "tool_result", "message": str(result)[:400]}

        except Exception as e:
            result = f"File error: {e}"
            yield {"type": "tool_result", "message": result}

        yield from self._synth(query, result)

    # ── Shell (upgraded with real execution) ──────────────────────────────────────────────
    def _shell(self, query, mem_ctx, context, sp=""):
        from lirox.tools.terminal import run_command, is_safe
        yield {"type": "agent_progress", "message": "💻 Planning shell command…"}

        raw = generate_response(
            f"Task: {query}\n"
            f'Output ONLY JSON: {{"command":"exact shell command","reason":"why this command",'
            f'"working_dir":"~ or specific path or empty for cwd"}}',
            provider="auto",
            system_prompt="Shell expert. Output ONLY JSON. Be precise.")
        result = ""
        try:
            d       = _extract_json(raw)
            command = d.get("command", "").strip()
            reason  = d.get("reason", "")
            cwd     = d.get("working_dir", "").strip()

            if not command:
                yield {"type": "tool_result", "message": "Could not determine command."}
                yield from self._synth(query, "Could not determine command.")
                return

            # Expand home in working directory
            if cwd:
                cwd = str(Path(cwd).expanduser())

            # Safety check before running
            safe, safety_reason = is_safe(command)
            if not safe:
                yield {"type": "tool_result", "message": f"❌ Blocked: {safety_reason}"}
                yield from self._synth(query, f"Command blocked: {safety_reason}")
                return

            yield {"type": "tool_call", "message": f"$ {command}"}
            if reason:
                yield {"type": "agent_progress", "message": reason}

            # Execute with working directory if specified
            import subprocess, sys as _sys, shlex
            try:
                parsed = shlex.split(command)
                if parsed and parsed[0] in ("python3", "python"):
                    parsed[0] = _sys.executable
                proc = subprocess.run(
                    parsed,
                    capture_output=True, text=True, timeout=60,
                    cwd=cwd if cwd and Path(cwd).exists() else None
                )
                output = (proc.stdout + proc.stderr).strip()
                result = output if output else "✅ Command completed (no output)"
                if len(result) > 3000:
                    result = result[:3000] + f"\n\n[Output truncated — {len(result)} chars total]"
            except subprocess.TimeoutExpired:
                result = "❌ Command timed out after 60s"
            except Exception as ex:
                result = f"❌ Shell error: {ex}"

            yield {"type": "tool_result", "message": str(result)[:400]}
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
        """
        Conversational response. Always grounded in identity + user knowledge.
        No context from previous sessions — only from this session.
        """
        base_sys = system_prompt or _get_sys(self.profile_data)

        # Only use mem_ctx if it's directly relevant to this query
        if mem_ctx and mem_ctx.strip():
            prompt = f"Relevant context:\n{mem_ctx}\n\nUser: {query}"
        else:
            prompt = query

        if context:
            prompt = f"Thinking:\n{context[:1500]}\n\n{prompt}"

        answer = generate_response(prompt, provider="auto", system_prompt=base_sys)
        self.memory.save_exchange(query, answer)
        for chunk in _STREAMER.stream_in_paragraphs(answer):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    # ── Memory (answers about history, identity, what agent knows) ─────────────────────
    def _memory(self, query, mem_ctx, context, sp=""):
        """
        Handle questions about the agent's identity, the user's profile,
        and conversation history. Uses actual stored data — never hallucinates.
        """
        from lirox.mind.agent import get_soul, get_learnings
        from lirox.memory.session_store import SessionStore

        q = query.lower()

        soul      = get_soul()
        learnings = get_learnings()
        agent_name = self.profile_data.get("agent_name", soul.get_name())
        user_name  = self.profile_data.get("user_name", "")

        # Build a factual context block from ACTUAL stored data
        context_block = []

        # Identity questions
        if any(kw in q for kw in ["who are you", "what are you", "introduce yourself",
                                    "tell me about yourself", "your name"]):
            context_block.append(
                f"YOUR IDENTITY (factual, from stored profile):\n"
                f"Name: {agent_name}\n"
                f"Role: Personal AI agent for {user_name if user_name else 'this user'}\n"
                f"Soul depth: {soul.state.get('interaction_count', 0)} interactions logged"
            )

        # User knowledge questions
        if any(kw in q for kw in ["what do you know", "about me", "what's my", "who am i",
                                    "what have you learned", "my name"]):
            facts_summary = learnings.get_facts_summary(n=10)
            topics = learnings.get_top_topics(5)
            topic_str = ", ".join(t["topic"] for t in topics) if topics else "none yet"
            context_block.append(
                f"WHAT I KNOW ABOUT YOU (from LearningsStore):\n"
                f"Facts:\n{facts_summary}\n"
                f"Main interests: {topic_str}\n"
                f"Projects: {', '.join(p['name'] for p in learnings.data.get('projects', [])[:3]) or 'none yet'}"
            )

        # History questions
        if any(kw in q for kw in ["last conversation", "previous", "what did we discuss",
                                    "our history", "last time", "remember when"]):
            store = SessionStore()
            recent_sessions = store.list_sessions(limit=5)
            if recent_sessions:
                history_lines = []
                for s in recent_sessions[:3]:
                    user_msgs = [e.content[:100] for e in s.entries if e.role == "user"][:2]
                    if user_msgs:
                        history_lines.append(
                            f"  Session '{s.name}' ({s.created_at[:10]}): "
                            + " | ".join(user_msgs)
                        )
                context_block.append(
                    f"ACTUAL SESSION HISTORY (from disk):\n"
                    + "\n".join(history_lines)
                )
            else:
                context_block.append("No previous sessions found on disk.")

        # Build the final answer using actual data + LLM synthesis
        factual_ctx = "\n\n".join(context_block) if context_block else "No specific data found for this query."

        sys_prompt = _get_sys(self.profile_data)
        prompt = (
            f"USER QUERY: {query}\n\n"
            f"FACTUAL DATA FROM STORAGE (use ONLY this — do not invent or guess):\n"
            f"{factual_ctx}\n\n"
            f"Answer the user's question using ONLY the factual data above. "
            f"If data is missing, say so honestly. Never make things up."
        )

        answer = generate_response(prompt, provider="auto", system_prompt=sys_prompt)
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
