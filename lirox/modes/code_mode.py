"""
Code Mode — Persistent /code session.

Maintains state across multiple queries so the user can iteratively build,
edit, and run code without repeating context each time.
"""
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional

_logger = logging.getLogger("lirox.modes.code_mode")


@dataclass
class CodeSession:
    """Tracks state for an active /code session."""
    session_id: str
    working_dir: str
    language: str
    files: Dict[str, str] = field(default_factory=dict)   # filename → content
    history: List[Dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)

    def add_file(self, name: str, content: str) -> None:
        self.files[name] = content
        self.last_active = time.time()

    def add_history(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content, "ts": time.time()})
        self.last_active = time.time()

    def context_summary(self) -> str:
        """Build a concise context string for LLM prompts."""
        lines = [
            f"Language: {self.language}",
            f"Working directory: {self.working_dir}",
            f"Files in session: {', '.join(self.files.keys()) or 'none'}",
        ]
        if self.history:
            lines.append("Recent exchanges:")
            for entry in self.history[-4:]:
                lines.append(f"  [{entry['role']}] {entry['content'][:150]}")
        return "\n".join(lines)


class CodeMode:
    """
    Persistent /code session manager.

    Usage:
        mode = CodeMode()
        session = mode.start("python", working_dir="~/my_project")
        for event in mode.run(session, "create a Flask hello-world app"):
            ...
    """

    _sessions: Dict[str, CodeSession] = {}

    # ── Session management ───────────────────────────────────────────────────

    def start(self, language: str = "python", working_dir: str = "") -> CodeSession:
        """Create and register a new session."""
        from lirox.config import WORKSPACE_DIR

        sid = f"code_{int(time.time())}"
        wdir = os.path.expanduser(working_dir) if working_dir else WORKSPACE_DIR
        session = CodeSession(session_id=sid, working_dir=wdir, language=language)
        self._sessions[sid] = session
        _logger.info("Code session started: %s (%s)", sid, language)
        return session

    def get(self, session_id: str) -> Optional[CodeSession]:
        return self._sessions.get(session_id)

    def end(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    # ── Execution ────────────────────────────────────────────────────────────

    def run(
        self, session: CodeSession, query: str
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Process a query within the code session context.

        Yields agent-style event dicts for UI rendering.
        """
        from lirox.utils.llm import generate_response

        session.add_history("user", query)
        yield {"type": "agent_progress", "message": f"💻 [Code Mode / {session.language}] Processing..."}

        context = session.context_summary()
        system = (
            f"You are an expert {session.language} developer in a persistent coding session.\n"
            f"Session context:\n{context}\n\n"
            "Rules:\n"
            "- Write COMPLETE, runnable code (no snippets, no placeholders)\n"
            "- If creating files, output filename and full content\n"
            "- Track state between requests — don't repeat what's already built\n"
            "- Use emojis for structure, zero asterisks"
        )

        response = generate_response(query, provider="auto", system_prompt=system)
        session.add_history("assistant", response)

        # Parse any file blocks the LLM produced
        import re
        file_blocks = re.findall(
            r"```(?:\w+)?\s*\n# ?filename: ([^\n]+)\n(.*?)```",
            response, re.DOTALL
        )
        for filename, content in file_blocks:
            filename = filename.strip()
            path = os.path.join(session.working_dir, filename)
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content.strip())
            session.add_file(filename, content.strip())
            yield {"type": "tool_result", "message": f"📄 Saved: {path}"}

        from lirox.utils.streaming import StreamingResponse
        streamer = StreamingResponse()
        clean = streamer.clean_formatting(response)
        for chunk in streamer.stream_words(clean, delay=0.02):
            yield {"type": "streaming", "message": chunk}

        yield {"type": "done", "answer": clean}
