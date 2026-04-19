"""Lirox v3.1.1 — PersonalAgent (Advanced Reasoning & Execution)

One unified agent. Real file operations. Real shell execution.
Self-aware (can read its own source). Learns from user.
All operations verified on disk. No virtual/fake results.

v3.1.1 UPGRADE:
  - Advanced signal routing with multi-layer classification
  - Follow-up context tracking (remembers last task)
  - Anti-hallucination guard: NEVER claims success without tool receipt
  - Auto-redirect: chat detects action requests and dispatches tools
  - Filegen fallback in _file when document formats detected
  - Richer LLM planning prompts for higher-quality output
"""
from __future__ import annotations

import json as _json
import os
import re as _re
import time
from pathlib import Path
from typing import Any, Dict, Generator, Optional

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.utils.llm import generate_response
from lirox.utils.streaming import StreamingResponse
from lirox.verify import FileReceipt, ShellReceipt

_STREAMER = StreamingResponse()


# ═══════════════════════════════════════════════════════════════════
# SYSTEM PROMPT — Anti-hallucination + Advanced reasoning
# ═══════════════════════════════════════════════════════════════════

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
        "• When asked to create/write/edit files — DO IT using tools. Do not describe how.\n"
        "• When writing code — write the COMPLETE implementation.\n"
        "• When a tool receipt says VERIFIED you may confirm success.\n"
        "  When it says FAILED you MUST report failure honestly.\n"
        "• NEVER say 'I have created' or 'The file has been created' unless a tool receipt confirms it.\n"
        "• NEVER hallucinate creating files. If you didn't use a tool to create it, IT DOES NOT EXIST.\n"
        "• If the user asks you to CREATE something (file, document, presentation), you MUST use tools.\n"
        "  Simply describing what you would create is NOT acceptable.\n"
        "• Address the user by name when known.\n"
        "• Think step-by-step: understand the task → plan the action → execute with tools → verify result.\n"
    )
    return base


# ═══════════════════════════════════════════════════════════════════
# JSON EXTRACTION
# ═══════════════════════════════════════════════════════════════════

def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    from lirox.utils.regex_cache import JSON_FENCE
    m = JSON_FENCE.search(text)
    if m:
        try:
            return _json.loads(m.group(1))
        except _json.JSONDecodeError:
            pass
    for start_idx in range(len(text)):
        if text[start_idx] != '{':
            continue
        depth = 0
        in_string = False
        i = start_idx
        while i < len(text):
            ch = text[i]
            if ch == '"' and in_string:
                num_backslashes = 0
                j = i - 1
                while j >= start_idx and text[j] == '\\':
                    num_backslashes += 1
                    j -= 1
                if num_backslashes % 2 == 0:
                    in_string = False
            elif ch == '"' and not in_string:
                in_string = True
            if not in_string:
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            return _json.loads(text[start_idx:i + 1])
                        except _json.JSONDecodeError:
                            break
            i += 1
    raise ValueError("No JSON in LLM response")


# ═══════════════════════════════════════════════════════════════════
# PATH RESOLUTION
# ═══════════════════════════════════════════════════════════════════

def _resolve_path(raw: str, query: str) -> str:
    if not raw:
        return ""
    from lirox.config import WORKSPACE_DIR, SAFE_DIRS_RESOLVED, PROTECTED_PATHS
    from lirox.utils.input_sanitizer import sanitize_path
    raw = sanitize_path(raw)
    p = os.path.expandvars(os.path.expanduser(raw))
    if os.path.isabs(p) or "/" in p or "\\" in p:
        canonical = os.path.realpath(p)
    else:
        q = (query or "").lower()
        if "downloads" in q:   folder = "~/Downloads"
        elif "documents" in q: folder = "~/Documents"
        elif "desktop" in q:   folder = "~/Desktop"
        else:                  folder = WORKSPACE_DIR
        canonical = os.path.realpath(os.path.expanduser(os.path.join(folder, p)))

    for protected in PROTECTED_PATHS:
        protected_real = os.path.realpath(protected)
        if canonical.startswith(protected_real + os.sep) or canonical == protected_real:
            raise PermissionError(f"Access denied: {protected} is a protected path")

    if not any(
        canonical == safe or canonical.startswith(safe + os.sep)
        for safe in SAFE_DIRS_RESOLVED
    ):
        allowed_dirs = ", ".join(SAFE_DIRS_RESOLVED)
        raise PermissionError(
            f"Path '{canonical}' is outside permitted directories. "
            f"Allowed: {allowed_dirs}."
        )

    return canonical


# ═══════════════════════════════════════════════════════════════════
# ADVANCED SIGNAL CLASSIFICATION (Multi-layer)
# ═══════════════════════════════════════════════════════════════════

SHELL_SIGNALS = [
    "run command", "execute command", "in the terminal", "in bash",
    "run python", "git status", "git commit", "git push", "git pull",
    "npm install", "pip install", "docker run", "docker build",
    "start server", "pytest ", "cargo run", "make test", "ls ",
]

WEB_SIGNALS = [
    "search for", "look up", "find information", "google", "latest news",
    "research", "find out about", "current price", "news about",
    "what is in the news", "trending", "who won",
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

# Document format keywords — used for filegen detection
_DOC_FORMATS = {"pdf", "word", "docx", "excel", "xlsx", "pptx", "powerpoint",
                "ppt", "spreadsheet", "presentation", "slide", "slides"}

# Action verbs that signal creation
_ACTION_VERBS = {"create", "make", "generate", "build", "prepare", "write", "produce", "draft"}

# Follow-up patterns (user agrees or re-requests)
_FOLLOWUP_PATTERNS = _re.compile(
    r"^(?:ok\s+)?(?:yes|yeah|yep|sure|go\s*ahead|do\s*it|create\s*it|make\s*it|"
    r"build\s*it|generate\s*it|just\s*(?:create|make|do)\s*it|"
    r"ok\s*(?:create|make|good\s*create|its?\s*good\s*create))",
    _re.IGNORECASE,
)


def _classify(query: str) -> str:
    """Multi-layer signal classification with follow-up awareness."""
    q = query.lower().strip()
    words = set(q.split())

    # ─── Layer 1: Self-awareness (highest priority, very specific) ───
    if any(s in q for s in SELF_SIGNALS):
        return "self"

    # ─── Layer 2: Memory/identity (specific phrases) ───
    if any(s in q for s in MEMORY_SIGNALS):
        return "memory"

    # ─── Layer 3: File generation (document formats + action verbs) ───
    # Check 3a: Regex for "create/make/generate + document format"
    if _re.search(
        r'\b(?:create|make|generate|build|prepare|write|produce|draft)\b'
        r'.*\b(?:pdf|word|docx|excel|xlsx|pptx|powerpoint|ppt|spreadsheet|'
        r'presentation|slides?|report|resume|cv)\b', q
    ):
        return "filegen"

    # Check 3b: Simple word intersection — action verb + doc format anywhere
    if words & _ACTION_VERBS and words & _DOC_FORMATS:
        return "filegen"

    # Check 3c: Doc format mentioned with filename-like patterns
    if _re.search(r'\.\s*(?:pdf|docx|xlsx|pptx)\b', q):
        if words & _ACTION_VERBS:
            return "filegen"

    # ─── Layer 4: Shell (specific tool/command mentions) ───
    if any(s in q for s in SHELL_SIGNALS):
        return "shell"

    # ─── Layer 5: Web search (specific phrases) ───
    if any(s in q for s in WEB_SIGNALS):
        return "web"

    # ─── Layer 6: File ops — word-boundary checks for ambiguous signals ───
    _EXACT_FILE_SIGNALS = [
        "read file", "write file", "create file", "edit file", "delete file",
        "save to", "open file", "file contents", "folder", "directory",
        "list files", "show files", "what files", "find files",
        "on my desktop", "in downloads", "in documents", "save as", "write to",
        "tree", "structure",
    ]
    _EXT_SIGNALS = [".py", ".js", ".md", ".txt", ".json", ".csv", ".html", ".css", ".ts"]
    if any(s in q for s in _EXACT_FILE_SIGNALS):
        return "file"
    for ext in _EXT_SIGNALS:
        if _re.search(r'\w' + _re.escape(ext) + r'\b', q):
            return "file"

    # ─── Layer 7: Follow-up detection (returns "followup" for dispatch) ───
    if _FOLLOWUP_PATTERNS.search(q):
        return "followup"

    return "chat"


# ═══════════════════════════════════════════════════════════════════
# PERSONAL AGENT (Advanced Reasoning + Execution)
# ═══════════════════════════════════════════════════════════════════

class PersonalAgent(BaseAgent):
    def __init__(self, memory=None, profile_data=None):
        super().__init__(memory=memory, profile_data=profile_data)
        # Context tracking for intelligent follow-ups
        self._last_task: Optional[str] = None       # "filegen", "file", "shell", etc.
        self._last_query: Optional[str] = None      # The original query
        self._last_context: Optional[str] = None    # Extra context

    @property
    def name(self) -> str: return "personal"

    def run(self, query: str, system_prompt: str = "",
            context: str = "", mode: str = "auto") -> Generator[AgentEvent, None, None]:
        from lirox.utils.input_sanitizer import sanitize
        query = sanitize(query)
        task = _classify(query)

        # ── Follow-up handling: re-dispatch to last task ──
        if task == "followup" and self._last_task and self._last_query:
            # User said "ok create it" or "do it" → re-run last task with original query
            task = self._last_task
            # Augment the query with the original context
            query = f"{query} — Original request: {self._last_query}"

        # ── Chat guard: detect action requests that slipped through ──
        if task == "chat":
            task = self._chat_action_guard(query, task)

        dispatch = {
            "self":    self._self,
            "file":    self._file,
            "filegen": self._filegen,
            "shell":   self._shell,
            "web":     self._web,
            "memory":  self._memory,
            "chat":    self._chat,
        }

        # Save task context for follow-ups (before dispatching)
        if task in ("filegen", "file", "shell", "web"):
            self._last_task = task
            self._last_query = query
            self._last_context = context

        yield from dispatch.get(task, self._chat)(query, context, system_prompt)

    def _chat_action_guard(self, query: str, current_task: str) -> str:
        """Detect action requests that slipped past signal classification.

        If the user is asking to CREATE/MAKE something that involves a document,
        redirect to the appropriate handler instead of letting chat hallucinate.
        """
        q = query.lower()

        # Check for document creation intent with fuzzy matching
        doc_words = ["pdf", "word", "docx", "excel", "xlsx", "pptx", "ppt",
                     "powerpoint", "presentation", "spreadsheet", "slide",
                     "resume", "report", "cv", "document"]
        action_words = ["create", "make", "generate", "build", "write", "prepare",
                        "draft", "produce"]

        has_doc = any(w in q for w in doc_words)
        has_action = any(w in q for w in action_words)

        if has_doc and has_action:
            return "filegen"

        # Check for file creation intent
        file_words = [".py", ".js", ".html", ".css", ".ts", ".md", ".txt",
                      ".json", ".csv", "file", "script", "code"]
        if any(w in q for w in file_words) and has_action:
            return "file"

        return current_task

    # ═══════════════════════════════════════════════════════════════
    # CHAT — with action detection
    # ═══════════════════════════════════════════════════════════════

    def _chat(self, query, context, sp=""):
        base_sys = sp or _get_sys(self.profile_data)
        mem_ctx = self.memory.get_relevant_context(query)
        prompt = query
        if mem_ctx and mem_ctx.strip():
            prompt = f"Relevant context:\n{mem_ctx}\n\nUser: {query}"
        if context:
            prompt = f"Context:\n{context[:1500]}\n\n{prompt}"
        answer = generate_response(prompt, provider="auto", system_prompt=base_sys)
        for chunk in _STREAMER.stream_words(answer, delay=0.01):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    # ═══════════════════════════════════════════════════════════════
    # FILE GENERATION (PDF/Word/Excel/PPT) — Advanced
    # ═══════════════════════════════════════════════════════════════

    def _filegen(self, query, context, sp=""):
        from lirox.tools.file_generator import create_pdf, create_docx, create_xlsx, create_pptx
        from lirox.config import OUTPUTS_DIR

        yield {"type": "agent_progress", "message": "📄 Planning document generation…"}

        # Detect output directory from query
        output_dir = OUTPUTS_DIR
        q_lower = query.lower()
        if "desktop" in q_lower:
            output_dir = os.path.expanduser("~/Desktop")
        elif "documents" in q_lower:
            output_dir = os.path.expanduser("~/Documents")
        elif "downloads" in q_lower:
            output_dir = os.path.expanduser("~/Downloads")

        # Detect file type from query
        if "pdf" in q_lower:
            default_type = "pdf"
        elif any(w in q_lower for w in ["word", "docx", "resume", "cv"]):
            default_type = "docx"
        elif any(w in q_lower for w in ["excel", "xlsx", "spreadsheet"]):
            default_type = "xlsx"
        elif any(w in q_lower for w in ["ppt", "pptx", "powerpoint", "presentation", "slide"]):
            default_type = "pptx"
        else:
            default_type = "pdf"

        # Detect custom filename from query
        name_match = _re.search(r'(?:name|named|called|filename)\s+["\']?(\w[\w\s.-]*)', q_lower)
        custom_name = name_match.group(1).strip().rstrip('.') if name_match else None

        # Detect page/slide count
        count_match = _re.search(r'(\d+)\s*(?:pages?|slides?|sheets?)', q_lower)
        page_count = int(count_match.group(1)) if count_match else 6

        plan_prompt = (
            f"Task: {query}\n"
            f"File type: {default_type}\n"
            f"Output directory: {output_dir}\n"
            f"Page/slide count requested: {page_count}\n\n"
            "You MUST generate COMPLETE, rich, detailed content. "
            "Do NOT use placeholders like 'Add content here' or '[Image description]'. "
            "Write REAL paragraphs with REAL information.\n\n"
            'Output ONLY valid JSON with this structure:\n'
            '{\n'
            f'  "file_type": "{default_type}",\n'
            f'  "filename": "{custom_name or "descriptive_name"}.{default_type}",\n'
            '  "title": "Document Title",\n'
        )

        if default_type in ("pdf", "docx"):
            plan_prompt += (
                f'  "sections": [\n'
                f'    {{"heading": "Section Title", "body": "Multiple detailed paragraphs...", '
                f'"bullets": ["Key point 1", "Key point 2", "Key point 3"]}}\n'
                f'  ]  // Generate {page_count} sections with RICH content\n'
                '}\n'
            )
        elif default_type == "xlsx":
            plan_prompt += (
                '  "sheets": [\n'
                '    {"name": "Sheet1", "headers": ["Col A", "Col B", "Col C"], '
                '"rows": [["val1", "val2", "val3"], ...]}\n'
                f'  ]  // Generate meaningful data with at least 10 rows\n'
                '}\n'
            )
        elif default_type == "pptx":
            plan_prompt += (
                '  "slides": [\n'
                '    {"title": "Slide Title", "bullets": ["Point 1", "Point 2", "Point 3", "Point 4"], '
                '"notes": "speaker notes"}\n'
                f'  ]  // Generate EXACTLY {page_count} slides with 4-5 bullets each\n'
                '}\n'
            )

        plan_prompt += (
            "\nIMPORTANT: Generate ALL content now. Each section/slide must have REAL, detailed content. "
            "Never use placeholder text. Output ONLY the JSON, nothing else."
        )

        raw = generate_response(plan_prompt, provider="auto",
                                system_prompt="You are a document generation planner. "
                                "Output ONLY valid JSON. Generate rich, detailed content. "
                                "Never use placeholders.")

        try:
            d = _extract_json(raw)
            file_type = (d.get("file_type") or default_type).lower().strip()
            filename = d.get("filename", "")

            # Ensure valid file type
            ext_map = {"pdf": ".pdf", "docx": ".docx", "xlsx": ".xlsx", "pptx": ".pptx"}
            if file_type not in ext_map:
                file_type = default_type

            # Build filename
            if custom_name:
                filename = custom_name
            elif not filename:
                filename = f"output_{int(time.time())}"

            # Ensure correct extension
            if not filename.endswith(ext_map[file_type]):
                # Remove wrong extension if present
                for ext in ext_map.values():
                    if filename.endswith(ext):
                        filename = filename[:-len(ext)]
                        break
                filename = filename + ext_map[file_type]

            # Detect custom output path from query
            path = os.path.join(output_dir, filename)

            # Check if user specified a folder name in the query
            folder_match = _re.search(
                r'(?:in|into|to|inside)\s+(?:my\s+)?(?:the\s+)?'
                r'(?:desktop|downloads|documents)?\s*(?:/|\\)?'
                r'(?:folder\s+)?["\'`]?(\w[\w\s.-]*)["\'`]?\s*(?:folder)?',
                q_lower
            )
            if folder_match:
                folder_name = folder_match.group(1).strip()
                # Check if it's a known location keyword
                if folder_name not in ("desktop", "documents", "downloads", "folder", "directory"):
                    potential_path = os.path.join(output_dir, folder_name)
                    if os.path.isdir(potential_path):
                        path = os.path.join(potential_path, filename)

            yield {"type": "tool_call", "message": f"📄 Creating {file_type.upper()}: {filename}"}

            if file_type == "pdf":
                receipt = create_pdf(path, d.get("title", "Untitled"), d.get("sections", []))
            elif file_type == "docx":
                receipt = create_docx(path, d.get("title", "Untitled"), d.get("sections", []))
            elif file_type == "xlsx":
                receipt = create_xlsx(path, d.get("title", "Untitled"), d.get("sheets", []))
            elif file_type == "pptx":
                receipt = create_pptx(path, d.get("title", "Untitled"), d.get("slides", []))
            else:
                receipt = FileReceipt(tool="file_generator", error=f"Unknown type: {file_type}")

        except Exception as e:
            receipt = FileReceipt(tool="file_generator", operation="error",
                                  error=f"File generation error: {e}")

        yield {"type": "tool_result", "message": receipt.as_user_summary()}
        yield from self._synth_receipt(query, receipt)

    # ═══════════════════════════════════════════════════════════════
    # FILE (REAL operations, verified on disk)
    # ═══════════════════════════════════════════════════════════════

    def _file(self, query, context, sp=""):
        from lirox.tools.file_tools import (
            file_read_verified, file_write_verified, file_list,
            file_delete_verified, file_search, file_patch_verified,
            file_read_lines, create_directory_verified,
            file_append_verified, list_directory_tree,
        )

        # ── Filegen redirect guard ──
        # If the user is asking to create a document file, redirect to _filegen
        q_lower = query.lower()
        doc_exts = [".pdf", ".docx", ".xlsx", ".pptx", ".ppt", ".doc", ".xls"]
        doc_words = ["pdf", "word document", "powerpoint", "presentation",
                     "spreadsheet", "excel", "slide"]
        if any(ext in q_lower for ext in doc_exts) or any(w in q_lower for w in doc_words):
            action_words = ["create", "make", "generate", "build", "write", "prepare"]
            if any(w in q_lower for w in action_words):
                yield from self._filegen(query, context, sp)
                return

        yield {"type": "agent_progress", "message": "📁 Planning file operation…"}

        from lirox.config import WORKSPACE_DIR
        plan_prompt = (
            f"Task: {query}\n"
            f"Default workspace: {WORKSPACE_DIR}\n\n"
            "Determine the EXACT file operation. For write/create: include COMPLETE content.\n"
            "Use absolute paths or ~/relative. Reflect user intent (desktop, downloads, etc).\n\n"
            "IMPORTANT: If the user wants to create a text file, script, or code file,\n"
            "use write_file with the COMPLETE content. Never create an empty file.\n\n"
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
                                system_prompt="File operation planner. Output ONLY valid JSON. "
                                "For write operations, generate COMPLETE file content.")

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
                    answer = f"📄 **{path}** ({receipt.lines} lines, {receipt.bytes_read} bytes):\n\n```\n{file_content[:3000]}\n```"
                    if receipt.details.get("truncated"):
                        answer += "\n\n*(truncated — file is larger)*"
                    for chunk in _STREAMER.stream_words(answer, delay=0.01):
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

    # ═══════════════════════════════════════════════════════════════
    # SHELL (REAL execution)
    # ═══════════════════════════════════════════════════════════════

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

    # ═══════════════════════════════════════════════════════════════
    # WEB SEARCH
    # ═══════════════════════════════════════════════════════════════

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
        for chunk in _STREAMER.stream_words(answer, delay=0.01):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    # ═══════════════════════════════════════════════════════════════
    # SELF-AWARENESS (reads own source code)
    # ═══════════════════════════════════════════════════════════════

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
        for chunk in _STREAMER.stream_words(answer, delay=0.01):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    # ═══════════════════════════════════════════════════════════════
    # MEMORY / IDENTITY
    # ═══════════════════════════════════════════════════════════════

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
        for chunk in _STREAMER.stream_words(answer, delay=0.01):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    # ═══════════════════════════════════════════════════════════════
    # RECEIPT SYNTHESIZERS (anti-hallucination)
    # ═══════════════════════════════════════════════════════════════

    def _synth_receipt(self, query, receipt):
        ctx = receipt.as_llm_context()
        if receipt.verified and receipt.ok:
            prompt = (f"User asked: {query}\n\nTool receipt (VERIFIED SUCCESS):\n{ctx}\n\n"
                      "Confirm briefly what was done. Include the full file path. Max 3 sentences.\n"
                      "You MUST only state facts from the receipt. Do not add information not in the receipt.")
        else:
            prompt = (f"User asked: {query}\n\nTool receipt (FAILED):\n{ctx}\n\n"
                      "Operation FAILED. Tell user exactly what failed and suggest a specific fix. Max 3 sentences.\n"
                      "Be honest about the failure. Do NOT claim success.")
        answer = generate_response(prompt, provider="auto", system_prompt=_get_sys(self.profile_data))
        for chunk in _STREAMER.stream_words(answer, delay=0.01):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    def _synth_text(self, query, text_result):
        prompt = f"Task: {query}\nTool output:\n{text_result}\n\nSummarize concisely based ONLY on this output."
        answer = generate_response(prompt, provider="auto", system_prompt=_get_sys(self.profile_data))
        for chunk in _STREAMER.stream_words(answer, delay=0.01):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}
