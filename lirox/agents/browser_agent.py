"""Browser Agent — Lightpanda-inspired web automation + content extraction."""
from __future__ import annotations

import re
from typing import Generator

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.utils.llm import generate_response


class BrowserAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "browser"

    @property
    def description(self) -> str:
        return "Web browsing, content extraction, navigation"

    def run(
        self, query: str, system_prompt: str = "", context: str = ""
    ) -> Generator[AgentEvent, None, None]:
        yield {"type": "agent_progress", "message": "Browser Agent starting..."}
        url_match = re.search(r"https?://\S+", query)

        if url_match:
            url = url_match.group()
            yield {"type": "tool_call", "message": f"Fetching {url}..."}
            content = self._fetch(url)
            if len(content) > 3000:
                yield {"type": "agent_progress", "message": "Summarizing..."}
                answer = generate_response(
                    f"Summarize for: {query}\n\nContent:\n{content[:8000]}",
                    provider="auto",
                    system_prompt="Concise web content summarizer.",
                )
            else:
                answer = content
        else:
            yield {"type": "tool_call", "message": "Searching..."}
            from lirox.tools.search.duckduckgo import search_ddg

            results = search_ddg(query)
            prompt = f"Query: {query}\n\nResults:\n{results}"
            if context:
                prompt = f"Thinking:\n{context}\n\n{prompt}"
            answer = generate_response(
                prompt,
                provider="auto",
                system_prompt=system_prompt or "Web research assistant.",
            )

        yield {"type": "done", "answer": answer, "sources": []}

    def _fetch(self, url: str) -> str:
        try:
            import requests
            from bs4 import BeautifulSoup

            resp = requests.get(
                url,
                headers={"User-Agent": "Lirox/2.0"},
                timeout=15,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            main = soup.find("main") or soup.find("article") or soup.find("body")
            text = (
                main.get_text(separator="\n", strip=True)
                if main
                else soup.get_text(separator="\n", strip=True)
            )
            return re.sub(r"\n{3,}", "\n\n", text)[:10000]
        except Exception as e:
            return f"Fetch error: {e}"
