"""Lirox v1.1 — Agent Manager

Simplified agent management. The cryptographic identity system (lirox.security)
was removed in v1.1 as dead weight. Agent names are now stored plainly in
profile.json and the registry JSON files.
"""
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

_logger = logging.getLogger("lirox.agents.manager")


class AgentManager:
    """
    Manages agent registry and configuration.
    v1.1: Removed cryptographic identity system (was never used at runtime).
    """

    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir or os.path.expanduser("~/.lirox/agents"))
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_agent_dir(self, name: str) -> Path:
        agent_dir = self.base_dir / name
        agent_dir.mkdir(parents=True, exist_ok=True)
        return agent_dir

    def create_or_load_identity(self, name: str) -> Dict:
        """Load or create a simple agent identity (name + metadata)."""
        identity_path = self._get_agent_dir(name) / "identity.json"

        if identity_path.exists():
            try:
                with open(identity_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                _logger.error("Failed to load identity for %s: %s", name, e)

        # Create a simple identity record
        identity = {
            "name": name,
            "version": "1.1",
            "created_at": __import__("datetime").datetime.now().isoformat(),
        }
        with open(identity_path, "w") as f:
            json.dump(identity, f, indent=2)

        return identity

    def list_agents(self) -> List[str]:
        """List all registered agents."""
        if not self.base_dir.exists():
            return []
        return [d.name for d in self.base_dir.iterdir() if d.is_dir()]

    def kill_agent(self, name: str):
        """Placeholder for agent termination."""
        _logger.critical("KILL SWITCH INITIATED for agent: %s", name)
