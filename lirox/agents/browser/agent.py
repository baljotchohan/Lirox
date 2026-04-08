"""
Lirox v1.0.0 — Browser Agent

Web research and browsing agent that combines live web search with URL
fetching to answer questions about current events and online content.
"""

from __future__ import annotations

from typing import Generator

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.utils.llm import generate_response


class BrowserAgent(BaseAgent):
    """
    Web research and browsing agent.

    Uses the ``search_web`` and ``fetch_url`` helpers inherited from
    :class:`~lirox.agents.base_agent.BaseAgent` to gather live content
    before synthesising an answer with the LLM.
    """

    @property
    def name(self) -> str:
        return "browser"

    @property
    def description(self) -> str:
        return "Web research and browsing agent"

    def get_onboarding_message(self) -> str:
        """Return the first-launch welcome message."""
        return (
            "🌐 **Browser Agent** connected!\n\n"
            "I can search the web and fetch live content to answer your questions "
            "with up-to-date information.\n\n"
            "Just ask me anything — I'll search, read, and summarise for you."
        )

    def run(
        self,
        query: str,
        system_prompt: str = "",
        context: str = "",
        mode: str = "think",
    ) -> Generator[AgentEvent, None, None]:
        """
        Research *query* using live web search then synthesise an answer.

        Args:
            query:         User question or research request.
            system_prompt: Optional extra system instructions.
            context:       Additional context from memory or caller.
            mode:          Execution mode (unused internally).

        Yields:
            ``{"type": "thinking", …}``, optionally
            ``{"type": "search_result", …}``, then
            ``{"type": "done", …}``.
        """
        yield {"type": "thinking", "message": "🔍 Searching the web…"}

        # Perform web search
        search_results = self.search_web(query)

        if search_results and not search_results.startswith("Search error"):
            yield {
                "type":    "search_result",
                "message": f"Found web results for: {query}",
                "data":    search_results[:1000],
            }

        memory_ctx = self.memory.get_relevant_context(query, max_items=4)
        parts = [p for p in [context, memory_ctx, search_results] if p]
        full_context = "\n\n".join(parts)

        browser_system = (
            "You are a research assistant with access to live web search results. "
            "Synthesise the provided search results and context into a clear, "
            "accurate, and well-structured answer. "
            "Cite relevant sources when available."
        )
        combined_system = "\n\n".join(filter(None, [system_prompt, browser_system]))

        prompt = f"{full_context}\n\nQuestion: {query}" if full_context else query

        try:
            response = generate_response(prompt, system_prompt=combined_system)
        except Exception as exc:
            response = f"I encountered an error: {exc}"

        self.memory.save_exchange(query, response[:500])

        yield {"type": "done", "message": response}
