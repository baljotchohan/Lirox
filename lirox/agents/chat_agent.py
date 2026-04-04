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
        from lirox.utils.structured_logger import get_logger, log_with_metadata
        import time
        logger = get_logger(f"lirox.agents.{self.name}")
        start = time.time()
        log_with_metadata(logger, "INFO", "Agent started", agent=self.name, query=query[:100])

        yield {"type": "agent_progress", "message": "Processing..."}

        sys = system_prompt or get_identity_prompt()
        mem = self.memory.get_relevant_context(query)
        prompt = f"{mem}\n\nUser: {query}" if mem else query
        if context:
            prompt = f"Thinking:\n{context}\n\n{prompt}"

        answer = generate_response(prompt, provider="auto", system_prompt=sys)
        log_with_metadata(logger, "INFO", "Agent completed", agent=self.name, duration_ms=int((time.time() - start)*1000))
        yield {"type": "done", "answer": answer, "sources": []}
