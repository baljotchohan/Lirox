"""
Lirox v1.0.0 — Agent Manager
Discovers, loads, and manages custom sub-agents saved to data/mind/agents/.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from lirox.config import MIND_AGENTS_DIR


class AgentManager:
    """
    Manages the lifecycle of custom sub-agents: discovery, loading,
    listing, and removal.

    Agents are stored as JSON configuration files under MIND_AGENTS_DIR
    (``data/mind/agents/<name>.json``).
    """

    def __init__(self, agents_dir: str = MIND_AGENTS_DIR) -> None:
        self.agents_dir = agents_dir
        os.makedirs(self.agents_dir, exist_ok=True)

    # ── Discovery ─────────────────────────────────────────────────────────────

    def list_agents(self) -> List[Dict[str, Any]]:
        """Return metadata for every agent found on disk."""
        agents: List[Dict[str, Any]] = []
        for fname in sorted(Path(self.agents_dir).glob("*.json")):
            try:
                with open(fname, encoding="utf-8") as f:
                    data = json.load(f)
                agents.append(
                    {
                        "name":          data.get("name", fname.stem),
                        "description":   data.get("description", ""),
                        "specialization": data.get("specialization", ""),
                        "capabilities":  data.get("capabilities", []),
                        "path":          str(fname),
                    }
                )
            except Exception:
                pass
        return agents

    # ── Loading ───────────────────────────────────────────────────────────────

    def get_agent(self, name: str) -> Optional[Dict[str, Any]]:
        """Load an agent config by name (case-insensitive).  Returns *None* if not found."""
        target = name.strip().lower().replace(" ", "_").lstrip("@")
        for fname in Path(self.agents_dir).glob("*.json"):
            if fname.stem.lower() == target:
                try:
                    with open(fname, encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    return None
        return None

    # ── Persistence ───────────────────────────────────────────────────────────

    def save_agent(self, agent_data: Dict[str, Any]) -> str:
        """
        Persist *agent_data* to disk.

        Returns the absolute path of the saved file.
        """
        name = agent_data.get("name", "unnamed_agent").replace(" ", "_").lower()
        path = os.path.join(self.agents_dir, f"{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(agent_data, f, indent=2)
        return path

    def delete_agent(self, name: str) -> bool:
        """Remove an agent config by name.  Returns *True* on success."""
        target = name.strip().lower().replace(" ", "_").lstrip("@")
        path   = os.path.join(self.agents_dir, f"{target}.json")
        try:
            os.remove(path)
            return True
        except OSError:
            return False

    # ── Helpers ───────────────────────────────────────────────────────────────

    def agent_path(self, name: str) -> str:
        """Return the expected file path for an agent config (may or may not exist)."""
        safe = name.strip().lower().replace(" ", "_").lstrip("@")
        return os.path.join(self.agents_dir, f"{safe}.json")
