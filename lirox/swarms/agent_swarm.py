"""
Lirox v2.0 — Agent Swarm

Coordinate multiple specialized agents working in parallel toward
a shared goal, with result aggregation and collective learning.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from lirox.agents.agent_factory import AgentFactory


class AgentSwarm:
    """
    Manages a swarm of specialized agents collaborating on a shared task.

    Usage:
        swarm = AgentSwarm()
        result = swarm.coordinate_task("Analyze recent AI papers and summarize findings")
    """

    def __init__(self, factory: Optional[AgentFactory] = None):
        self.factory  = factory or AgentFactory()
        self._history: List[Dict[str, Any]] = []

    def coordinate_task(
        self,
        task: str,
        agent_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Distribute a task across multiple specialized agents and
        aggregate their results into a single coherent answer.

        Args:
            task:        The task to complete.
            agent_types: List of agent type keys to use.
                         Defaults to ["research", "analysis", "planning",
                         "execution", "verification"].

        Returns:
            Aggregated result dict.
        """
        if agent_types is None:
            agent_types = ["research", "analysis", "planning", "execution", "verification"]

        # Create agents
        agents = []
        for agent_type in agent_types:
            try:
                agent = self.factory.create_agent(agent_type, {"name": f"{agent_type}_swarm"})
                agents.append((agent_type, agent))
            except Exception as e:
                # Skip unknown agent types gracefully
                continue

        # Execute in simulated parallel
        results = []
        for agent_type, agent in agents:
            try:
                result = agent.execute_parallel(task)
                results.append(result)
            except Exception as e:
                results.append({"status": "error", "error": str(e), "agent": agent_type})

        # Aggregate
        final = self.aggregate_results(results)

        # Learn
        self._learn_from_swarm(agents, results)
        self._history.append({"task": task, "agents": [a for a, _ in agents], "result": final})

        return final

    def aggregate_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge results from multiple agents into a single response.

        Args:
            results: List of agent result dicts.

        Returns:
            Aggregated dict with combined outputs and metadata.
        """
        successes = [r for r in results if r.get("status") == "success"]
        outputs   = [r.get("output", "") for r in successes if r.get("output")]

        return {
            "status":        "success" if successes else "error",
            "outputs":       outputs,
            "combined":      "\n".join(str(o) for o in outputs),
            "agent_count":   len(results),
            "success_count": len(successes),
        }

    def spawn_agent(self, agent_type: str, config: Optional[Dict[str, Any]] = None) -> Any:
        """Dynamically spawn a new agent and add it to the swarm."""
        return self.factory.create_agent(agent_type, config or {})

    def get_history(self) -> List[Dict[str, Any]]:
        """Return history of all swarm tasks."""
        return list(self._history)

    def _learn_from_swarm(self, agents: List, results: List[Dict[str, Any]]) -> None:
        """Aggregate learning from all agent results."""
        pass  # Hook for future self-learning integration
