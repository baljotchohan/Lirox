"""
Lirox v1.0.0 — Research Agent

Deep research and analysis agent capable of multi-step investigation,
source synthesis, and structured reporting on complex topics.
"""

from __future__ import annotations

from typing import Generator

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.utils.llm import generate_response


class ResearchAgent(BaseAgent):
    """
    Deep research and analysis agent.

    Combines web search, memory context, and an LLM reasoning pass to
    produce thorough, structured research outputs on any topic.
    """

    @property
    def name(self) -> str:
        return "research"

    @property
    def description(self) -> str:
        return "Deep research and analysis agent"

    def get_onboarding_message(self) -> str:
        """Return the first-launch welcome message."""
        return (
            "🔬 **Research Agent** activated!\n\n"
            "I specialise in deep-dive research and analysis:\n"
            "  • Multi-source information gathering\n"
            "  • Structured summaries and reports\n"
            "  • Comparative analysis across topics\n"
            "  • Fact-checking and verification\n\n"
            "Give me a topic or a complex question and I'll investigate thoroughly."
        )

    def run(
        self,
        query: str,
        system_prompt: str = "",
        context: str = "",
        mode: str = "think",
    ) -> Generator[AgentEvent, None, None]:
        """
        Conduct deep research on *query*.

        Args:
            query:         Research topic or question.
            system_prompt: Optional extra system instructions.
            context:       Additional context from memory or caller.
            mode:          Execution mode (unused internally).

        Yields:
            ``{"type": "thinking", …}``, optionally
            ``{"type": "search_result", …}``, then
            ``{"type": "done", …}``.
        """
        yield {"type": "thinking", "message": "🔎 Beginning research…"}

        # Gather live web data to supplement the LLM knowledge cut-off
        web_data = self.search_web(query)

        if web_data and not web_data.startswith("Search error"):
            yield {
                "type":    "search_result",
                "message": "Retrieved web research data.",
                "data":    web_data[:1000],
            }

        memory_ctx = self.memory.get_relevant_context(query, max_items=6)
        parts = [p for p in [context, memory_ctx, web_data] if p]
        full_context = "\n\n".join(parts)

        research_system = (
            "You are a meticulous research analyst. "
            "Provide comprehensive, well-structured reports with clear sections: "
            "Executive Summary, Key Findings, Analysis, and Conclusions. "
            "Distinguish clearly between established facts and informed speculation. "
            "Use precise language and support claims with evidence from the provided context."
        )
        combined_system = "\n\n".join(filter(None, [system_prompt, research_system]))

        prompt = f"{full_context}\n\nResearch topic: {query}" if full_context else query

        try:
            response = generate_response(prompt, system_prompt=combined_system)
        except Exception as exc:
            response = f"I encountered an error during research: {exc}"

        self.memory.save_exchange(query, response[:500])

        yield {"type": "done", "message": response}
