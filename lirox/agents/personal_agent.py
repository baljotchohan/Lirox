"""Lirox v2.0 — PersonalAgent

ARCHITECTURE:
  Every query goes through: CLASSIFY → PLAN → EXECUTE → VERIFY → RESPOND
  
  The agent NEVER says "I did X" without verification.
  The agent NEVER describes how to do something — it DOES it.
  Tool calls produce real side effects that are verified on disk.
"""
from __future__ import annotations

import json as _json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Generator, List

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.utils.llm import generate_response
from lirox.utils.streaming import StreamingResponse
from lirox.verify import FileReceipt, ShellReceipt

_STREAMER = StreamingResponse()
_logger = logging.getLogger("lirox.personal_agent")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SYSTEM PROMPT BUILDER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
        "• When a tool receipt says VERIFIED — confirm success.\n"
        "  When it says FAILED — report failure HONESTLY.\n"
        "• NEVER say 'I have created' unless you have a verified receipt.\n"
        "• Address the user by name when known.\n"
    )
    return base


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# JSON EXTRACTION (robust — handles fenced, nested, escaped)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _extract_json(text: str) -> dict:
    """Extract the first JSON object from *text*.

    Delegates to lirox.utils.llm_json which provides:
    - O(n) single-pass scanning (no quadratic back-tracking — C-02 fix)
    - Hard input size cap to prevent DoS on adversarially large responses
    - Correct backslash-escape tracking without backward re-scanning
    """
    from lirox.utils.llm_json import extract_json
    return extract_json(text)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PATH RESOLVER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _resolve_path(raw: str, query: str) -> str:
    if not raw:
        return ""
    from lirox.config import WORKSPACE_DIR, SAFE_DIRS_RESOLVED, PROTECTED_PATHS
    from lirox.utils.input_sanitizer import sanitize_path
    raw = sanitize_path(raw)
    p = os.path.expandvars(os.path.expanduser(raw))
    if os.path.isabs(p) or "/" in p or "\\" in p:
        # BUG-10 fix: os.path.realpath() fully resolves ALL symlink chains
        # (including intermediate components) so that symlinks pointing outside
        # the permitted directories are caught by the SAFE_DIRS_RESOLVED check
        # below.
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
        raise PermissionError(f"Path '{canonical}' is outside permitted directories.")

    return canonical


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CLASSIFIER — Determines what KIND of task this is
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Priority order matters. More specific patterns checked first.

SELF_SIGNALS = [
    "your code", "your source", "how do you work", "your architecture",
    "your files", "read your", "lirox code", "understand yourself",
]

MEMORY_SIGNALS = [
    "last conversation", "what did we discuss", "what do you know about me",
    "what's my name", "who am i", "who are you", "introduce yourself",
    "what have you learned", "remember when", "our history",
]

# File GENERATION — creating new document files (pdf/docx/xlsx/pptx)
_FILEGEN_PATTERN = re.compile(
    r'\b(?:create|make|generate|build|prepare|draft|write|design)\b'
    r'.*\b(?:pdf|word|docx|doc|excel|xlsx|xls|spreadsheet|'
    r'pptx?|powerpoint|presentation|slides?|report|resume|invoice|'
    r'certificate|letter|memo|proposal|deck)\b',
    re.IGNORECASE,
)

# Also match reversed order: "pdf about X" or "presentation on Y"
_FILEGEN_PATTERN_REV = re.compile(
    r'\b(?:pdf|word|docx|excel|xlsx|pptx?|powerpoint|presentation|slide|deck)\b'
    r'.*\b(?:about|on|of|for|with|containing)\b',
    re.IGNORECASE,
)

SHELL_SIGNALS = [
    "run command", "execute command", "in the terminal", "in bash",
    "run python", "git status", "git commit", "git push", "git pull",
    "npm install", "pip install", "docker run", "docker build",
    "start server", "pytest ", "cargo run", "make test", "ls ",
]

WEB_SIGNALS = [
    "search for", "look up", "find information", "google", "latest news",
    "research", "find out about", "current price", "news about",
    "in the news", "what is trending", "headlines",
]

# File OPERATIONS — reading/writing/listing existing files
_FILE_OP_SIGNALS = [
    "read file", "write file", "edit file", "delete file",
    "save to", "open file", "file contents",
    "list files", "show files", "what files", "find files",
    "on my desktop", "in downloads", "in documents",
    "tree", "structure", "folder", "directory",
]


def _classify(query: str) -> str:
    """Classify query intent. Order matters — most specific first."""
    q = query.lower().strip()

    # 1. Self-awareness (very specific, rare)
    if any(s in q for s in SELF_SIGNALS):
        return "self"

    # 2. Memory/identity (specific phrases)
    if any(s in q for s in MEMORY_SIGNALS):
        return "memory"

    # 3. FILE GENERATION — BEFORE generic file ops
    #    "create a ppt", "make a pdf", "generate excel", "presentation on X"
    if _FILEGEN_PATTERN.search(q) or _FILEGEN_PATTERN_REV.search(q):
        return "filegen"

    # 4. Shell commands
    if any(s in q for s in SHELL_SIGNALS):
        return "shell"

    # 5. Web search
    if any(s in q for s in WEB_SIGNALS):
        return "web"

    # 6. File operations (read/write/list existing files)
    #    Only match explicit file-op phrases, not broad patterns
    if any(s in q for s in _FILE_OP_SIGNALS):
        return "file"

    # 7. Check for file extensions in context of actual file operations
    if re.search(r'\b\w+\.(py|js|ts|md|txt|json|csv|html|css|yaml|yml|toml)\b', q):
        # Only if there's an action verb
        if re.search(r'\b(read|write|create|edit|open|show|cat|save|delete|find)\b', q):
            return "file"

    # 8. Default: conversational chat
    return "chat"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# THE AGENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PersonalAgent(BaseAgent):
    @property
    def name(self) -> str: return "personal"

    def run(self, query: str, system_prompt: str = "",
            context: str = "", mode: str = "auto") -> Generator[AgentEvent, None, None]:
        from lirox.utils.input_sanitizer import sanitize
        query = sanitize(query)
        task = _classify(query)

        dispatch = {
            "self":    self._self,
            "memory":  self._memory,
            "filegen": self._filegen,
            "shell":   self._shell,
            "web":     self._web,
            "file":    self._file,
            "chat":    self._chat,
        }
        handler = dispatch.get(task, self._chat)
        yield from handler(query, context, system_prompt)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CHAT — General conversation
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _chat(self, query, context, sp=""):
        base_sys = sp or _get_sys(self.profile_data)
        mem_ctx = self.memory.get_relevant_context(query)
        prompt = query
        if mem_ctx and mem_ctx.strip():
            prompt = f"Relevant context:\n{mem_ctx}\n\nUser: {query}"
        if context:
            prompt = f"Context:\n{context[:1500]}\n\n{prompt}"
        answer = generate_response(prompt, provider="auto", system_prompt=base_sys)
        for chunk in _STREAMER.stream_words(answer, delay=0.025):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # FILE GENERATION — PDF / Word / Excel / PPT
    # This is the CORE fix: actually creates files
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _filegen(self, query, context, sp=""):
        from lirox.tools.document_creators import create_pdf, create_docx, create_xlsx, create_pptx
        from lirox.verify import FileVerificationEngine, ContentQualityVerifier
        from lirox.tools.content_generator import ContentGenerator
        from lirox.config import WORKSPACE_DIR, OUTPUTS_DIR
        from lirox.utils.input_sanitizer import sanitize_user_name
        from datetime import datetime

        yield {"type": "agent_progress", "message": "📄 Planning document generation…"}

        user_name = sanitize_user_name(self.profile_data.get("user_name", ""))

        # ── STEP 1: Determine file type, path, and content via LLM ──
        plan_prompt = f"""You are a document generation planner. The user wants a file created.

USER REQUEST: {query}
DEFAULT WORKSPACE: {WORKSPACE_DIR}
OUTPUTS DIRECTORY: {OUTPUTS_DIR}
USER NAME: {user_name or 'User'}

TASK: Determine the file type, output path, and generate COMPLETE, RICH content.

CONTENT QUALITY RULES:
- Generate AT LEAST 3-4 sentences per section — never just bullet points
- Include specific facts, statistics, dates, and examples
- Vary the content structure — mix paragraphs, key stats, comparisons
- For presentations: create 8+ slides with rich bullet points (4-6 per slide)
- For PDFs: write full prose paragraphs, not just bullet lists
- Always include an introduction and conclusion section
- Add real value — don't restate the topic title as a sentence

Output ONLY this JSON — no other text:
{{
  "file_type": "pdf|docx|xlsx|pptx",
  "path": "/absolute/path/to/filename.ext",
  "title": "Document Title",
  "sections": [
    {{"heading": "Section Title", "body": "Full paragraph text here. Multiple sentences with real content.", "bullets": ["Detailed point 1", "Detailed point 2"]}}
  ],
  "sheets": [
    {{"name": "Sheet1", "headers": ["Column A", "Column B"], "rows": [["data1", "data2"]]}}
  ],
  "slides": [
    {{"title": "Slide Title", "bullets": ["Rich bullet with detail and context", "Another substantial point with examples", "A third point with specific facts", "Fourth point with actionable insight"], "notes": "Speaker notes with additional context"}}
  ]
}}

IMPORTANT:
- Use "sections" for pdf and docx files
- Use "sheets" for xlsx files
- Use "slides" for pptx files — generate AT LEAST 6-8 content slides
- Generate ALL content NOW — complete paragraphs, real data, full bullet points
- Each bullet should be a full sentence or detailed phrase, NOT just 2-3 words
- For {query}: generate rich, detailed, informative, expert-level content"""

        raw = generate_response(plan_prompt, provider="auto",
                                system_prompt="Document planner. Output ONLY the JSON object. No explanation.")

        # ── STEP 2: Parse the plan with triple-layer fallback ──
        from lirox.utils.llm import is_error_response
        if is_error_response(raw):
            yield {"type": "error", "message": f"❌ LLM provider error: {raw[:200]}"}
            yield from self._chat(query, context, sp)
            return
        
        d = None
        try:
            d = _extract_json(raw)
            if not d or not isinstance(d, dict):
                raise ValueError("JSON extraction returned None or non-dict")
        except ValueError:
            _logger.warning("JSON extraction failed, attempting fallback")
            d = self._filegen_fallback(query)
            if not d:
                yield {"type": "error", "message": "❌ Could not parse document plan from LLM."}
                yield from self._chat(query, context, sp)
                return

        # ── STEP 3: Validate and normalize plan dict ──
        file_type = (d.get("file_type") or "").lower().strip()
        path = (d.get("path") or "").strip()
        title = (d.get("title") or "").strip()

        if not file_type:
            q = query.lower()
            if any(w in q for w in ["pdf"]):
                file_type = "pdf"
            elif any(w in q for w in ["word", "docx", "doc", "document"]):
                file_type = "docx"
            elif any(w in q for w in ["excel", "xlsx", "spreadsheet", "xls"]):
                file_type = "xlsx"
            elif any(w in q for w in ["ppt", "pptx", "powerpoint", "presentation", "slide", "deck"]):
                file_type = "pptx"
            else:
                file_type = "pdf"

        if not title:
            title = f"Generated {file_type.upper()}"

        # ── STEP 4: Resolve output path with safety checks ──
        ext_map = {"pdf": ".pdf", "docx": ".docx", "xlsx": ".xlsx", "pptx": ".pptx"}
        ext = ext_map.get(file_type, ".pdf")

        if not path:
            q = query.lower()
            if "desktop" in q:
                base_dir = os.path.expanduser("~/Desktop")
            elif "download" in q:
                base_dir = os.path.expanduser("~/Downloads")
            elif "document" in q:
                base_dir = os.path.expanduser("~/Documents")
            else:
                base_dir = WORKSPACE_DIR

            safe_name = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')[:50]
            if not safe_name:
                safe_name = f"document_{int(time.time())}"
            path = os.path.join(base_dir, safe_name + ext)
        
        if not path.endswith(ext):
            base = path.rsplit('.', 1)[0] if '.' in os.path.basename(path) else path
            path = base + ext

        try:
            path = _resolve_path(path, query)
        except (PermissionError, ValueError) as pe:
            yield {"type": "error", "message": f"❌ Path validation failed: {pe}"}
            return

        # Ensure parent directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)

        # ── STEP 4b: Ensure sections/slides/sheets are proper lists ──
        if file_type in ("pdf", "docx"):
            sections = d.get("sections", [])
            if not isinstance(sections, list):
                sections = []
            if not sections:
                sections = [{"heading": "Content", "body": query[:500], "bullets": []}]
            d["sections"] = sections

        elif file_type == "xlsx":
            sheets = d.get("sheets", [])
            if not isinstance(sheets, list):
                sheets = []
            if not sheets:
                sheets = [{"name": "Sheet1", "headers": ["Data"], "rows": [[query[:100]]]}]
            d["sheets"] = sheets

        elif file_type == "pptx":
            slides = d.get("slides", [])
            if not isinstance(slides, list):
                slides = []
            if not slides:
                slides = [{"title": title, "bullets": [query[:80]], "notes": ""}]
            d["slides"] = slides

        # ── STEP 4c: Content quality check — enrich thin content via ContentGenerator ──
        quality_check = ContentQualityVerifier.check(file_type, d)
        if quality_check.get("issues"):
            yield {"type": "agent_progress", "message": "📝 Enriching document content…"}
            try:
                gen = ContentGenerator()
                topic = title or query[:80]
                enriched = gen.generate(file_type, topic, query=query)
                for key in ("slides", "sections", "sheets"):
                    if enriched.get(key) and (not d.get(key) or quality_check.get("issues")):
                        d[key] = enriched[key]
            except Exception as _ce:
                _logger.warning("ContentGenerator failed: %s", _ce)

        # ── STEP 4d: Add user context to content ──
        context_header = ""
        if user_name and user_name.lower() not in ("lirox", "lirox ai", "", "unknown"):
            context_header = (
                f"Document prepared for {user_name}\n"
                f"Topic: {query}\n"
                f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}\n\n"
            )

        if file_type in ("pdf", "docx") and context_header:
            if d.get("sections") and len(d["sections"]) > 0:
                first_section = d["sections"][0]
                if first_section.get("body"):
                    first_section["body"] = context_header + first_section["body"]
                else:
                    first_section["body"] = context_header

        yield {"type": "tool_call", "message": f"📄 Creating {file_type.upper()}: {os.path.basename(path)}"}

        # ── STEP 5: EXECUTE — Actually create the file ──
        receipt = None
        user_expertise = self.profile_data.get("expertise_level", "intermediate")
        try:
            if file_type == "pdf":
                sections = d.get("sections", [])
                if not isinstance(sections, list) or not sections:
                    sections = [{"heading": title, "body": query[:500], "bullets": []}]
                receipt = create_pdf(path, title, sections,
                                     query=query, user_name=user_name, user_expertise=user_expertise)

            elif file_type == "docx":
                sections = d.get("sections", [])
                if not isinstance(sections, list) or not sections:
                    sections = [{"heading": title, "body": query[:500], "bullets": []}]
                receipt = create_docx(path, title, sections,
                                      query=query, user_name=user_name, user_expertise=user_expertise)

            elif file_type == "xlsx":
                sheets = d.get("sheets", [])
                if not isinstance(sheets, list) or not sheets:
                    sheets = [{"name": "Sheet1", "headers": ["Data"], "rows": [[query[:100]]]}]
                receipt = create_xlsx(path, title, sheets,
                                      query=query, user_name=user_name, user_expertise=user_expertise)

            elif file_type == "pptx":
                slides = d.get("slides", [])
                if not isinstance(slides, list) or not slides:
                    slides = [{"title": title, "bullets": [query[:80]], "notes": ""}]
                receipt = create_pptx(path, title, slides,
                                      query=query, user_name=user_name, user_expertise=user_expertise)

            else:
                receipt = FileReceipt(tool="file_generator", operation="create",
                                      error=f"Unknown file type: {file_type}")

        except Exception as e:
            _logger.exception("File creation exception: %s", e)
            receipt = FileReceipt(tool="file_generator", operation="create",
                                  path=path, error=f"File creation error: {e}")

        if receipt is None:
            receipt = FileReceipt(tool="file_generator", operation="create", path=path,
                                  error="File creation returned None receipt")

        # ── VERIFICATION & ERROR HANDLING ──
        # Only claim success if file actually exists and is valid

        try:
            from lirox.verify.file_verification import FileVerificationEngine
            
            # Strict verification: file must exist AND have content AND have right structure
            fv = FileVerificationEngine.verify(path)
            
            if fv["passed"]:
                # File is valid
                file_size = os.path.getsize(path)
                section_count = self._count_content(d, file_type)
                
                answer = (
                    f"✅ Created **{os.path.basename(path)}**\n\n"
                    f"📁 Path: `{path}`\n"
                    f"📊 Size: {file_size:,} bytes\n"
                    f"📄 Content: {section_count}\n\n"
                    f"Your {file_type.upper()} is ready!"
                )
                
                yield {"type": "message", "message": answer}
                return
            else:
                # Verification failed - don't claim success
                issues_str = "; ".join(fv["issues"])
                answer = (
                    f"❌ File creation encountered issues:\n\n"
                    f"**Issues:**\n"
                    + "\n".join(f"- {issue}" for issue in fv["issues"]) + f"\n\n"
                    f"**Path:** `{path}`\n"
                    f"**Type:** {file_type.upper()}\n\n"
                    f"Please try again or use a different topic."
                )
                
                yield {"type": "error", "message": answer}
                return
                
        except Exception as e:
            # Verification system error
            _logger.error(f"File verification error: {e}")
            answer = (
                f"⚠️ File was created but verification failed:\n\n"
                f"**Path:** `{path}`\n"
                f"**Error:** {str(e)}\n\n"
                f"Please check the file manually."
            )
            yield {"type": "warning", "message": answer}
            return

        for chunk in _STREAMER.stream_words(answer, delay=0.025):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    def _count_content(self, d: dict, file_type: str) -> str:
        """Human-readable content summary."""
        if not d or not isinstance(d, dict):
            return "unknown amount"
        
        if file_type == "pptx":
            slides = d.get("slides", [])
            if not isinstance(slides, list):
                return "unknown amount"
            n = len(slides)
            return f"{n} slide{'s' if n != 1 else ''}"
        elif file_type == "xlsx":
            sheets = d.get("sheets", [])
            if not isinstance(sheets, list):
                return "unknown amount"
            total_rows = sum(len(s.get("rows", []) if isinstance(s, dict) else []) for s in sheets)
            return f"{len(sheets)} sheet{'s' if len(sheets) != 1 else ''}, {total_rows} rows"
        else:
            sections = d.get("sections", [])
            if not isinstance(sections, list):
                return "unknown amount"
            n = len(sections)
            return f"{n} section{'s' if n != 1 else ''}"

    def _filegen_fallback(self, query: str) -> dict:
        """Last-resort: build a complete, valid plan from the query itself."""
        q = query.lower()
        file_type = "pdf"
        if any(w in q for w in ["ppt", "powerpoint", "presentation", "slide", "deck"]):
            file_type = "pptx"
        elif any(w in q for w in ["excel", "xlsx", "spreadsheet", "xls"]):
            file_type = "xlsx"
        elif any(w in q for w in ["word", "docx", "doc"]):
            file_type = "docx"

        title = query[:80] if query else "Untitled Document"
        
        fallback = {
            "file_type": file_type,
            "title": title,
            "path": "",  
            "sections": [{"heading": "Content", "body": query[:500], "bullets": []}],
            "slides": [{"title": title, "bullets": ["Content based on: " + query[:60]], "notes": ""}],
            "sheets": [{"name": "Sheet1", "headers": ["Info"], "rows": [[query[:100]]]}],
        }
        
        return fallback

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # FILE OPERATIONS — Read/Write/List existing files
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
        # Check for provider error before JSON extraction for a clearer error message.
        from lirox.utils.llm import is_error_response as _is_err
        if _is_err(raw):
            yield {"type": "error", "message": f"❌ LLM provider error: {raw[:200]}"}
            return
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
            # FIX-1C: If path is still empty, try extracting a filename from the query
            if not path:
                import re as _re
                _fname_match = _re.search(
                    r'\b([\w\-./\\]+\.(?:html|py|js|ts|css|json|txt|md|csv|yaml|yml|xml|sh|bash|go|rs|java|c|cpp|h|rb|php|sql|log|ini|cfg|toml|env))\b',
                    query, _re.IGNORECASE,
                )
                if _fname_match:
                    path = _resolve_path(_fname_match.group(1), query)
            content = d.get("content", "")
            yield {"type": "tool_call", "message": f"📁 {op}: {path or '(workspace)'}"}

            if op == "read_file":
                if not path:
                    yield {"type": "error", "message": "❌ No file path specified. Please include a filename."}
                    return
                receipt = file_read_verified(path)
                if receipt.ok and receipt.verified:
                    file_content = receipt.details.get("content", "")
                    yield {"type": "tool_result", "message": f"📄 Read {receipt.bytes_read} bytes from {path}"}
                    answer = f"📄 **{path}** ({receipt.lines} lines, {receipt.bytes_read} bytes):\n\n```\n{file_content[:3000]}\n```"
                    if receipt.details.get("truncated"):
                        answer += "\n\n*(truncated — file is larger)*"
                    for chunk in _STREAMER.stream_words(answer, delay=0.025):
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

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SHELL — Real command execution
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _shell(self, query, context, sp=""):
        from lirox.tools.shell_verified import shell_run_verified
        yield {"type": "agent_progress", "message": "💻 Planning command…"}
        raw = generate_response(
            f"Task: {query}\n"
            'Output ONLY JSON: {{"command":"exact shell command","reason":"why",'
            '"working_dir":"~ or path or empty"}}',
            provider="auto", system_prompt="Shell expert. Output ONLY JSON.")
        try:
            # BUG-09 fix: ValueError from _extract_json is caught explicitly so
            # that a meaningful error message is returned rather than the catch-all
            # masking the real cause.
            d = _extract_json(raw)
            command = (d.get("command") or "").strip()
            if not command:
                yield {"type": "tool_result", "message": "❌ Could not determine command."}
                yield from self._chat(query, context, sp)
                return
            yield {"type": "tool_call", "message": f"$ {command}"}
            receipt = shell_run_verified(command, cwd=d.get("working_dir", ""))
        except ValueError:
            receipt = ShellReceipt(tool="shell", error="Could not parse shell plan from LLM response.")
        except Exception as e:
            receipt = ShellReceipt(tool="shell", error=f"Shell error: {e}")
        yield {"type": "tool_result", "message": receipt.as_user_summary()}
        yield from self._synth_receipt(query, receipt)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # WEB — Search the internet
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
        for chunk in _STREAMER.stream_words(answer, delay=0.025):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SELF — Read own source code
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
        for chunk in _STREAMER.stream_words(answer, delay=0.025):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # MEMORY — What do I know about the user
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
        for chunk in _STREAMER.stream_words(answer, delay=0.025):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # RECEIPT SYNTHESIZERS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _synth_receipt(self, query, receipt):
        ctx = receipt.as_llm_context()
        if receipt.verified and receipt.ok:
            prompt = (f"User asked: {query}\n\nTool receipt:\n{ctx}\n\n"
                      "Confirm briefly what was done. Include path if file was written. Max 3 sentences.")
        else:
            prompt = (f"User asked: {query}\n\nTool receipt:\n{ctx}\n\n"
                      "Operation FAILED. Tell user what failed and suggest a fix. Max 3 sentences.")
        answer = generate_response(prompt, provider="auto", system_prompt=_get_sys(self.profile_data))
        for chunk in _STREAMER.stream_words(answer, delay=0.025):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    def _synth_text(self, query, text_result):
        prompt = f"Task: {query}\nTool output:\n{text_result}\n\nSummarize concisely."
        answer = generate_response(prompt, provider="auto", system_prompt=_get_sys(self.profile_data))
        for chunk in _STREAMER.stream_words(answer, delay=0.025):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}
