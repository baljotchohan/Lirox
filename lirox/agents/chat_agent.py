"""Chat Agent — default conversational fallback. Mode-aware. No planning."""
from typing import Generator

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.utils.llm import generate_response
from lirox.soul import get_identity_prompt
from lirox.config import ThinkingMode


FAST_SUFFIX  = "\n\nBe concise. Answer in 1-3 sentences max. No markdown headers."
THINK_SUFFIX = "\n\nBe thorough and clear. Use markdown for structure when helpful."
COMPLEX_SUFFIX = ""  # Handled by orchestrator system prompt injection


class ChatAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "chat"

    @property
    def description(self) -> str:
        return "General conversation, questions, explanations"

    def run(
        self, query: str, system_prompt: str = "", context: str = "", mode: str = ThinkingMode.THINK
    ) -> Generator[AgentEvent, None, None]:
        from lirox.utils.structured_logger import get_logger, log_with_metadata
        import time
        logger = get_logger(f"lirox.agents.{self.name}")
        start  = time.time()
        log_with_metadata(logger, "INFO", "Agent started", agent=self.name, query=query[:100], mode=mode)



        yield {"type": "agent_progress", "message": "Processing..."}

        base_sys = system_prompt or get_identity_prompt()
        # Mode-specific system prompt suffix
        if mode == ThinkingMode.FAST:
            base_sys += FAST_SUFFIX
        elif mode == ThinkingMode.THINK:
            base_sys += THINK_SUFFIX
        # COMPLEX: orchestrator already injected structured format

        mem    = self.memory.get_relevant_context(query)
        prompt = f"{mem}\n\nUser: {query}" if mem else query
        if context:
            prompt = f"Thinking:\n{context}\n\n{prompt}"

        answer = generate_response(prompt, provider="auto", system_prompt=base_sys)
        self.memory.save_exchange(query, answer)

        log_with_metadata(logger, "INFO", "Agent completed",
                          agent=self.name, duration_ms=int((time.time() - start) * 1000))
        yield {"type": "done", "answer": answer, "sources": []}
