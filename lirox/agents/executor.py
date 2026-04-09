"""
Lirox v1.0.0 — Agent Executor
Runs a custom sub-agent defined by its JSON config, using the LLM
to produce a response that reflects the agent's specialization and
system prompt.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from lirox.agents.manager import AgentManager
from lirox.utils.llm import generate_response


class AgentExecutor:
    """
    Executes a named custom agent with a user query.

    Usage::

        executor = AgentExecutor()
        result   = executor.run("research_bot", "Summarise recent AI papers")
    """

    def __init__(self, manager: Optional[AgentManager] = None) -> None:
        self.manager = manager or AgentManager()

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self, agent_name: str, query: str) -> str:
        """
        Execute the agent identified by *agent_name* on *query*.

        Parameters
        ----------
        agent_name:
            The agent's name (case-insensitive, leading ``@`` stripped).
        query:
            The user's question or instruction for this agent.

        Returns
        -------
        str
            The agent's response, or an error message if execution fails.
        """
        name   = agent_name.lstrip("@")
        config = self.manager.get_agent(name)

        if config is None:
            available = ", ".join(
                f"@{a['name']}" for a in self.manager.list_agents()
            ) or "none"
            return (
                f"❌ Agent '@{name}' not found.\n"
                f"Available agents: {available}\n"
                f"Create one with: /add-agent <description>"
            )

        system_prompt = self._build_system_prompt(config)
        try:
            result = generate_response(
                query,
                provider="auto",
                system_prompt=system_prompt,
            )
            display_name = config.get("name", name)
            return f"🤖 **@{display_name}**:\n\n{result}"
        except Exception as e:
            return f"❌ Agent execution error: {e}"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_system_prompt(self, config: Dict[str, Any]) -> str:
        """Build a system prompt from the agent configuration."""
        parts = []

        custom_prompt = config.get("system_prompt", "").strip()
        if custom_prompt:
            parts.append(custom_prompt)
        else:
            name    = config.get("name", "Agent")
            spec    = config.get("specialization", "general tasks")
            desc    = config.get("description", "")
            fmt     = config.get("response_format", "balanced")
            parts.append(
                f"You are {name}, a specialized AI agent focused on {spec}."
            )
            if desc:
                parts.append(desc)
            if fmt == "concise":
                parts.append("Be brief and to the point.")
            elif fmt == "detailed":
                parts.append("Provide thorough, detailed responses.")

        caps = config.get("capabilities", [])
        if caps:
            parts.append(f"Your capabilities include: {', '.join(caps)}.")

        return "\n".join(parts)
