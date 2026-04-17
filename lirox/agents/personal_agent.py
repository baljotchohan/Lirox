"""Lirox v1.1 — PersonalAgent with verified execution.

Key v2 changes vs v1:
  - All file ops go through FileReceipt and are disk-verified.
  - Shell ops go through ShellReceipt; non-zero exits never reported as success.
  - _synth_receipt() reads structured receipts — it CANNOT hallucinate success
    because the receipt explicitly marks `verified` and `ok`.
  - _synth_text() used only for read-only ops (list/tree/search).
  - Planner prompts include user's niche/current_project for better paths.
  - Path disambiguation: bare filenames resolved to ~/Desktop by default.
  - FILE_SIGNALS tightened so "create a function" no longer routes to file.
"""
from __future__ import annotations

import json as _json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Generator

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.thinking.scratchpad import Scratchpad
from lirox.utils.llm import generate_response
from lirox.utils.streaming import StreamingResponse
from lirox.verify import FileReceipt, ShellReceipt

_STREAMER = StreamingResponse()

_SYSTEM_RULES = (
    "\n\nCRITICAL EXECUTION RULES:\n"
    "• You have FULL filesystem access. Never say you cannot access it.\n"
    "• When asked to create/write/edit files — DO IT. Do not describe how.\n"
    "• When writing code — write the COMPLETE implementation. All imports. All logic.\n"
    "• Always address the user by name when known.\n"
    "• When a tool receipt says STATUS: SUCCESS_VERIFIED you may confirm success.\n"
    "  When it says STATUS: FAILED you MUST report failure honestly and show the error.\n"
    "  Never claim success unless the receipt confirms it.\n"
)


# ── System prompt construction ────────────────────────────────────

def _get_sys(profile_data: dict = None) -> str:
    profile_data = profile_data or {}
    agent_name = profile_data.get("agent_name", "Lirox")
    user_name  = profile_data.get("user_name", "")

    try:
        from lirox.mind.agent import get_soul, get_learnings
        soul = get_soul()
        if soul.get_name() != agent_name:
            soul.set_name(agent_name)
        base = soul.to_system_prompt(get_learnings().to_context_string())
    except Exception:
        base = (
            f"You are {agent_name}, a personal AI agent "
            f"{'for ' + user_name if user_name else ''}. "
            "You are direct, capable, and deeply personalized."
        )

    profile_lines = []
    for key, label in [
        ("user_name",       "User's name"),
        ("niche",           "Their work"),
        ("current_project", "Current project"),
        ("profession",      "Profession"),
    ]:
        val = profile_data.get(key, "")
        if val and val not in ("Operator", "Generalist"):
            profile_lines.append(f"• {label}: {val}")

    if profile_lines and "USER PROFILE" not in base:
        base += "\n\nUSER PROFILE:\n" + "\n".join(profile_lines)

    # Niche deep details
    niche_details = (profile_data.get("preferences") or {}).get("niche_details")
    if isinstance(niche_details, dict) and niche_details:
        base += "\n\nNICHE DETAILS:\n" + "\n".join(
            f"• {k.replace('_', ' ').title()}: {v}"
            for k, v in niche_details.items() if v
        )

    goals = profile_data.get("goals", [])
    if goals:
        base += "\n\nUSER'S GOALS:\n" + "\n".join(f"• {g}" for g in goals[:5])

    return base + _SYSTEM_RULES


# ── JSON extraction (robust) ──────────────────────────────────────

def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    # Strip markdown fence first
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return _json.loads(m.group(1))
        except Exception:
            pass
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
                try:
                    return _json.loads(text[start:i + 1])
                except _json.JSONDecodeError:
                    start = None
                    depth = 0
    raise ValueError("No JSON object in LLM response")


# Shell signals — must be unambiguous command-form phrases. Bare tool
# names like "python " or "git " match too eagerly (e.g. "show me a git
# tutorial" should not route to shell), so we require either a multi-word
# command phrase or a word-boundary regex check.
SHELL_SIGNALS = [
    "run command", "execute command", "execute this", "in the terminal",
    "in bash", "in shell", "run python", "run node", "run npm",
    "git status", "git commit", "git push", "git pull", "git diff",
    "git log", "git checkout", "git branch", "git merge", "git rebase",
    "npm install", "npm run", "pip install", "pip3 install",
    "python -c", "python -m", "python3 -c", "python3 -m",
    "docker run", "docker build", "docker ps", "docker compose",
    "start server", "check port", "build and run", "ls ", "pwd",
    "make test", "make build", "pytest ", "cargo run", "cargo build",
]

# Word-boundary shell tokens — match only as standalone words.
SHELL_WORD_TOKENS = {"git", "npm", "pip", "node", "docker", "yarn", "pytest"}

FILE_SIGNALS = [
    "read file", "write file", "create file", "edit file", "delete file",
    "save to", "open file", "file contents", "in my ", "in the ",
    "folder", "directory",
    ".py", ".js", ".md", ".txt", ".json", ".csv", ".pdf",
    "readme", "file in", "add to", "put in", "store in",
    "on my desktop", "in downloads", "in documents",
    "save as", "write to", "append to",
]

# File intents that DO NOT need a path anchor to qualify. These are
# explicit listing/searching phrases that are unambiguously file-oriented.
FILE_INTENT_BYPASS = [
    "list files", "show me files", "what files", "all files",
    "list my files", "search files", "find files", "list of files",
    "show files",
]

# Path anchors used to disambiguate generic FILE_SIGNALS from CODE_SIGNALS.
_FILE_PATH_ANCHORS = (
    ".", "/", "\\", "~", "desktop", "documents", "downloads",
    "folder", "directory",
)

WEB_SIGNALS = [
    "search for", "look up", "find information", "google", "fetch url",
    "browse to", "latest news", "wikipedia", "research", "find out about",
    "current price", "news about",
]

CODE_SIGNALS = [
    "write a function", "create a function", "create a class",
    "build a script", "code for", "function that", "class that",
    "script that", "program that", "implement", "refactor",
    "fix the bug", "debug", "add feature", "api that", "test for",
    "algorithm", "data structure", "python code", "write code",
    "create a python script", "create a script",
]

SELF_SIGNALS = [
    "your code", "your source", "how do you work", "your architecture",
    "your files", "read your", "understand yourself", "lirox code",
    "improve yourself", "fix yourself",
]

AUTONOMY_SIGNALS = [
    "analyze my code", "analyse my code", "fix bugs", "scan codebase",
    "improve your code", "audit code", "self-improve",
    "generate code for", "decompose", "break down", "step by step plan",
    "need permission", "ask permission",
]

DEEP_THINK_SIGNALS = [
    "complex", "architecture", "design", "refactor", "best approach",
    "trade-off", "trade off", "pros and cons", "compare options",
    "which is better", "strategy",
]

MEMORY_SIGNALS = [
    "last conversation", "previous conversation", "what did we discuss",
    "what did we talk about", "what have you learned",
    "what do you know about me",
    "our history", "remember when", "last time", "you told me",
    "i told you", "what's my name", "who am i", "what are my",
    "tell me about yourself", "who are you", "what are you",
    "introduce yourself",
]


def requires_autonomy(q: str) -> bool:
    q = q.lower()
    return any(s in q for s in AUTONOMY_SIGNALS)


def requires_deep_thinking(q: str) -> bool:
    q = q.lower()
    return any(s in q for s in DEEP_THINK_SIGNALS)


def _matches_shell(q: str) -> bool:
    """True if query is a shell-execution intent.

    Checks two conditions:
      1. Any SHELL_SIGNALS substring matches.
      2. Any SHELL_WORD_TOKENS appears as a standalone word
         AND the query has command-y verbs (run/execute/exec).
    """
    if any(s in q for s in SHELL_SIGNALS):
        return True
    has_command_verb = any(v in q for v in ("run ", "execute ", "exec "))
    if has_command_verb:
        for tok in SHELL_WORD_TOKENS:
            if re.search(rf"\b{tok}\b", q):
                return True
    return False


def classify_task(query: str) -> str:
    q = query.lower()
    if any(s in q for s in SELF_SIGNALS):
        return "self"
    if any(s in q for s in MEMORY_SIGNALS):
        return "memory"
    # File intents that bypass the anchor requirement (B8 fix)
    if any(s in q for s in FILE_INTENT_BYPASS):
        return "file"
    # File: explicit when there's a path anchor present (B7 disambiguation)
    if any(s in q for s in FILE_SIGNALS) and any(a in q for a in _FILE_PATH_ANCHORS):
        return "file"
    # Code beats shell — "create a python script" is code, not shell (B7 fix)
    if any(s in q for s in CODE_SIGNALS):
        return "code"
    if any(s in q for s in FILE_SIGNALS):
        return "file"
    # Shell now uses the stricter matcher (B19 fix)
    if _matches_shell(q):
        return "shell"
    if any(s in q for s in WEB_SIGNALS):
        return "web"
    return "chat"


# ── Path resolver ─────────────────────────────────────────────────

def _resolve_target_path(raw_path: str, query: str, default_dir: str = "~/Desktop") -> str:
    """Given a planner-proposed path and the user's query, produce an absolute path.

    Rules:
      - ~ expanded; env vars expanded.
      - If raw_path is a bare filename (no slash), prefix with default_dir
        (or contextual folder from query).
      - Absolute paths pass through unchanged.
    """
    if not raw_path:
        return ""
    p = os.path.expandvars(os.path.expanduser(raw_path))
    # Already absolute? Keep.
    if os.path.isabs(p):
        return p
    # Has a directory component? Make absolute.
    if ("/" in p) or ("\\" in p):
        return os.path.abspath(p)
    # Bare filename — choose folder from query context
    q = (query or "").lower()
    if "downloads" in q:
        folder = "~/Downloads"
    elif "documents" in q:
        folder = "~/Documents"
    elif "desktop" in q:
        folder = "~/Desktop"
    else:
        folder = default_dir
    return os.path.abspath(os.path.expanduser(os.path.join(folder, p)))


# ─────────────────────────────────────────────────────────────────
# PersonalAgent
# ─────────────────────────────────────────────────────────────────

class PersonalAgent(BaseAgent):
    @property
    def name(self) -> str: return "personal"
    @property
    def description(self) -> str: return "Autonomous personal agent"

    # ── Entry ──────────────────────────────────────────────────────
    def run(self, query: str, system_prompt: str = "",
            context: str = "", mode: str = "complex") -> Generator[AgentEvent, None, None]:
        from lirox.utils.structured_logger import get_logger
        logger = get_logger("lirox.agents.personal")
        start  = time.time()
        mem_ctx = self.memory.get_relevant_context(query)

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
            "memory": self._memory,
        }

        if requires_deep_thinking(query) and not context:
            try:
                from lirox.thinking.chain_of_thought import ThinkingEngine
                deep = ThinkingEngine().reason_deep(query)
                if deep:
                    yield {"type": "deep_thinking", "message": deep[:600]}
                    context = deep
            except Exception:
                pass

        yield from dispatch.get(task_type, self._chat)(query, mem_ctx, context, system_prompt)
        logger.info(f"PersonalAgent {task_type} {(time.time()-start)*1000:.0f}ms")

    # ── Autonomy ─────────────────────────────────────────────────
    def _autonomy(self, query, mem_ctx, context, sp=""):
        from lirox.autonomy.autonomous_resolver import AutonomousResolver
        from lirox.autonomy.permission_system import PermissionTier, PermissionRequest
        yield {"type": "agent_progress", "message": "🤖 Activating autonomy subsystem…"}
        permissions = getattr(self, "_permissions", None)
        resolver = AutonomousResolver(permission_system=permissions)
        q = query.lower()

        if any(s in q for s in ["improve your code", "improve yourself", "self-improve",
                                  "fix yourself", "audit code", "scan codebase"]):
            if not resolver.permissions.has_permission(PermissionTier.SELF_MODIFY):
                req = PermissionRequest(
                    tier=PermissionTier.SELF_MODIFY,
                    reason="Scan and improve the Lirox codebase",
                    action="Read all .py files, detect issues, generate patches",
                    alternatives=["Use /improve for the standard audit flow"],
                )
                yield {"type": "permission_request",
                       "message": "🔬 Self-modification requires TIER 5 permission.",
                       "data": {"request": req}}
                answer = "Self-modification needs TIER 5. Use `/ask-permission 5`."
                self.memory.save_exchange(query, answer)
                for chunk in _STREAMER.stream_in_paragraphs(answer):
                    yield {"type": "streaming", "message": chunk}
                yield {"type": "done", "answer": answer}
                return
            yield from resolver.resolve_self_improvement()
            return

        if any(s in q for s in ["analyze my code", "analyse my code", "fix bugs",
                                  "scan", "find issues"]):
            if not resolver.permissions.has_permission(PermissionTier.FILE_READ):
                req = PermissionRequest(
                    tier=PermissionTier.FILE_READ,
                    reason="Read project files to analyse them",
                    action="Scan all Python files for issues",
                    alternatives=["Describe the issue and I'll advise without file access"],
                )
                yield {"type": "permission_request",
                       "message": "📖 Code analysis requires TIER 1 permission.",
                       "data": {"request": req}}
                answer = "Code analysis needs TIER 1. Use `/ask-permission 1`."
                self.memory.save_exchange(query, answer)
                for chunk in _STREAMER.stream_in_paragraphs(answer):
                    yield {"type": "streaming", "message": chunk}
                yield {"type": "done", "answer": answer}
                return
            from lirox.autonomy.code_intelligence import CodeIntelligence
            yield {"type": "code_analysis", "message": "📖 Scanning project…"}
            summary = CodeIntelligence().summary()
            yield {"type": "code_analysis", "message": summary}
            answer = generate_response(
                f"Query: {query}\n\nProject analysis:\n{summary}\n\nProvide insights.",
                provider="auto", system_prompt=_get_sys(self.profile_data),
            )
            self.memory.save_exchange(query, answer)
            for chunk in _STREAMER.stream_in_paragraphs(answer):
                yield {"type": "streaming", "message": chunk}
            yield {"type": "done", "answer": answer}
            return

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

    # ── Self ──────────────────────────────────────────────────────
    def _self(self, query, mem_ctx, context, sp=""):
        from lirox.config import PROJECT_ROOT
        from lirox.autonomy.self_improver import SelfImprover
        from lirox.autonomy.code_executor import CodeExecutor

        q_lower = query.lower()
        lirox_dir = Path(PROJECT_ROOT) / "lirox"

        if any(kw in q_lower for kw in ("improve", "fix", "scan", "analyse", "analyze", "bugs")):
            yield {"type": "agent_progress", "message": "🔍 Performing deep codebase analysis…"}
            imp = SelfImprover(str(lirox_dir))
            yield from imp.analyse_and_stream()
            summary = imp.get_improvement_summary()
            self.memory.save_exchange(query, summary)
            for chunk in _STREAMER.stream_in_paragraphs(summary):
                yield {"type": "streaming", "message": chunk}
            yield {"type": "done", "answer": summary}
            return

        if any(kw in q_lower for kw in ("execute", "run", "test")) and "```" in query:
            cm = re.search(r"```(?:python)?\n?([\s\S]+?)```", query)
            if cm:
                yield {"type": "agent_progress", "message": "⚙️  Executing code…"}
                yield from CodeExecutor().run_and_stream(cm.group(1))
                yield {"type": "done", "answer": "Code executed."}
                return

        yield {"type": "agent_progress", "message": "📖 Reading own source code…"}
        file_map = {str(p.relative_to(PROJECT_ROOT)): p.read_text(errors="replace")[:2000]
                    for p in sorted(lirox_dir.rglob("*.py"))
                    if "__pycache__" not in str(p)}
        summary = "\n".join(f"### {k}\n```python\n{v[:400]}\n```"
                             for k, v in list(file_map.items())[:12])
        answer = generate_response(
            f"Query: {query}\n\nSource:\n{summary}\n\nAnswer from actual code.",
            provider="auto", system_prompt=_get_sys(self.profile_data),
        )
        self.memory.save_exchange(query, answer)
        for chunk in _STREAMER.stream_in_paragraphs(answer):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    # ── File (verified) ──────────────────────────────────────────
    def _file(self, query, mem_ctx, context, sp=""):
        from lirox.tools.file_tools import (
            file_read_verified, file_write_verified, file_list,
            file_delete_verified, file_search, file_patch_verified,
            file_read_lines, create_directory_verified,
            file_append_verified, list_directory_tree,
        )
        yield {"type": "agent_progress", "message": "📁 Planning file operation…"}

        # Build niche-aware planner prompt
        niche    = self.profile_data.get("niche", "")
        cur_proj = self.profile_data.get("current_project", "")
        profile_hint = ""
        if niche or cur_proj:
            profile_hint = f"\nUSER CONTEXT: niche={niche!r} project={cur_proj!r}"

        plan_prompt = (
            f"Task: {query}{profile_hint}\n\n"
            "Determine the EXACT file operation. For write/create: include COMPLETE file content.\n"
            "For paths: use absolute paths or ~-prefixed. If the user says 'on my desktop' etc., reflect that.\n\n"
            'Output ONLY JSON:\n'
            '{"op":"read_file|read_lines|write_file|append_file|patch_file|list_files|tree|'
            'delete_file|search_files|create_dir",'
            '"path":"absolute or ~/relative path",'
            '"content":"complete file content if writing",'
            '"old_text":"exact text to replace (for patch)",'
            '"new_text":"replacement text (for patch)",'
            '"start_line":1,"end_line":50,'
            '"pattern":"*","query":"search term"}'
        )

        raw = generate_response(
            plan_prompt, provider="auto",
            system_prompt="File operation planner. Output ONLY valid JSON.",
        )

        receipt = None
        text_result = None

        try:
            d = _extract_json(raw)
            if not isinstance(d, dict):
                d = {}
            op = (d.get("op") or "").lower()

            if not op:
                q2 = query.lower()
                if any(w in q2 for w in ["create","write","make","generate","save","add"]): op = "write_file"
                elif any(w in q2 for w in ["read","show","open","what's in","look","see"]): op = "read_file"
                elif any(w in q2 for w in ["list","ls","directory","folder","files in"]):   op = "list_files"
                elif any(w in q2 for w in ["tree","structure","overview"]):                  op = "tree"
                elif any(w in q2 for w in ["patch","replace","fix","change","edit"]):        op = "patch_file"
                elif any(w in q2 for w in ["append","add to","insert"]):                    op = "append_file"
                elif any(w in q2 for w in ["mkdir","create folder","create dir"]):           op = "create_dir"
                else:
                    receipt = FileReceipt(tool="file", operation="unknown",
                                          error="Could not determine file operation.")
                    yield {"type": "tool_result", "message": receipt.as_user_summary()}
                    yield from self._synth_receipt(query, receipt)
                    return

            raw_path = d.get("path", "") or ""
            path = _resolve_target_path(raw_path, query) if raw_path else ""
            content    = d.get("content", "")
            pattern    = d.get("pattern", "*")
            fquery     = d.get("query", "")
            old_text   = d.get("old_text", "")
            new_text   = d.get("new_text", "")
            start_line = d.get("start_line", 1)
            end_line   = d.get("end_line", None)

            yield {"type": "tool_call", "message": f"📁 {op}: {path or '(no path)'}"}

            if op == "read_file":
                receipt = file_read_verified(path)
            elif op == "read_lines":
                text_result = file_read_lines(path, start_line, end_line)
            elif op == "write_file":
                if not content:
                    content = generate_response(
                        f"Generate COMPLETE file content for: {query}",
                        provider="auto",
                        system_prompt=(
                            "Write complete file content only. "
                            "No explanation, no markdown fences."
                        ),
                    )
                receipt = file_write_verified(path, content)
            elif op == "append_file":
                receipt = file_append_verified(path, content)
            elif op == "patch_file":
                if old_text:
                    receipt = file_patch_verified(path, old_text, new_text)
                else:
                    receipt = FileReceipt(tool="file", operation="patch",
                                          error="patch_file requires old_text.")
            elif op == "list_files":
                text_result = file_list(path or ".", pattern)
            elif op == "tree":
                text_result = list_directory_tree(path or ".")
            elif op == "delete_file":
                receipt = file_delete_verified(path)
            elif op == "search_files":
                text_result = file_search(path or ".", fquery)
            elif op == "create_dir":
                receipt = create_directory_verified(path)
            else:
                receipt = FileReceipt(tool="file", operation=op,
                                      error=f"Unknown op: {op}")

        except Exception as e:
            receipt = FileReceipt(tool="file", operation="error", error=f"File error: {e}")

        if receipt is not None:
            yield {"type": "tool_result", "message": receipt.as_user_summary()}
            yield from self._synth_receipt(query, receipt)
        else:
            out_text = text_result or "(no output)"
            yield {"type": "tool_result", "message": str(out_text)[:400]}
            yield from self._synth_text(query, out_text)

    # ── Shell (verified) ─────────────────────────────────────────
    def _shell(self, query, mem_ctx, context, sp=""):
        from lirox.tools.shell_verified import shell_run_verified
        yield {"type": "agent_progress", "message": "💻 Planning shell command…"}

        raw = generate_response(
            f"Task: {query}\n"
            'Output ONLY JSON: {"command":"exact shell command","reason":"why",'
            '"working_dir":"~ or specific path or empty"}',
            provider="auto",
            system_prompt="Shell expert. Output ONLY JSON. Be precise.",
        )
        receipt = None
        try:
            d = _extract_json(raw)
            command = (d.get("command") or "").strip()
            reason  = (d.get("reason") or "").strip()
            cwd     = (d.get("working_dir") or "").strip()
            if not command:
                receipt = ShellReceipt(tool="shell", error="Could not determine command.")
                yield {"type": "tool_result", "message": receipt.as_user_summary()}
                yield from self._synth_receipt(query, receipt)
                return
            yield {"type": "tool_call", "message": f"$ {command}"}
            if reason:
                yield {"type": "agent_progress", "message": reason}
            receipt = shell_run_verified(command, cwd=cwd)
        except Exception as e:
            receipt = ShellReceipt(tool="shell", error=f"Shell error: {e}")

        yield {"type": "tool_result", "message": receipt.as_user_summary()}
        yield from self._synth_receipt(query, receipt)

    # ── Web ──────────────────────────────────────────────────────
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
            provider="auto", system_prompt=_get_sys(self.profile_data),
        )
        self.memory.save_exchange(query, final)
        for chunk in _STREAMER.stream_in_paragraphs(final):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": final}

    # ── Chat ─────────────────────────────────────────────────────
    def _chat(self, query, mem_ctx, context, system_prompt=""):
        base_sys = system_prompt or _get_sys(self.profile_data)
        prompt = f"Relevant context:\n{mem_ctx}\n\nUser: {query}" if mem_ctx and mem_ctx.strip() else query
        if context:
            prompt = f"Thinking:\n{context[:1500]}\n\n{prompt}"
        answer = generate_response(prompt, provider="auto", system_prompt=base_sys)
        self.memory.save_exchange(query, answer)
        for chunk in _STREAMER.stream_in_paragraphs(answer):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    # ── Memory (history / identity) ──────────────────────────────
    def _memory(self, query, mem_ctx, context, sp=""):
        from lirox.mind.agent import get_soul, get_learnings
        from lirox.memory.session_store import SessionStore

        q = query.lower()
        soul      = get_soul()
        learnings = get_learnings()
        agent_name = self.profile_data.get("agent_name", soul.get_name())
        user_name  = self.profile_data.get("user_name", "")

        blocks = []
        if any(kw in q for kw in ["who are you", "what are you", "introduce yourself",
                                    "tell me about yourself", "your name"]):
            blocks.append(
                f"YOUR IDENTITY (stored profile):\n"
                f"Name: {agent_name}\n"
                f"Role: Personal AI agent for {user_name or 'this user'}\n"
                f"Soul depth: {soul.state.get('interaction_count', 0)} interactions"
            )
        if any(kw in q for kw in ["what do you know", "about me", "what's my",
                                    "who am i", "what have you learned", "my name"]):
            facts_summary = learnings.get_facts_summary(n=10)
            topics = learnings.get_top_topics(5)
            topic_str = ", ".join(t["topic"] for t in topics) if topics else "none"
            blocks.append(
                f"WHAT I KNOW:\nFacts:\n{facts_summary}\n"
                f"Topics: {topic_str}\n"
                f"Projects: {', '.join(p['name'] for p in learnings.data.get('projects', [])[:3]) or 'none'}"
            )
        if any(kw in q for kw in ["last conversation", "previous", "what did we discuss",
                                    "our history", "last time", "remember when"]):
            store = SessionStore()
            sessions = store.list_sessions(limit=5)
            if sessions:
                lines = []
                for s in sessions[:3]:
                    msgs = [e.content[:100] for e in s.entries if e.role == "user"][:2]
                    if msgs:
                        lines.append(f"  Session '{s.name}' ({s.created_at[:10]}): " + " | ".join(msgs))
                blocks.append("SESSION HISTORY:\n" + "\n".join(lines))
            else:
                blocks.append("No previous sessions found.")

        factual_ctx = "\n\n".join(blocks) if blocks else "No specific data found."
        sys_prompt = _get_sys(self.profile_data)
        prompt = (
            f"USER QUERY: {query}\n\n"
            f"FACTUAL DATA (use ONLY this — do not invent):\n{factual_ctx}\n\n"
            "Answer using ONLY the data above. If missing, say so honestly."
        )
        answer = generate_response(prompt, provider="auto", system_prompt=sys_prompt)
        self.memory.save_exchange(query, answer)
        for chunk in _STREAMER.stream_in_paragraphs(answer):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    # ── Code ─────────────────────────────────────────────────────
    def _code(self, query, mem_ctx, context, sp=""):
        yield {"type": "agent_progress", "message": "💻 Writing code…"}
        sys_p = _get_sys(self.profile_data) + (
            "\n\nCODE RULES:\n"
            "• Write COMPLETE code. ALL imports. Error handling.\n"
            "• Include if __name__ == '__main__' demo.\n"
            "• Docstrings + type hints.\n"
            "• NEVER use '...' or placeholders."
        )
        prompt = f"Context:\n{mem_ctx}\n\nTask: {query}" if mem_ctx else query
        if context:
            prompt = f"Thinking:\n{context[:2000]}\n\n{prompt}"
        raw_answer = generate_response(prompt, provider="auto", system_prompt=sys_p)

        cm = re.search(r"```(?:python)?\n?([\s\S]+?)```", raw_answer)
        code_block = cm.group(1).strip() if cm else ""

        should_execute = (
            code_block and len(code_block) < 5000 and
            any(kw in query.lower() for kw in ["run", "execute", "test", "try", "demo", "show me"])
        )

        # Save path?
        save_path = ""
        for pat in [r"(?:save|write|create|store)(?:\s+\w+)?\s+(?:to|in|as|at)\s+([~/\w.\-/]+)",
                    r"in\s+(?:my\s+)?([~/\w\-]+(?:/[~/\w.\-]+)*\.[a-zA-Z0-9]+)"]:
            m = re.search(pat, query, re.IGNORECASE)
            if m:
                save_path = _resolve_target_path(m.group(1), query)
                break

        if save_path and code_block:
            from lirox.tools.file_tools import file_write_verified
            r = file_write_verified(save_path, code_block)
            yield {"type": "tool_result", "message": r.as_user_summary()}
            if r.verified and r.ok:
                raw_answer += f"\n\n**Verified saved to** `{r.details.get('resolved_path', save_path)}`"
            else:
                raw_answer += f"\n\n**Save failed:** {r.error or 'unknown error'}"

        if should_execute and code_block:
            yield {"type": "agent_progress", "message": "⚙️ Running code…"}
            try:
                from lirox.autonomy.code_executor import CodeExecutor
                res = CodeExecutor(timeout=15).execute(code_block)
                if res.success:
                    yield {"type": "tool_result", "message": "✅ Executed successfully"}
                    if res.stdout:
                        yield {"type": "tool_result", "message": f"Output:\n{res.stdout[:500]}"}
                    raw_answer += f"\n\n**Execution output:**\n```\n{res.stdout[:300]}\n```"
                else:
                    yield {"type": "tool_result",
                           "message": f"⚠ Failed: {res.error or res.stderr[:200]}"}
            except Exception:
                pass

        self.memory.save_exchange(query, raw_answer)
        for chunk in _STREAMER.stream_in_paragraphs(raw_answer):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": raw_answer}

    # ── Receipt-based synth (hallucination-proof) ─────────────────
    def _synth_receipt(self, query, receipt):
        """LLM summarizer that reads the receipt status — cannot claim success without verification."""
        ctx = receipt.as_llm_context()
        if receipt.verified and receipt.ok:
            prompt = (
                f"User asked: {query}\n\n"
                f"Tool receipt:\n{ctx}\n\n"
                "Confirm briefly what was done. Reference the verified result. "
                "If a file was written include the path. Max 3 sentences."
            )
        else:
            prompt = (
                f"User asked: {query}\n\n"
                f"Tool receipt:\n{ctx}\n\n"
                "The operation did NOT succeed. Tell the user honestly what failed "
                "and give the error. Suggest one concrete fix. Do NOT claim success. "
                "Max 3 sentences."
            )
        answer = generate_response(prompt, provider="auto",
                                    system_prompt=_get_sys(self.profile_data))
        self.memory.save_exchange(query, answer)
        for chunk in _STREAMER.stream_in_paragraphs(answer):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    def _synth_text(self, query, text_result):
        """Used only for read-only ops (list, tree, search) — no state to verify."""
        prompt = (
            f"Task: {query}\nTool output:\n{text_result}\n\n"
            "Summarize the output for the user. Be concise and factual."
        )
        answer = generate_response(prompt, provider="auto",
                                    system_prompt=_get_sys(self.profile_data))
        self.memory.save_exchange(query, answer)
        for chunk in _STREAMER.stream_in_paragraphs(answer):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    # ── Legacy synth (kept for any callers that still reference it) ─
    def _synth(self, query, result):
        """Legacy string-result synth — routes through receipt path for consistency."""
        if isinstance(result, str) and (result.startswith("❌") or "error" in result.lower()):
            r = FileReceipt(tool="file", operation="unknown", error=result)
            yield from self._synth_receipt(query, r)
        else:
            yield from self._synth_text(query, result)
