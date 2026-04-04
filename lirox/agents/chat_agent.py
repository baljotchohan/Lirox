"""Chat Agent — default conversational fallback."""
from typing import Generator

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.utils.llm import generate_response
from lirox.soul import get_identity_prompt


class ChatAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "chat"

    @property
    def description(self) -> str:
        return "General conversation, questions, explanations"

    def run(
        self, query: str, system_prompt: str = "", context: str = ""
    ) -> Generator[AgentEvent, None, None]:
        yield {"type": "agent_progress", "message": "Processing..."}

        sys = system_prompt or get_identity_prompt()
        mem = self.memory.get_relevant_context(query)
        prompt = f"{mem}\n\nUser: {query}" if mem else query
        if context:
            prompt = f"Thinking:\n{context}\n\n{prompt}"

        answer = generate_response(prompt, provider="auto", system_prompt=sys)
        yield {"type": "done", "answer": answer, "sources": []}
