"""Base Agent Protocol — all agents implement this."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any, Generator, Optional

from lirox.memory.manager import MemoryManager
from lirox.thinking.scratchpad import Scratchpad

AgentEvent = Dict[str, Any]


class BaseAgent(ABC):
    def __init__(self, memory: MemoryManager = None, scratchpad: Scratchpad = None):
        self.memory = memory or MemoryManager()
        self.scratchpad = scratchpad or Scratchpad()

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    def run(
        self, query: str, system_prompt: str = "", context: str = ""
    ) -> Generator[AgentEvent, None, None]: ...

    # ── Cross-Agent Helpers ───────────────────────────────────────────────

    def search_web(self, query: str) -> str:
        """Search the web — usable by any agent."""
        try:
            from lirox.tools.search.duckduckgo import search_ddg
            return search_ddg(query)
        except Exception as e:
            return f"Search error: {e}"

    def fetch_url(self, url: str) -> str:
        """Fetch a URL's content — usable by any agent."""
        try:
            import requests
            from bs4 import BeautifulSoup
            resp = requests.get(url, headers={"User-Agent": "Lirox/2.1"}, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            main = soup.find("main") or soup.find("article") or soup.find("body")
            text = main.get_text(separator="\n", strip=True) if main else soup.get_text(separator="\n", strip=True)
            import re
            return re.sub(r"\n{3,}", "\n\n", text)[:8000]
        except Exception as e:
            return f"Fetch error: {e}"

    def get_free_data(self, query: str) -> dict:
        """Get free real-time data — usable by any agent."""
        try:
            from lirox.tools.free_data import get_free_data
            return get_free_data(query)
        except Exception:
            return {"status": "error", "answer": ""}
