"""Research Agent — Multi-source deep research and synthesis."""
from typing import Generator

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.utils.llm import generate_response
from lirox.config import MAX_LLM_PROMPT_CHARS


class ResearchAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "research"

    @property
    def description(self) -> str:
        return "Deep multi-source research and analysis"

    def run(
        self, query: str, system_prompt: str = "", context: str = ""
    ) -> Generator[AgentEvent, None, None]:
        from lirox.utils.structured_logger import get_logger, log_with_metadata
        import time
        logger = get_logger(f"lirox.agents.{self.name}")
        start = time.time()
        log_with_metadata(logger, "INFO", "Agent started", agent=self.name, query=query[:100])

        yield {"type": "agent_progress", "message": "Research Agent starting..."}
        yield {"type": "tool_call", "message": "Searching multiple sources..."}
        results = self._multi_search(query)
        yield {"type": "agent_progress", "message": "Synthesizing..."}

        prompt = f"Query: {query}\n\nSearch Results:\n{results[:MAX_LLM_PROMPT_CHARS]}"
        if context:
            prompt += f"\n\nContext: {context}"
        prompt += "\n\nSynthesize comprehensively. Cross-reference. Note conflicts."

        sys = system_prompt or "Thorough research analyst. Well-sourced answers."
        answer = generate_response(prompt, provider="auto", system_prompt=sys)
        log_with_metadata(logger, "INFO", "Agent completed", agent=self.name, duration_ms=int((time.time() - start)*1000))
        yield {"type": "done", "answer": answer, "sources": []}

    def _multi_search(self, query: str) -> str:
        results = []
        try:
            from lirox.tools.search.duckduckgo import search_ddg

            r = search_ddg(query)
            if r and "error" not in r.lower():
                results.append(f"## DuckDuckGo\n{r}")
        except Exception as e:
            from lirox.utils.structured_logger import get_logger
            get_logger("lirox.agents.research").warning(f"Non-critical DDG error: {e}")
        try:
            from lirox.tools.search.tavily import search_tavily

            r = search_tavily(query)
            if r:
                results.append(f"## Tavily\n{r}")
        except Exception as e:
            from lirox.utils.structured_logger import get_logger
            get_logger("lirox.agents.research").warning(f"Non-critical Tavily error: {e}")
        return "\n\n".join(results) if results else "No results. Answering from knowledge."
