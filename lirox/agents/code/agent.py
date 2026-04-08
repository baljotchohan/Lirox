"""
Lirox v1.0.0 — Code Agent

A ``BaseAgent`` subclass specialised for code generation, analysis, and
debugging.  Generated code is automatically validated by
``CodeInspector`` before being returned to the user.
"""

from __future__ import annotations

from typing import Generator, Optional

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.agents.code.code_inspector import CodeInspector
from lirox.utils.llm import generate_response


class CodeAgent(BaseAgent):
    """
    Code generation, analysis, and debugging agent.

    Workflow for each ``run()`` call:

    1. Yield a *thinking* event.
    2. Call the LLM to generate code.
    3. Run ``CodeInspector`` on the generated code.
    4. Yield *inspection* events when issues are found.
    5. Yield the final *done* event containing the validated (or
       auto-fixed) code.
    """

    # ── Identity ──────────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        """Agent identifier used for routing and memory namespacing."""
        return "code"

    @property
    def description(self) -> str:
        """Short description shown in the agent roster."""
        return "Code generation, analysis and debugging agent"

    # ── Onboarding ────────────────────────────────────────────────────────────

    def get_onboarding_message(self) -> str:
        """Return the first-launch welcome message for this agent."""
        return (
            "👾 **Code Agent** online!\n\n"
            "I can help you:\n"
            "  • **Generate** code in Python, JS, TS, Go, Rust, and more\n"
            "  • **Debug** errors and explain stack traces\n"
            "  • **Review** code for bugs, style issues, and security holes\n"
            "  • **Refactor** and optimise existing code\n\n"
            "Just describe what you need or paste the code you want me to inspect."
        )

    # ── Main run loop ─────────────────────────────────────────────────────────

    def run(
        self,
        query: str,
        system_prompt: str = "",
        context: str = "",
        mode: str = "think",
    ) -> Generator[AgentEvent, None, None]:
        """
        Handle a coding query end-to-end.

        Args:
            query:         The user's request or code snippet.
            system_prompt: Optional extra system instructions.
            context:       Additional context (e.g. from memory).
            mode:          Execution mode (currently unused internally).

        Yields:
            :class:`AgentEvent` dicts of types:
            ``"thinking"``, ``"inspection"``, ``"done"``.
        """
        # ── Step 1: announce thinking ─────────────────────────────────────────
        yield {"type": "thinking", "message": "🧠 Analysing your request…"}

        # ── Step 2: call LLM ──────────────────────────────────────────────────
        memory_ctx = self.memory.get_relevant_context(query, max_items=6)
        full_context = "\n".join(filter(None, [context, memory_ctx]))

        code_system = (
            (system_prompt + "\n\n") if system_prompt else ""
        ) + (
            "You are an expert software engineer. "
            "When writing code, always include the language name as the first "
            "word on a line by itself (e.g. 'python') before the code block, "
            "so it can be detected automatically. "
            "Be precise, idiomatic, and well-documented."
        )

        prompt = query
        if full_context:
            prompt = f"{full_context}\n\nRequest: {query}"

        try:
            llm_response = generate_response(prompt, system_prompt=code_system)
        except Exception as exc:
            yield {"type": "done", "message": f"LLM error: {exc}", "code": None}
            return

        # ── Step 3: detect language and inspect ───────────────────────────────
        language = self._detect_language_from_response(llm_response, query)
        code_block = self._extract_code_block(llm_response)

        inspector = CodeInspector()
        inspection = inspector.inspect(code_block or llm_response, language)

        # ── Step 4: yield inspection results if issues exist ──────────────────
        if not inspection["valid"] and inspection["issues"]:
            yield {
                "type":    "inspection",
                "message": "⚠️ Issues detected in generated code:",
                "issues":  inspection["issues"],
            }

        # ── Step 5: build final response ──────────────────────────────────────
        final_code = (
            inspection.get("fixed_code")
            or code_block
            or llm_response
        )

        self.memory.save_exchange(query, final_code[:500])

        yield {
            "type":        "done",
            "message":     llm_response,
            "code":        final_code,
            "language":    language,
            "inspection":  inspection,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_code_block(text: str) -> Optional[str]:
        """
        Extract the first fenced code block from *text*.

        Handles both ` ```lang\\n…\\n``` ` and bare ` ``` ` fences.
        Returns ``None`` if no fenced block is found.
        """
        import re
        m = re.search(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
        return m.group(1).strip() if m else None

    @staticmethod
    def _detect_language_from_response(text: str, query: str) -> str:
        """
        Heuristically detect the intended language from the LLM response.

        Checks markdown fence annotations first, then falls back to
        keywords in the query.
        """
        import re
        m = re.search(r"```(\w+)", text)
        if m:
            lang = m.group(1).lower()
            if lang not in ("text", "plain", "output", "bash", "shell", "sh"):
                return lang

        query_lower = query.lower()
        for keyword in ("python", "javascript", "typescript", "go", "rust",
                         "java", "c#", "csharp", "cpp", "c++", "ruby", "php",
                         "swift", "kotlin"):
            if keyword in query_lower:
                return keyword.replace("c#", "csharp").replace("c++", "cpp")

        return "python"
