"""Base Agent Protocol — all agents implement this."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any, Generator, Optional, List

from lirox.memory.manager import MemoryManager
from lirox.thinking.scratchpad import Scratchpad

AgentEvent = Dict[str, Any]


class BaseAgent(ABC):
    # BUG-7 FIX: Removed dead PlanningMixin. create_plan(), format_plan_display(),
    # and plan_events() were never called in the active code path.
    def __init__(
        self,
        memory:       MemoryManager = None,
        scratchpad:   Scratchpad    = None,
        profile_data: Dict[str, Any] = None,
    ):
        self.memory       = memory       or MemoryManager(agent_name="base")
        self.scratchpad   = scratchpad   or Scratchpad()
        self.profile_data = profile_data or {}

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    def run(
        self, query: str, system_prompt: str = "", context: str = "", mode: str = "think"
    ) -> Generator[AgentEvent, None, None]: ...

    def is_first_interaction(self) -> bool:
        """True if this agent has never been used before."""
        return (len(self.memory.conversation_buffer) == 0 and
                len(self.memory._lt.get("facts", [])) == 0)

    def get_onboarding_message(self) -> str:
        return (f"👋 Hi! I'm your **{self.name.capitalize()} Agent**.\n"
                f"What would you like to work on?")

    def search_web(self, query: str) -> str:
        try:
            from lirox.tools.search.duckduckgo import search_ddg
            return search_ddg(query)
        except Exception as e:
            return f"Search error: {e}"

    def fetch_url(self, url: str) -> str:
        try:
            import requests
            import re
            from bs4 import BeautifulSoup
            resp = requests.get(url, headers={"User-Agent": "Lirox/1.0"}, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            main = soup.find("main") or soup.find("article") or soup.find("body")
            text = (main.get_text(separator="\n", strip=True) if main
                    else soup.get_text(separator="\n", strip=True))
            return re.sub(r"\n{3,}", "\n\n", text)[:8000]
        except Exception as e:
            return f"Fetch error: {e}"
