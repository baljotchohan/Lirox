"""
Lirox v1.0.0 — Chat Agent

A general-purpose conversational agent that delegates directly to the
configured LLM provider. Suitable for open-ended dialogue and
question-answering tasks.
"""

from __future__ import annotations

from typing import Generator

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.utils.llm import generate_response


class ChatAgent(BaseAgent):
    """
    General conversation agent.

    Routes user queries straight to the LLM with minimal pre-processing,
    storing each exchange in the agent's isolated memory.
    """

    @property
    def name(self) -> str:
        return "chat"

    @property
    def description(self) -> str:
        return "General conversation agent"

    def get_onboarding_message(self) -> str:
        """Return the first-launch welcome message."""
        return (
            "💬 **Chat Agent** ready!\n\n"
            "I'm here for open-ended conversation, quick questions, brainstorming, "
            "writing assistance, and everything in between.\n\n"
            "What's on your mind?"
        )

    def run(
        self,
        query: str,
        system_prompt: str = "",
        context: str = "",
        mode: str = "think",
    ) -> Generator[AgentEvent, None, None]:
        """
        Handle a conversational query.

        Args:
            query:         User input.
            system_prompt: Optional extra system instructions.
            context:       Additional context from memory or the caller.
            mode:          Execution mode (unused internally).

        Yields:
            ``{"type": "thinking", …}`` then ``{"type": "done", …}``.
        """
        yield {"type": "thinking", "message": "💭 Thinking…"}

        memory_ctx = self.memory.get_relevant_context(query, max_items=8)
        full_context = "\n".join(filter(None, [context, memory_ctx]))

        base_system = (
            "You are a helpful, knowledgeable, and friendly assistant. "
            "Be concise yet thorough, and adapt your tone to the user's style."
        )
        combined_system = "\n\n".join(filter(None, [system_prompt, base_system]))

        prompt = f"{full_context}\n\nUser: {query}" if full_context else query

        try:
            response = generate_response(prompt, system_prompt=combined_system)
        except Exception as exc:
            response = f"I encountered an error: {exc}"

        self.memory.save_exchange(query, response[:500])

        yield {"type": "done", "message": response}
