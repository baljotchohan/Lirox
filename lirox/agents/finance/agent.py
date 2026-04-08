"""
Lirox v1.0.0 — Finance Agent

Specialised agent for financial analysis, market commentary, and
quantitative reasoning.  Provides an onboarding greeting aligned with
the financial domain and applies a finance-focused system prompt to
every LLM call.
"""

from __future__ import annotations

from typing import Generator

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.utils.llm import generate_response


class FinanceAgent(BaseAgent):
    """
    Financial analysis and market data agent.

    Focuses on financial topics including market analysis, portfolio
    management, economic indicators, and quantitative modelling.
    """

    @property
    def name(self) -> str:
        return "finance"

    @property
    def description(self) -> str:
        return "Financial analysis and market data agent"

    def get_onboarding_message(self) -> str:
        """Return the first-launch welcome message."""
        return (
            "📈 **Finance Agent** at your service!\n\n"
            "How are you? I'm here to help with financial analysis — "
            "whether that's market trends, portfolio breakdowns, economic data, "
            "or quantitative modelling.\n\n"
            "What would you like to explore today?"
        )

    def run(
        self,
        query: str,
        system_prompt: str = "",
        context: str = "",
        mode: str = "think",
    ) -> Generator[AgentEvent, None, None]:
        """
        Handle a finance-related query.

        Args:
            query:         User question or analysis request.
            system_prompt: Optional extra system instructions.
            context:       Additional context from memory or caller.
            mode:          Execution mode (unused internally).

        Yields:
            ``{"type": "thinking", …}`` then ``{"type": "done", …}``.
        """
        yield {"type": "thinking", "message": "📊 Analysing financial data…"}

        memory_ctx = self.memory.get_relevant_context(query, max_items=6)
        full_context = "\n".join(filter(None, [context, memory_ctx]))

        finance_system = (
            "You are a senior financial analyst with expertise in equity markets, "
            "macroeconomics, portfolio theory, and quantitative finance. "
            "Provide clear, data-driven analysis. Cite relevant metrics and ratios. "
            "Always remind users that this is for informational purposes only and "
            "does not constitute investment advice."
        )
        combined_system = "\n\n".join(filter(None, [system_prompt, finance_system]))

        prompt = f"{full_context}\n\nUser: {query}" if full_context else query

        try:
            response = generate_response(prompt, system_prompt=combined_system)
        except Exception as exc:
            response = f"I encountered an error: {exc}"

        self.memory.save_exchange(query, response[:500])

        yield {"type": "done", "message": response}
