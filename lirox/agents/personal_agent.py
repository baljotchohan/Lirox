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

def _get_sys(profile_data: Dict[str, Any]) -> str:
    """
    Build system prompt with user context.
    
    UPDATED: Natural tone, clear limitations, smart formatting.
    """
    import platform
    import os
    
    # Detect OS
    os_type = platform.system().lower()
    os_info = {
        "darwin": "macOS",
        "linux": "Linux",
        "windows": "Windows"
    }.get(os_type, platform.system())
    
    # Get workspace
    from lirox.config import WORKSPACE_DIR
    
    # Base identity
    base = (
        "You are Lirox, a personal AI agent focused on autonomous execution and learning.\n"
        "You help with coding, file operations, research, and building projects.\n"
        f"You have full access to the filesystem (workspace: {WORKSPACE_DIR}).\n"
        f"You're running on {os_info}.\n"
    )
    
    # Add user context if available
    user_name = profile_data.get("user_name", "")
    if user_name and user_name.lower() not in ("king", "boss", "user", "operator"):
        base += f"You're assisting {user_name}.\n"
    
    # Add user background (but don't spam it in every response)
    user_role = profile_data.get("role", "")
    user_company = profile_data.get("company", "")
    if user_role or user_company:
        context_parts = []
        if user_company:
            context_parts.append(f"at {user_company}")
        if user_role:
            context_parts.append(f"working as {user_role}")
        if context_parts:
            base += f"They're {' '.join(context_parts)}.\n"
    
    # Core operational rules
    base += (
        "\n"
        "CORE CAPABILITIES:\n"
        "• Execute shell commands and verify results\n"
        "• Create/edit files directly on the system\n"
        "• Search the web for current information\n"
        "• Generate documents (PDF, DOCX, XLSX, PPTX)\n"
        "• Write complete code implementations\n"
        "\n"
        "CRITICAL LIMITATIONS:\n"
        "• You CANNOT view images (JPEG, PNG, etc.) - you can only read text files\n"
        "• If user shares an image path, tell them clearly: 'I can't view images yet. Can you describe what's in it or share it as text/PDF?'\n"
        "• Never say 'I cannot see the image' repeatedly - say it ONCE then ask for alternatives\n"
        "\n"
        "EXECUTION RULES:\n"
        "• Only confirm success after actual verification (file exists, command ran, etc.)\n"
        "• Report failures honestly - never pretend something worked\n"
        "• Write complete implementations - no TODOs or placeholders\n"
        "• Use real data when available, never 'John Doe' or 'example.com'\n"
        "\n"
        "COMMUNICATION STYLE - CRITICAL:\n"
        "• MATCH THE USER'S TONE:\n"
        "  - If they're casual/friendly → be conversational and relaxed\n"
        "  - If they use slang or another language → acknowledge it naturally\n"
        "  - If they're formal/professional → be professional back\n"
        "  - If they're stressed/urgent → be direct and helpful\n"
        "\n"
        "• FORMATTING BALANCE:\n"
        "  - Mix paragraphs and bullet points naturally\n"
        "  - Use emojis for section headers and visual breaks (NOT every line)\n"
        "  - Write in prose when explaining, use bullets for lists/steps\n"
        "  - Use '__text__' for emphasis (NEVER use asterisks)\n"
        "\n"
        "• GOOD RESPONSE PATTERN:\n"
        "  [Brief context paragraph]\n"
        "  \n"
        "  🎯 __Section Header__ (only when needed)\n"
        "  • Point one\n"
        "  • Point two\n"
        "  \n"
        "  [Concluding paragraph or next steps]\n"
        "\n"
        "• AVOID:\n"
        "  ✗ Giant single paragraphs with no breaks\n"
        "  ✗ Emoji on every single line (🔹 like this 🔹 every 🔹 time)\n"
        "  ✗ Over-structured corporate format (### headers everywhere)\n"
        "  ✗ Repetitive responses - vary your approach each time\n"
        "  ✗ Robotic language like 'I am operating at full capacity'\n"
        "\n"
        "• BE NATURAL:\n"
        "  ✓ 'Hey! All good. What's up?' (if they're casual)\n"
        "  ✓ 'Sure, I can help with that.' (not 'I shall assist you')\n"
        "  ✓ 'Got it - let me create that for you.' (not 'Acknowledged')\n"
        "\n"
        "MEMORY & LEARNING:\n"
        "• Remember what the user tells you (education, projects, preferences)\n"
        "• Don't ask for the same information twice\n"
        "• Build on previous context naturally\n"
        "• If they mention they're a student, remember their field/university\n"
        "• If they share project details, reference them in future conversations\n"
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
    r'pptx?|powerpoint|presentation|slides?|report|repoty?|resume|invoice|'
    r'certificate|letter|memo|proposal|deck|document|file|paper|chart)\b',
    re.IGNORECASE,
)


# Also match reversed order: "pdf about X" or "presentation on Y"
_FILEGEN_PATTERN_REV = re.compile(
    r'\b(?:pdf|word|docx|excel|xlsx|pptx?|powerpoint|presentation|slide|deck|report|repoty?|chart)\b'
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
    # Real-time data queries — must trigger web search, not chat
    "price of", "price today", "stock price", "share price",
    "market price", "exchange rate", "conversion rate",
    "weather in", "weather today", "weather forecast",
    "score of", "match score", "live score",
    "nifty", "sensex", "dow jones", "nasdaq", "s&p 500",
    "bitcoin price", "crypto price", "gold price", "silver price",
    "today's", "right now", "currently",
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
    """
    Classify query into task type.
    
    CRITICAL: Web search indicators must be checked FIRST.
    """
    q = query.lower().strip()
    
    # ═══════════════════════════════════════════════════════
    # WEB SEARCH - CHECK FIRST (highest priority)
    # ═══════════════════════════════════════════════════════
    web_indicators = [
        "search", "find on web", "look up", "google",
        "research", "find information", "search for",
        "look for", "find me", "deep research",
        "search web", "web search", "online",
        "latest", "recent", "news about", "current",
        "what is", "who is", "when did", "where is",
        "how to find", "show me", "get me"
    ]
    
    if any(indicator in q for indicator in web_indicators):
        return "web"
    
    # ═══════════════════════════════════════════════════════
    # FILE GENERATION
    # ═══════════════════════════════════════════════════════
    if any(w in q for w in ["create", "generate", "make", "write", "build"]):
        if any(w in q for w in ["pdf", "document", "docx", "presentation", 
                                 "pptx", "spreadsheet", "xlsx", "resume", 
                                 "report", "website", "site", "page"]):
            return "filegen"
    
    # ═══════════════════════════════════════════════════════
    # FILE OPERATIONS
    # ═══════════════════════════════════════════════════════
    if any(w in q for w in ["read", "open", "show", "list", "view", "cat"]):
        if any(w in q for w in ["file", "folder", "directory", "document"]):
            return "file"
    
    # ═══════════════════════════════════════════════════════
    # SHELL COMMANDS
    # ═══════════════════════════════════════════════════════
    if any(w in q for w in ["run", "execute", "command", "terminal", 
                            "shell", "install", "npm", "pip", "git"]):
        return "shell"
    
    # ═══════════════════════════════════════════════════════
    # DEFAULT: CHAT
    # ═══════════════════════════════════════════════════════
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

        # ── /code persistent session ────────────────────────────────────────
        if query.strip().lower().startswith("/code"):
            yield from self._code_session(query, context)
            return

        task = _classify(query)

        dispatch = {
            "self":    self._self,
            "memory":  self._memory,
            "filegen": self._filegen_pipeline,  # NEW pipeline-backed handler
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
        # Show immediate progress to avoid "stuck" feeling
        yield {"type": "agent_progress", "message": "🔍 Analyzing request...", "agent": self.name}
        
        base_sys = sp or _get_sys(self.profile_data)
        user_name = self.profile_data.get("user_name", "")
        agent_name = self.profile_data.get("agent_name", "Lirox")

        # ── GREETING DETECTION ──
        # Simple greetings should get a clean, direct response without injecting
        # stale conversation history (which causes hallucination about old projects).
        q_stripped = query.lower().strip().rstrip("!.?")
        _GREETINGS = {
            "hi", "hello", "hey", "yo", "sup", "hola", "howdy",
            "good morning", "good evening", "good afternoon", "good night",
            "what's up", "whats up", "wassup", "hii", "hiii",
            "hey there", "hello there", "hi there",
        }
        if q_stripped in _GREETINGS or (len(query.split()) <= 3 and q_stripped.split()[0] in {"hi", "hello", "hey", "yo", "sup"}):
            # Direct greeting — use enriched system prompt but force brevity
            greeting_prompt = (
                f"The user '{user_name or 'the user'}' just greeted you with: \"{query}\"\n\n"
                "Respond with a brief, warm greeting. Be direct and natural.\n"
                "Ask what they'd like to work on. Do NOT reference any past projects or topics.\n"
                "Keep it to 2-3 sentences max."
            )
            # Use the full enriched system prompt so it knows who it is (Lirox) and who the user is (boss)
            answer = generate_response(greeting_prompt, provider="auto", system_prompt=base_sys)
            answer = _STREAMER.clean_formatting(answer)
            for chunk in _STREAMER.stream_words(answer, delay=0.025):
                yield {"type": "streaming", "message": chunk}
            yield {"type": "done", "answer": answer}
            return

        # ── NORMAL CHAT (with context) ──
        yield {"type": "agent_progress", "message": "🧠 Synthesizing response...", "agent": self.name}
        mem_ctx = self.memory.get_relevant_context(query)
        prompt = query
        if mem_ctx and mem_ctx.strip():
            prompt = f"Relevant context:\n{mem_ctx}\n\nUser: {query}"
        
        # Add tone matching based on user's message
        user_is_casual = any(word in query.lower() for word in ['hey', 'yo', 'sup', "what's up", 'wassup', 'hi', 'hello'])
        user_is_urgent = any(word in query.lower() for word in ['urgent', 'asap', 'quick', 'emergency', 'help!', 'now'])
        user_is_multilingual = any(ord(c) > 127 for c in query)  # Non-ASCII chars = another language

        tone_guidance = ""
        if user_is_casual:
            tone_guidance = "\n[User is being casual/friendly - match their relaxed tone. No corporate speak.]"
        elif user_is_urgent:
            tone_guidance = "\n[User needs quick help - be direct and concise.]"
        elif user_is_multilingual:
            tone_guidance = "\n[User may be speaking another language - acknowledge it naturally if relevant.]"

        prompt += tone_guidance
        prompt += "\n[Format: Natural paragraphs + strategic bullets. Emojis for sections only, not every line. Use '__' for emphasis.]"

        if context:
            prompt = f"Context:\n{context[:1500]}\n\n{prompt}"
            
        answer = generate_response(prompt, provider="auto", system_prompt=base_sys)

        # ANTI-REPETITION CHECK
        # If this response is too similar to last response, regenerate with variation
        if hasattr(self, '_last_response') and self._last_response:
            from lirox.quality.similarity import calculate_similarity
            
            similarity = calculate_similarity(answer, self._last_response)
            
            if similarity > 0.75 and len(answer) > 300:
                # Too similar, regenerate with anti-repetition instruction
                varied_prompt = prompt + "\n\n[IMPORTANT: Your last response was similar to this. Vary your approach - try a different structure, different examples, or different angle.]"
                
                answer = generate_response(
                    varied_prompt,
                    provider="auto",
                    system_prompt=base_sys,
                )

        # Store this response for next comparison
        self._last_response = answer

        # Extract and store facts automatically
        try:
            self._extract_and_store_facts(query, answer)
        except Exception:
            pass  # Don't break chat if extraction fails

        answer = _STREAMER.clean_formatting(answer)
        for chunk in _STREAMER.stream_words(answer, delay=0.025):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # FILE GENERATION — v1.1 Pipeline (NEW)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _filegen_pipeline(self, query, context, sp=""):
        """
        Pipeline-backed file generation.
        CLASSIFY → THINK → PLAN → EXECUTE → VERIFY → RESPOND

        Uses the new lirox.pipeline stack with Designer Agent + Quality checks.
        Falls back to legacy _filegen if the pipeline is unavailable.
        """
        try:
            from lirox.pipeline.core import ExecutionPipeline

            pipeline = ExecutionPipeline(
                memory=self.memory,
                profile_data=self.profile_data,
            )

            # SAFETY: context arriving from orchestrator may be a list or other type
            safe_context = context if isinstance(context, str) else str(context) if context else ""

            for event in pipeline.run(query, context=safe_context):
                if event.type == "done":
                    answer = event.message
                    answer = _STREAMER.clean_formatting(answer)
                    for chunk in _STREAMER.stream_words(answer, delay=0.025):
                        yield {"type": "streaming", "message": chunk}
                    yield {"type": "done", "answer": answer}
                    return
                elif event.type == "error":
                    # Log and fall through to legacy handler
                    _logger.warning("Pipeline error: %s — falling back", event.message)
                    yield {"type": "agent_progress", "message": f"⚠️ {event.message}"}
                else:
                    # Forward progress / thinking / plan / execute / verify events
                    yield {"type": "agent_progress", "message": event.message}

        except Exception as exc:
            _logger.error("Pipeline failed (%s) — falling back to legacy filegen", exc)
            yield {"type": "agent_progress",
                   "message": "⚠️ Advanced pipeline unavailable — using standard generation."}

        # ── Legacy fallback ──────────────────────────────────────────────────
        yield from self._filegen(query, context, sp)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # /code PERSISTENT SESSION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    _code_session_store: dict = {}  # class-level session registry

    def _code_session(self, query: str, context: str, sp: str = ""):
        """Handle /code <language> or subsequent queries within a session."""
        from lirox.modes.code_mode import CodeMode

        mode = CodeMode()

        # Parse language from /code invocation
        parts = query.strip().split(maxsplit=2)
        if len(parts) >= 2 and not parts[1].startswith("/"):
            language = parts[1]
            actual_query = " ".join(parts[2:]) if len(parts) > 2 else ""
        else:
            language = "python"
            actual_query = " ".join(parts[1:])

        # Re-use or create session
        session = self._code_session_store.get("active")
        if session is None or session.language != language:
            session = mode.start(language=language)
            self._code_session_store["active"] = session
            yield {"type": "agent_progress",
                   "message": f"💻 Code session started [{language.upper()}]. "
                               "Type /code end to exit."}

        if actual_query.strip().lower() in ("/code end", "end", "exit", "quit"):
            mode.end(session.session_id)
            self._code_session_store.pop("active", None)
            yield {"type": "done", "answer": "✅ Code session ended."}
            return

        if not actual_query.strip():
            yield {"type": "done",
                   "answer": f"💻 Code session active [{session.language.upper()}]. "
                              "Type your coding request."}
            return

        yield from mode.run(session, actual_query)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # FILE GENERATION — Legacy (fallback)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _filegen(self, query, context, sp=""):

        """
        COMPLETE FILE GENERATION WITH REAL DESIGN THINKING.

        Pipeline:
        1. DESIGN:   Analyze topic → Create design plan
        2. CONTENT:  Generate rich content → Structure for audience
        3. PATH:     Determine safe output path
        4. CREATE:   Build actual file → Verify on disk
        5. REPORT:   Show user what was created (only if verified)
        """
        from pathlib import Path as _Path
        from datetime import datetime
        from lirox.tools.file_generation.design_engine import DesignEngine
        from lirox.tools.file_generation.content_strategist import ContentStrategist
        from lirox.tools.document_creators import create_pdf, create_docx, create_xlsx, create_pptx
        from lirox.config import WORKSPACE_DIR
        from lirox.utils.input_sanitizer import sanitize_user_name

        user_name = sanitize_user_name(self.profile_data.get("user_name", ""))
        if user_name.lower() in ("lirox", "lirox ai", "unknown", ""):
            user_name = ""

        # ──────────────────────────────────────────────────────────────────
        # PHASE 1 — ADAPTIVE THINKING
        # ──────────────────────────────────────────────────────────────────
        yield {"type": "agent_progress", "message": "🧠 Initiating Adaptive Thinking Engine..."}

        think_result = None
        try:
            from lirox.thinking.adaptive_engine import AdaptiveThinkingEngine

            thinking_engine = AdaptiveThinkingEngine()

            for event in thinking_engine.think(
                query=query,
                context={"query": query, "raw_context": context},
                complexity="high",
            ):
                if event.get("type") == "done":
                    think_result = event.get("data", {})
                else:
                    yield {"type": "agent_progress", "message": event.get("message", "")}

            if think_result:
                decision = think_result.get("decision", query)[:100]
                yield {
                    "type": "agent_progress",
                    "message": f"✓ Approach decided: {decision}",
                }

        except Exception as e:
            _logger.error("Thinking engine error: %s", e, exc_info=True)
            yield {"type": "agent_progress", "message": "⚠️ Thinking engine failed, using direct reasoning."}


            
        file_type = DesignEngine.detect_file_type(query)
        try:
            design = DesignEngine.plan_document(query, query[:80], file_type=file_type)
            design_log = DesignEngine.log_design_decision(design)
            yield {"type": "agent_progress", "message": design_log}
        except Exception as e:
            _logger.warning("Design planning failed (%s), using defaults", e)
            design = DesignEngine.plan_document(query, query[:80])

        palette_name = design.palette
        audience_level = design.audience.value
        user_expertise = self.profile_data.get("expertise_level", audience_level)

        # ──────────────────────────────────────────────────────────────────
        # PHASE 2 — CONTENT GENERATION
        # ──────────────────────────────────────────────────────────────────
        yield {"type": "agent_progress", "message": "📝 Generating rich content…"}

        try:
            from lirox.learning.manager import LearningManager
            lm = LearningManager()
            prefs_context = lm.apply_preferences_to_generation()
            
            design_context = f"Design Plan:\n- Theme: {design.theme.value}\n- Audience: {audience_level}\n- Structure: {len(design.structure)} sections on {design.topic}\n- Palette: {design.palette}"
            if prefs_context:
                design_context += "\n" + prefs_context
                
            content_generator = ContentStrategist.generate(
                topic=design.topic,
                query=query,
                file_type=file_type,
                audience=audience_level,
                structure_hints=design.structure,
                design_context=design_context,
            )
            
            content = None
            for event in content_generator:
                if event["type"] == "progress":
                    yield {"type": "agent_progress", "message": event["message"]}
                elif event["type"] == "result":
                    content = event["data"]
                    
            if not content:
                raise ValueError("Content generation yielded no result")
                
        except Exception as e:
            _logger.error(f"[ERROR] Content generation failed: {str(e)}", exc_info=True)
            yield {"type": "warning", "message": f"⚠️ Content generation issue: {str(e)}. Retrying with simpler approach..."}
            content = self._filegen_fallback(query)
            yield {"type": "agent_progress", "message": "✓ Generated with fallback method"}

        title = content.get("title", "") or design.topic or query[:80]



        # ──────────────────────────────────────────────────────────────────
        # PHASE 3 — RESOLVE OUTPUT PATH
        # ──────────────────────────────────────────────────────────────────
        ext_map = {"pdf": ".pdf", "docx": ".docx", "xlsx": ".xlsx", "pptx": ".pptx"}
        ext = ext_map.get(file_type, ".pdf")

        q_lower = query.lower()
        if "desktop" in q_lower:
            base_dir = os.path.expanduser("~/Desktop")
        elif "download" in q_lower:
            base_dir = os.path.expanduser("~/Downloads")
        elif "document" in q_lower:
            base_dir = os.path.expanduser("~/Documents")
        else:
            base_dir = WORKSPACE_DIR

        safe_name = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')[:50]
        if not safe_name:
            safe_name = f"document_{int(time.time())}"
        path = os.path.join(base_dir, safe_name + ext)

        try:
            path = _resolve_path(path, query)
        except (PermissionError, ValueError) as pe:
            yield {"type": "error", "message": f"❌ Path validation failed: {pe}"}
            return

        os.makedirs(os.path.dirname(path), exist_ok=True)

        # ──────────────────────────────────────────────────────────────────
        # PHASE 3b — ENSURE DATA STRUCTURES ARE VALID
        # ──────────────────────────────────────────────────────────────────
        if file_type in ("pdf", "docx"):
            sections = content.get("sections", [])
            if not isinstance(sections, list) or not sections:
                sections = [{"heading": title, "body": query[:500], "bullets": []}]
            # Add user personalisation to first section
            if user_name and user_name.lower() not in ("lirox", "lirox ai", "unknown"):
                header = (
                    f"Document prepared for {user_name}\n"
                    f"Topic: {query}\n"
                    f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}\n\n"
                )
                first = sections[0]
                first["body"] = header + (first.get("body") or "")
            content["sections"] = sections

        elif file_type == "pptx":
            slides = content.get("slides", [])
            if not isinstance(slides, list) or not slides:
                slides = [{"title": title, "bullets": [query[:80]], "notes": ""}]
            content["slides"] = slides

        elif file_type == "xlsx":
            sheets = content.get("sheets", [])
            if not isinstance(sheets, list) or not sheets:
                sheets = [{"name": "Sheet1", "headers": ["Data"], "rows": [[query[:100]]]}]
            content["sheets"] = sheets

        # ──────────────────────────────────────────────────────────────────
        # PHASE 4 — CREATE FILE
        # ──────────────────────────────────────────────────────────────────
        yield {"type": "tool_call", "message": f"✨ Creating {file_type.upper()}: {os.path.basename(path)}"}

        receipt = None
        try:
            if file_type == "pdf":
                receipt = create_pdf(
                    path, title, content["sections"],
                    query=query, user_name=user_name, user_expertise=user_expertise,
                    design_plan=design,
                )
            elif file_type == "docx":
                receipt = create_docx(
                    path, title, content["sections"],
                    query=query, user_name=user_name, user_expertise=user_expertise,
                    design_plan=design,
                )
            elif file_type == "pptx":
                receipt = create_pptx(
                    path, title, content["slides"],
                    query=query, user_name=user_name, user_expertise=user_expertise,
                    design_plan=design,
                )
            elif file_type == "xlsx":
                receipt = create_xlsx(
                    path, title, content["sheets"],
                    query=query, user_name=user_name, user_expertise=user_expertise,
                    design_plan=design,
                )
            else:
                receipt = FileReceipt(
                    tool="file_generator", operation="create",
                    error=f"Unknown file type: {file_type}",
                )
        except Exception as e:
            _logger.exception("File creation exception: %s", e)
            receipt = FileReceipt(
                tool="file_generator", operation="create",
                path=path, error=f"File creation error: {e}",
            )

        if receipt is None:
            receipt = FileReceipt(
                tool="file_generator", operation="create", path=path,
                error="File creation returned None receipt",
            )

        # ──────────────────────────────────────────────────────────────────
        # PHASE 5 — STRICT VERIFICATION
        # Only claim success if file ACTUALLY exists and has content
        # ──────────────────────────────────────────────────────────────────
        try:
            from lirox.verify.comprehensive_check import ComprehensiveVerification

            cv_passed = True
            if file_type == "pdf":
                cv_passed = ComprehensiveVerification.verify_pdf_generation(path, design, content.get("sections", []))

            from lirox.verify.file_verification import FileVerificationEngine
            fv = FileVerificationEngine.verify(path)

            if fv["passed"] and cv_passed:
                file_size = os.path.getsize(path)
                section_count = self._count_content(content, file_type)

                # Build rich success message
                answer = (
                    f"✅ {file_type.upper()} created successfully!\n\n"
                    f"📄 __{os.path.basename(path)}__\n"
                    f"📍 `{path}`\n"
                    f"📊 {file_size:,} bytes | {section_count}\n"
                    f"🎨 Theme: {design.theme.value.capitalize()} | "
                    f"Palette: {design.palette.capitalize()}\n"
                    f"👥 Audience: {design.audience.value.capitalize()}\n"
                )
                if user_name:
                    answer += f"👤 Created for: {user_name}\n"
                answer += f"⏱️ {datetime.now().strftime('%B %d, %Y at %H:%M')}"

                answer = _STREAMER.clean_formatting(answer)

                for chunk in _STREAMER.stream_words(answer, delay=0.025):
                    yield {"type": "streaming", "message": chunk}
                done_event = {"type": "done", "answer": answer}
                if think_result:
                    done_event["thinking_result"] = think_result
                yield done_event
                return

            else:
                issues_str = "; ".join(fv["issues"]) if not fv["passed"] else "Comprehensive verification failed (e.g. thin content or generic text)"
                answer = (
                    f"❌ File creation encountered issues:\n\n"
                    f"__Issues:__\n"
                    f"- {issues_str}\n\n"
                    f"__Path:__ `{path}`\n"
                    f"__Type:__ {file_type.upper()}\n\n"
                    f"Please try again or use a different topic."
                )
                yield {"type": "error", "message": answer}
                return

        except Exception as e:
            _logger.error("File verification error: %s", e)
            answer = (
                f"⚠️ File was created but verification failed:\n\n"
                f"__Path:__ `{path}`\n"
                f"__Error:__ {e}\n\n"
                f"Please check the file manually."
            )
            yield {"type": "warning", "message": answer}
            return

    # ── helpers ───────────────────────────────────────────────────────────

    def _count_content(self, d: dict, file_type: str) -> str:
        """Human-readable content summary."""
        if not d or not isinstance(d, dict):
            return "unknown amount"

        if file_type == "pptx":
            slides = d.get("slides", [])
            if not isinstance(slides, list):
                return "unknown amount"
            n = len(slides)
            return f"{n + 2} slides"  # +hero +closing
        elif file_type == "xlsx":
            sheets = d.get("sheets", [])
            if not isinstance(sheets, list):
                return "unknown amount"
            total_rows = sum(
                len(s.get("rows", []) if isinstance(s, dict) else [])
                for s in sheets
            )
            return f"{len(sheets)} sheet{'s' if len(sheets) != 1 else ''}, {total_rows} rows"
        else:
            sections = d.get("sections", [])
            if not isinstance(sections, list):
                return "unknown amount"
            n = len(sections)
            return f"{n} section{'s' if n != 1 else ''}"

    def _filegen_fallback(self, query: str) -> dict:
        """Last-resort: build a valid plan from the query itself."""
        q = query.lower()
        file_type = "pdf"
        if any(w in q for w in ["ppt", "powerpoint", "presentation", "slide", "deck"]):
            file_type = "pptx"
        elif any(w in q for w in ["excel", "xlsx", "spreadsheet", "xls"]):
            file_type = "xlsx"
        elif any(w in q for w in ["word", "docx", "doc"]):
            file_type = "docx"

        title = query[:80] if query else "Untitled Document"

        return {
            "file_type": file_type,
            "title": title,
            "path": "",
            "sections": [{"heading": "Content", "body": query[:500], "bullets": []}],
            "slides": [{"title": title, "bullets": ["Content based on: " + query[:60]], "notes": ""}],
            "sheets": [{"name": "Sheet1", "headers": ["Info"], "rows": [[query[:100]]]}],
        }

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
        yield {"type": "agent_progress", "message": "📂 Planning file operation…"}

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
                    answer = f"📄 __{path}__ ({receipt.lines} lines, {receipt.bytes_read} bytes):\n\n```\n{file_content[:3000]}\n```"
                    if receipt.details.get("truncated"):
                        answer += "\n\n(truncated — file is larger)"
                    answer = _STREAMER.clean_formatting(answer)
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
        yield {"type": "agent_progress", "message": "⚡ Planning command…"}
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
        """
        Handle web search queries using REAL DuckDuckGo search.
        
        Returns actual URLs, titles, and snippets from the web.
        """
        from lirox.tools.search.duckduckgo import search
        
        yield {"type": "agent_progress", "message": "🔍 Searching the web..."}
        
        try:
            # ACTUALLY SEARCH THE WEB
            results = search(query, max_results=8)
            
            if not results:
                yield {"type": "done", "answer": "I couldn't find any results for that query. Try rephrasing or being more specific."}
                return
            
            yield {"type": "agent_progress", "message": f"📊 Found {len(results)} results"}
            
            # Build context from REAL results
            search_context = "WEB SEARCH RESULTS (REAL DATA FROM DUCKDUCKGO):\n\n"
            
            for i, result in enumerate(results, 1):
                search_context += f"Result {i}:\n"
                search_context += f"Title: {result['title']}\n"
                search_context += f"URL: {result['url']}\n"
                search_context += f"Snippet: {result['snippet']}\n"
                search_context += f"Source: {result['source']}\n\n"
            
            # Generate response using REAL data
            system_prompt = sp or _get_sys(self.profile_data)
            
            prompt = f"""
User query: {query}

Here are REAL search results from DuckDuckGo:

{search_context}

Your task:
1. Answer the user's question using information from these REAL results
2. Cite sources by name and include the actual URLs
3. Format sources as clickable links in your response
4. If results don't fully answer the question, say what information is missing
5. Be natural and helpful - don't just list the results

CRITICAL:
• Only use information from the search results above
• Always include actual URLs so user can click them
• Don't make up additional information
• Be conversational but accurate

Format example:
"I found several resources:

__Resource Name__
Description of what it offers
Link: https://actual-url.com

__Another Resource__
What this provides
Link: https://another-url.com"
"""
            
            yield {"type": "agent_progress", "message": "🧠 Analyzing results..."}
            
            answer = generate_response(
                prompt,
                provider="auto",
                system_prompt=system_prompt
            )
            
            answer = _STREAMER.clean_formatting(answer)
            for chunk in _STREAMER.stream_words(answer, delay=0.025):
                yield {"type": "streaming", "message": chunk}
                
            yield {"type": "done", "answer": answer}
        
        except Exception as e:
            _logger.error(f"Web search error: {e}", exc_info=True)
            yield {"type": "error", "message": f"Search failed: {str(e)}"}

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SELF — Read own source code
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _self(self, query, context, sp=""):
        from lirox.config import LIROX_SOURCE_DIR
        q = query.lower()
        
        # ── AUTONOMOUS SELF-AUDIT ──
        if any(kw in q for kw in ["fix", "audit", "check errors", "diagnostic", "test yourself"]):
            yield {"type": "agent_progress", "message": "🩺 Running internal diagnostics…"}
            from lirox.tools.shell_verified import shell_run_verified
            
            # 1. Run tests to see what's broken
            receipt = shell_run_verified("pytest --maxfail=2")
            yield {"type": "tool_result", "message": receipt.as_user_summary()}
            
            if receipt.ok and receipt.verified:
                answer = "✅ All systems normal! All internal tests passed. I'm running perfectly. 🚀"
            else:
                yield {"type": "agent_progress", "message": "🔬 Analyzing failures…"}
                # 2. If broken, analyze the output and files
                prompt = (
                    f"Task: {query}\n"
                    f"Test Output:\n{receipt.output[:2000]}\n\n"
                    "I am Lirox. I just ran my own tests and they failed. "
                    "Analyze the error and suggest which file needs fixing and what the fix is."
                )
                answer = generate_response(prompt, provider="auto", system_prompt=_get_sys(self.profile_data))
            
            answer = _STREAMER.clean_formatting(answer)
            
            for chunk in _STREAMER.stream_words(answer, delay=0.025):
                yield {"type": "streaming", "message": chunk}
            yield {"type": "done", "answer": answer}
            return

        # ── STANDARD INFORMATIONAL SELF ──
        yield {"type": "agent_progress", "message": "🔍 Reading own source code…"}
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
        answer = _STREAMER.clean_formatting(answer)
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
        answer = _STREAMER.clean_formatting(answer)
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
        answer = _STREAMER.clean_formatting(answer)
        for chunk in _STREAMER.stream_words(answer, delay=0.025):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    def _synth_text(self, query, text_result):
        prompt = f"Task: {query}\nTool output:\n{text_result}\n\nSummarize concisely."
        answer = generate_response(prompt, provider="auto", system_prompt=_get_sys(self.profile_data))
        answer = _STREAMER.clean_formatting(answer)
        for chunk in _STREAMER.stream_words(answer, delay=0.025):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    def _extract_and_store_facts(self, query: str, response: str):
        """
        Automatically extract facts from conversation and store in memory.
        
        Examples:
        - "I'm in BCA at Punjab University" → store education info
        - "I'm working on Lirox" → store project info
        - "I prefer dark theme" → store preference
        """
        from lirox.utils.llm import generate_response
        
        # Quick heuristic check - only extract if user is sharing info about themselves
        personal_indicators = [
            "i'm", "i am", "my", "i study", "i work", "i prefer",
            "i like", "i'm building", "i'm working on", "i'm in"
        ]
        
        query_lower = query.lower()
        if not any(ind in query_lower for ind in personal_indicators):
            return  # No personal info to extract
        
        # Use LLM to extract facts
        extract_prompt = f"""
Extract factual information about the user from this conversation:

User said: {query}
Assistant response: {response[:200]}

Extract any facts about:
- Education (university, degree, year, subjects)
- Projects (what they're building, technologies used)
- Preferences (favorite tools, work style, interests)
- Background (role, company, experience)

Format as JSON:
{{
  "education": "...",
  "projects": ["...", "..."],
  "preferences": "...",
  "background": "..."
}}

If no relevant facts, return empty object {{}}.
Output ONLY JSON, no explanation.
"""
        
        try:
            facts_json = generate_response(
                extract_prompt,
                provider="auto",
                system_prompt="Extract user facts precisely. Output only JSON."
            )
            
            # Clean and parse
            facts_json = facts_json.replace("```json", "").replace("```", "").strip()
            import json
            facts = json.loads(facts_json)
            
            # Store each fact type
            if facts.get("education"):
                self.memory.add_exchange(
                    "user", 
                    f"FACT: Education - {facts['education']}", 
                    "system",
                    "Stored"
                )
            
            if facts.get("projects"):
                for project in facts["projects"]:
                    self.memory.add_exchange(
                        "user",
                        f"FACT: Project - {project}",
                        "system",
                        "Stored"
                    )
            
            if facts.get("preferences"):
                self.memory.add_exchange(
                    "user",
                    f"FACT: Preference - {facts['preferences']}",
                    "system",
                    "Stored"
                )
            
            if facts.get("background"):
                self.memory.add_exchange(
                    "user",
                    f"FACT: Background - {facts['background']}",
                    "system",
                    "Stored"
                )
        
        except Exception as e:
            # Silent fail - fact extraction is optional
            pass
