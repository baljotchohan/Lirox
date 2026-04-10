"""Base Agent Protocol — all agents implement this. Includes PlanningMixin."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any, Generator, Optional, List

from lirox.memory.manager import MemoryManager
from lirox.thinking.scratchpad import Scratchpad

AgentEvent = Dict[str, Any]

FIRST_INTERACTION_KEY = "_first_interaction_shown"


class PlanningMixin:
    """
    Adds plan-create → show → confirm → execute flow to any agent.
    Planning is ONLY available in agents (not in main chat/FAST mode).
    """

    def create_plan(self, objective: str, steps: List[str]) -> dict:
        return {
            "objective": objective,
            "steps":     steps,
            "confirmed": False,
        }

    def format_plan_display(self, plan: dict) -> str:
        lines = [
            f"\n📋 EXECUTION PLAN",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"🎯 Objective: {plan['objective']}",
            "",
            "Steps:",
        ]
        for i, step in enumerate(plan["steps"], 1):
            lines.append(f"  {i}. {step}")
        lines.append("\nType [y] to execute or [n] to cancel.")
        return "\n".join(lines)

    def plan_events(self, plan: dict) -> Generator[AgentEvent, None, None]:
        """Yield a plan display event — agent waits for user confirmation."""
        yield {
            "type":    "plan_display",
            "message": self.format_plan_display(plan),
            "plan":    plan,
        }


class BaseAgent(ABC, PlanningMixin):
    def __init__(
        self,
        memory:       MemoryManager = None,
        scratchpad:   Scratchpad    = None,
        profile_data: Dict[str, Any] = None,
    ):
        self.memory       = memory       or MemoryManager(agent_name=self.name if hasattr(self, '_name') else "base")
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

    # ── First Interaction Onboarding ────────────────────────────────────────

    def is_first_interaction(self) -> bool:
        """True if this agent has never been used before (no memory entries)."""
        return len(self.memory.conversation_buffer) == 0 and \
               len(self.memory._lt.get("facts", [])) == 0

    def get_onboarding_message(self) -> str:
        """Override per-agent for custom onboarding. Default fallback."""
        return (
            f"👋 Hi! I'm your **{self.name.capitalize()} Agent** — still a baby!\n\n"
            f"I get smarter as you use me. You can also teach me by:\n"
            f"  • Adding relevant API keys in `/setup`\n"
            f"  • Giving me context about your needs\n\n"
            f"What would you like to work on?"
        )

    # ── Cross-Agent Helpers ─────────────────────────────────────────────────

    def search_web(self, query: str) -> str:
        try:
            from lirox.tools.search.duckduckgo import search_ddg
            return search_ddg(query)
        except Exception as e:
            return f"Search error: {e}"

    def fetch_url(self, url: str) -> str:
        try:
            import requests, re
            from bs4 import BeautifulSoup
            resp = requests.get(url, headers={"User-Agent": "Lirox/3.0"}, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            main = soup.find("main") or soup.find("article") or soup.find("body")
            text = main.get_text(separator="\n", strip=True) if main else soup.get_text(separator="\n", strip=True)
            return re.sub(r"\n{3,}", "\n\n", text)[:8000]
        except Exception as e:
            return f"Fetch error: {e}"


