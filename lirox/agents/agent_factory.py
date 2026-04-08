"""
Lirox v2.0 — Agent Factory

Creates specialized sub-agents dynamically with shared memory,
inter-agent communication, and autonomous delegation.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from lirox.agents.specialized_agents import Agent


class AgentFactory:
    """
    Dynamically creates and manages specialized sub-agents.

    Example:
        factory = AgentFactory()
        agent = factory.create_agent("research", {
            "specialization": "deep web research",
            "tools": ["search", "analyze", "synthesize"],
        })
        result = factory.delegate_task("Find latest AI papers", "research")
    """

    def __init__(self):
        self.agents: Dict[str, "Agent"] = {}
        self._delegation_history: List[Dict[str, Any]] = []

    def create_agent(self, agent_type: str, config: Dict[str, Any]) -> "Agent":
        """
        Instantiate a specialized agent of the given type.

        Args:
            agent_type: One of "research", "code", "security", "testing",
                        "optimization", "documentation", "analysis",
                        "planning", "execution", "verification".
            config:     Optional overrides for name, specialization, tools.

        Returns:
            The created Agent instance (also stored in self.agents).

        Raises:
            ValueError: If agent_type is unknown.
        """
        from lirox.agents.specialized_agents import (
            ResearchAgent, CodeAgent, SecurityAgent, TestingAgent,
            OptimizationAgent, DocumentationAgent, AnalysisAgent,
            PlanningAgent, ExecutionAgent, VerificationAgent,
        )

        agent_map = {
            "research":     ResearchAgent,
            "code":         CodeAgent,
            "security":     SecurityAgent,
            "testing":      TestingAgent,
            "optimization": OptimizationAgent,
            "documentation":DocumentationAgent,
            "analysis":     AnalysisAgent,
            "planning":     PlanningAgent,
            "execution":    ExecutionAgent,
            "verification": VerificationAgent,
        }

        agent_class = agent_map.get(agent_type)
        if not agent_class:
            raise ValueError(f"Unknown agent type: '{agent_type}'. "
                             f"Valid types: {list(agent_map.keys())}")

        name = config.get("name", f"{agent_type}_agent")
        agent = agent_class(
            name=name,
            specialization=config.get("specialization", ""),
            tools=config.get("tools", []),
        )

        # Register and initialize
        self.agents[name] = agent
        agent.learn_role()

        return agent

    def delegate_task(self, task: str, agent_type: str) -> Dict[str, Any]:
        """
        Delegate a task to a named or newly-created agent.

        Args:
            task:       Natural language task description.
            agent_type: Agent type key (also used as lookup name).

        Returns:
            AgentResult dict with status and output.
        """
        name = f"{agent_type}_agent"
        agent = self.agents.get(name)
        if not agent:
            agent = self.create_agent(agent_type, {})

        result = agent.execute(task)
        self._learn_from_delegation(task, result)
        return result

    def list_agents(self) -> List[str]:
        """Return names of all registered agents."""
        return list(self.agents.keys())

    def remove_agent(self, name: str) -> bool:
        """Remove a registered agent by name."""
        if name in self.agents:
            del self.agents[name]
            return True
        return False

    def _learn_from_delegation(self, task: str, result: Dict[str, Any]) -> None:
        self._delegation_history.append({"task": task, "result": result})
