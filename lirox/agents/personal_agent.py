"""Lirox v3.0 — PersonalAgent

One unified agent. Real file operations. Real shell execution.
Self-aware (can read its own source). Learns from user.
All operations verified on disk. No virtual/fake results.
"""
from __future__ import annotations

import json as _json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Generator

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.utils.llm import generate_response
from lirox.utils.streaming import StreamingResponse
from lirox.verify import FileReceipt, ShellReceipt

_STREAMER = StreamingResponse()


def _get_sys(profile_data: dict = None) -> str:
    profile_data = profile_data or {}
    agent_name = profile_data.get("agent_name", "Lirox")
    user_name  = profile_data.get("user_name", "")

    try:
        from lirox.mind.soul import LivingSoul
        from lirox.mind.learnings import LearningsStore
        soul = LivingSoul()
        learnings = LearningsStore()
        base = soul.to_system_prompt(learnings.to_context_string())
    except Exception:
        base = (f"You are {agent_name}, a personal AI agent "
                f"{'for ' + user_name if user_name else ''}. "
                "You are direct, capable, and deeply personalized.")

    profile_lines = []
    for key, label in [("user_name", "User"), ("niche", "Work"),
                       ("current_project", "Project"), ("profession", "Profession")]:
        val = profile_data.get(key, "")
        if val and val not in ("Operator", "Generalist"):
            profile_lines.append(f"• {label}: {val}")
    if profile_lines and "USER PROFILE" not in base:
        base += "\n\nUSER PROFILE:\n" + "\n".join(profile_lines)

    goals = profile_data.get("goals", [])
    if goals:
        base += "\n\nGOALS:\n" + "\n".join(f"• {g}" for g in goals[:5])

    base += (
        "\n\nCRITICAL RULES:\n"
        "• You have FULL filesystem access. Never say you cannot access it.\n"
        "• When asked to create/write/edit files — DO IT. Do not describe how.\n"
        "• When writing code — write the COMPLETE implementation.\n"
        "• When a tool receipt says VERIFIED you may confirm success.\n"
        "  When it says FAILED you MUST report failure honestly.\n"
        "• Address the user by name when known.\n"
    )
    return base


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try: return _json.loads(m.group(1))
        except Exception: pass
    depth = 0; start = None
    for i, ch in enumerate(text):
        if ch == "{":
            if start is None: start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try: return _json.loads(text[start:i + 1])
                except: start = None; depth = 0
    raise ValueError("No JSON in LLM response")


def _resolve_path(raw: str, query: str) -> str:
    if not raw: return ""
    from lirox.config import WORKSPACE_DIR
    p = os.path.expandvars(os.path.expanduser(raw))
    if os.path.isabs(p): return p
    if "/" in p or "\\" in p: return os.path.abspath(p)
    # Bare filename → use workspace dir
    q = (query or "").lower()
    if "downloads" in q:   folder = "~/Downloads"
    elif "documents" in q: folder = "~/Documents"
    elif "desktop" in q:   folder = "~/Desktop"
    else:                  folder = WORKSPACE_DIR
    return os.path.abspath(os.path.expanduser(os.path.join(folder, p)))


# ── Signal detection ──

FILE_SIGNALS = [
    "read file", "write file", "create file", "edit file", "delete file",
    "save to", "open file", "file contents", "in my ", "in the ",
    "folder", "directory", ".py", ".js", ".md", ".txt", ".json", ".csv",
    "readme", "list files", "show files", "what files", "find files",
    "on my desktop", "in downloads", "in documents", "save as", "write to",
    "tree", "structure",
]

SHELL_SIGNALS = [
    "run command", "execute command", "in the terminal", "in bash",
    "run python", "git status", "git commit", "git push", "git pull",
    "npm install", "pip install", "docker run", "docker build",
    "start server", "pytest ", "cargo run", "make test", "ls ",
]

WEB_SIGNALS = [
    "search for", "look up", "find information", "google", "latest news",
    "research", "find out about", "current price", "news about",
]

SELF_SIGNALS = [
    "your code", "your source", "how do you work", "your architecture",
    "your files", "read your", "lirox code", "understand yourself",
]

MEMORY_SIGNALS = [
    "last conversation", "what did we discuss", "what do you know about me",
    "what's my name", "who am i", "who are you", "introduce yourself",
    "what have you learned", "remember when", "our history",
]


def _classify(query: str) -> str:
    q = query.lower()
    if any(s in q for s in SELF_SIGNALS):   return "self"
    if any(s in q for s in MEMORY_SIGNALS): return "memory"
    if any(s in q for s in FILE_SIGNALS):   return "file"
    if any(s in q for s in SHELL_SIGNALS):  return "shell"
    if any(s in q for s in WEB_SIGNALS):    return "web"
    return "chat"


class PersonalAgent(BaseAgent):
    @property
    def name(self) -> str: return "personal"

    def run(self, query: str, system_prompt: str = "",
            context: str = "", mode: str = "auto") -> Generator[AgentEvent, None, None]:
        task = _classify(query)
        dispatch = {
            "self":   self._self,
            "file":   self._file,
            "shell":  self._shell,
            "web":    self._web,
            "memory": self._memory,
            "chat":   self._chat,
        }
        yield from dispatch.get(task, self._chat)(query, context, system_prompt)

    # ── Chat ──
    def _chat(self, query, context, sp=""):
        base_sys = sp or _get_sys(self.profile_data)
        mem_ctx = self.memory.get_relevant_context(query)
        prompt = query
        if mem_ctx and mem_ctx.strip():
            prompt = f"Relevant context:\n{mem_ctx}\n\nUser: {query}"
        if context:
            prompt = f"Context:\n{context[:1500]}\n\n{prompt}"
        answer = generate_response(prompt, provider="auto", system_prompt=base_sys)
        self.memory.save_exchange(query, answer)
        for chunk in _STREAMER.stream_in_paragraphs(answer):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    # ── File (REAL operations, verified on disk) ──
    def _file(self, query, context, sp=""):
        from lirox.tools.file_tools import (
            file_read_verified, file_write_verified, file_list,
            file_delete_verified, file_search, file_patch_verified,
            file_read_lines, create_directory_verified,
            file_append_verified, list_directory_tree,
        )
        yield {"type": "agent_progress", "message": "📁 Planning file operation…"}

        from lirox.config import WORKSPACE_DIR
        plan_prompt = (
            f"Task: {query}\n"
            f"Default workspace: {WORKSPACE_DIR}\n\n"
            "Determine the EXACT file operation. For write/create: include COMPLETE content.\n"
            "Use absolute paths or ~/relative. Reflect user intent (desktop, downloads, etc).\n\n"
            'Output ONLY JSON:\n'
            '{"op":"read_file|write_file|append_file|patch_file|list_files|tree|'
            'delete_file|search_files|create_dir",'
            '"path":"absolute or ~/path",'
            '"content":"complete file content if writing",'
            '"old_text":"text to replace (patch)",'
            '"new_text":"replacement (patch)",'
            '"pattern":"*","query":"search term"}'
        )
        raw = generate_response(plan_prompt, provider="auto",
                                system_prompt="File planner. Output ONLY valid JSON.")

        receipt = None; text_result = None
        try:
            d = _extract_json(raw)
            op = (d.get("op") or "").lower()
            if not op:
                q2 = query.lower()
                if any(w in q2 for w in ["create","write","make","save"]): op = "write_file"
                elif any(w in q2 for w in ["read","show","open","cat"]): op = "read_file"
                elif any(w in q2 for w in ["list","ls","files in"]): op = "list_files"
                elif any(w in q2 for w in ["tree","structure"]): op = "tree"
                elif any(w in q2 for w in ["delete","remove"]): op = "delete_file"
                elif any(w in q2 for w in ["search","find","grep"]): op = "search_files"
                else: op = "list_files"

            path = _resolve_path(d.get("path", ""), query)
            content = d.get("content", "")
            yield {"type": "tool_call", "message": f"📁 {op}: {path or '(workspace)'}"}

            if op == "read_file":
                receipt = file_read_verified(path)
                if receipt.ok and receipt.verified:
                    file_content = receipt.details.get("content", "")
                    yield {"type": "tool_result", "message": f"📄 Read {receipt.bytes_read} bytes from {path}"}
                    # Show actual content to user
                    answer = f"📄 **{path}** ({receipt.lines} lines, {receipt.bytes_read} bytes):\n\n```\n{file_content[:3000]}\n```"
                    if receipt.details.get("truncated"):
                        answer += "\n\n*(truncated — file is larger)*"
                    self.memory.save_exchange(query, answer)
                    for chunk in _STREAMER.stream_in_paragraphs(answer):
                        yield {"type": "streaming", "message": chunk}
                    yield {"type": "done", "answer": answer}
                    return

            elif op == "write_file":
                if not content:
                    content = generate_response(
                        f"Generate COMPLETE file content for: {query}",
                        provider="auto",
                        system_prompt="Write complete file content only. No explanation, no fences.")
                receipt = file_write_verified(path, content)

            elif op == "append_file":
                receipt = file_append_verified(path, content)

            elif op == "patch_file":
                old_text = d.get("old_text", "")
                new_text = d.get("new_text", "")
                if old_text:
                    receipt = file_patch_verified(path, old_text, new_text)
                else:
                    receipt = FileReceipt(tool="file", operation="patch",
                                          error="patch_file requires old_text")

            elif op == "list_files":
                text_result = file_list(path or ".", d.get("pattern", "*"))

            elif op == "tree":
                text_result = list_directory_tree(path or ".")

            elif op == "delete_file":
                receipt = file_delete_verified(path)

            elif op == "search_files":
                text_result = file_search(path or ".", d.get("query", query))

            elif op == "create_dir":
                receipt = create_directory_verified(path)

        except Exception as e:
            receipt = FileReceipt(tool="file", operation="error", error=f"File error: {e}")

        if receipt is not None:
            yield {"type": "tool_result", "message": receipt.as_user_summary()}
            yield from self._synth_receipt(query, receipt)
        else:
            yield {"type": "tool_result", "message": str(text_result)[:400]}
            yield from self._synth_text(query, text_result or "(no output)")

    # ── Shell (REAL execution) ──
    def _shell(self, query, context, sp=""):
        from lirox.tools.shell_verified import shell_run_verified
        yield {"type": "agent_progress", "message": "💻 Planning command…"}
        raw = generate_response(
            f"Task: {query}\n"
            'Output ONLY JSON: {{"command":"exact shell command","reason":"why",'
            '"working_dir":"~ or path or empty"}}',
            provider="auto", system_prompt="Shell expert. Output ONLY JSON.")
        try:
            d = _extract_json(raw)
            command = (d.get("command") or "").strip()
            if not command:
                yield {"type": "tool_result", "message": "❌ Could not determine command."}
                yield from self._chat(query, context, sp)
                return
            yield {"type": "tool_call", "message": f"$ {command}"}
            receipt = shell_run_verified(command, cwd=d.get("working_dir", ""))
        except Exception as e:
            receipt = ShellReceipt(tool="shell", error=f"Shell error: {e}")
        yield {"type": "tool_result", "message": receipt.as_user_summary()}
        yield from self._synth_receipt(query, receipt)

    # ── Web ──
    def _web(self, query, context, sp=""):
        yield {"type": "agent_progress", "message": "🌐 Searching…"}
        try:
            from lirox.tools.search.duckduckgo import search_ddg
            results = search_ddg(query)
            yield {"type": "tool_result", "message": f"Found results for: {query[:80]}"}
        except Exception as e:
            results = f"Search failed: {e}"
        answer = generate_response(
            f"Query: {query}\nResults:\n{str(results)[:6000]}\nComprehensive answer:",
            provider="auto", system_prompt=_get_sys(self.profile_data))
        self.memory.save_exchange(query, answer)
        for chunk in _STREAMER.stream_in_paragraphs(answer):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    # ── Self-awareness (reads own source code) ──
    def _self(self, query, context, sp=""):
        from lirox.config import LIROX_SOURCE_DIR
        yield {"type": "agent_progress", "message": "📖 Reading own source code…"}
        source_dir = Path(LIROX_SOURCE_DIR)
        file_map = {}
        for p in sorted(source_dir.rglob("*.py")):
            if "__pycache__" in str(p): continue
            try:
                rel = str(p.relative_to(source_dir.parent))
                file_map[rel] = p.read_text(errors="replace")[:2000]
            except Exception:
                continue
        summary = "\n".join(
            f"### {k}\n```python\n{v[:500]}\n```" for k, v in list(file_map.items())[:15])
        answer = generate_response(
            f"Query: {query}\n\nMy own source code:\n{summary}\n\nAnswer from actual code.",
            provider="auto", system_prompt=_get_sys(self.profile_data))
        self.memory.save_exchange(query, answer)
        for chunk in _STREAMER.stream_in_paragraphs(answer):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    # ── Memory/Identity ──
    def _memory(self, query, context, sp=""):
        from lirox.mind.soul import LivingSoul
        from lirox.mind.learnings import LearningsStore
        from lirox.memory.session_store import SessionStore

        soul = LivingSoul(); learnings = LearningsStore()
        agent_name = self.profile_data.get("agent_name", soul.get_name())
        user_name  = self.profile_data.get("user_name", "")
        q = query.lower()
        blocks = []

        if any(kw in q for kw in ["who are you", "what are you", "introduce yourself"]):
            blocks.append(f"YOUR IDENTITY:\nName: {agent_name}\n"
                          f"Role: Personal AI for {user_name or 'this user'}\n"
                          f"Interactions: {soul.state.get('interaction_count', 0)}")

        if any(kw in q for kw in ["what do you know", "about me", "my name", "who am i"]):
            facts = learnings.get_facts_summary(n=10)
            topics = learnings.get_top_topics(5)
            topic_str = ", ".join(t["topic"] for t in topics) if topics else "none"
            blocks.append(f"WHAT I KNOW:\n{facts}\nTopics: {topic_str}")

        if any(kw in q for kw in ["last conversation", "previous", "our history"]):
            store = SessionStore()
            sessions = store.list_sessions(limit=3)
            if sessions:
                lines = []
                for s in sessions:
                    msgs = [e.content[:100] for e in s.entries if e.role == "user"][:2]
                    if msgs:
                        lines.append(f"  Session '{s.name}' ({s.created_at[:10]}): " + " | ".join(msgs))
                blocks.append("HISTORY:\n" + "\n".join(lines))

        factual = "\n\n".join(blocks) if blocks else "No data found."
        answer = generate_response(
            f"USER QUERY: {query}\n\nFACTUAL DATA:\n{factual}\n\n"
            "Answer using ONLY the data above. If missing, say so honestly.",
            provider="auto", system_prompt=_get_sys(self.profile_data))
        self.memory.save_exchange(query, answer)
        for chunk in _STREAMER.stream_in_paragraphs(answer):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    # ── Receipt synthesizers ──
    def _synth_receipt(self, query, receipt):
        ctx = receipt.as_llm_context()
        if receipt.verified and receipt.ok:
            prompt = (f"User asked: {query}\n\nTool receipt:\n{ctx}\n\n"
                      "Confirm briefly what was done. Include path if file was written. Max 3 sentences.")
        else:
            prompt = (f"User asked: {query}\n\nTool receipt:\n{ctx}\n\n"
                      "Operation FAILED. Tell user what failed and suggest a fix. Max 3 sentences.")
        answer = generate_response(prompt, provider="auto", system_prompt=_get_sys(self.profile_data))
        self.memory.save_exchange(query, answer)
        for chunk in _STREAMER.stream_in_paragraphs(answer):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    def _synth_text(self, query, text_result):
        prompt = f"Task: {query}\nTool output:\n{text_result}\n\nSummarize concisely."
        answer = generate_response(prompt, provider="auto", system_prompt=_get_sys(self.profile_data))
        self.memory.save_exchange(query, answer)
        for chunk in _STREAMER.stream_in_paragraphs(answer):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}
