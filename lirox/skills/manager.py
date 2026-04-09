"""
Lirox v1.0.0 — Skill Manager
Discovers, loads, and manages reusable skills saved to /lirox/skills/.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from lirox.config import MIND_SKILLS_DIR


class SkillManager:
    """
    Manages the lifecycle of skills: discovery, loading, listing, and removal.

    Skills are stored as JSON files under MIND_SKILLS_DIR
    (``data/mind/skills/<name>.json``).
    """

    def __init__(self, skills_dir: str = MIND_SKILLS_DIR) -> None:
        self.skills_dir = skills_dir
        os.makedirs(self.skills_dir, exist_ok=True)

    # ── Discovery ─────────────────────────────────────────────────────────────

    def list_skills(self) -> List[Dict[str, Any]]:
        """Return metadata for every skill found on disk."""
        skills: List[Dict[str, Any]] = []
        for fname in sorted(Path(self.skills_dir).glob("*.json")):
            try:
                with open(fname, encoding="utf-8") as f:
                    data = json.load(f)
                skills.append(
                    {
                        "name":        data.get("name", fname.stem),
                        "description": data.get("description", ""),
                        "path":        str(fname),
                        "parameters":  data.get("parameters", []),
                        "output_type": data.get("output_type", "string"),
                    }
                )
            except Exception:
                pass
        return skills

    # ── Loading ───────────────────────────────────────────────────────────────

    def get_skill(self, name: str) -> Optional[Dict[str, Any]]:
        """Load a skill by name (case-insensitive).  Returns ``None`` if not found."""
        target = name.strip().lower().replace(" ", "_")
        for fname in Path(self.skills_dir).glob("*.json"):
            if fname.stem.lower() == target:
                try:
                    with open(fname, encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    return None
        return None

    # ── Persistence ───────────────────────────────────────────────────────────

    def save_skill(self, skill_data: Dict[str, Any]) -> str:
        """
        Persist *skill_data* to disk.

        Returns the absolute path of the saved file.
        """
        name = skill_data.get("name", "unnamed_skill").replace(" ", "_").lower()
        path = os.path.join(self.skills_dir, f"{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(skill_data, f, indent=2)
        return path

    def delete_skill(self, name: str) -> bool:
        """Remove a skill by name.  Returns *True* on success."""
        skill = self.get_skill(name)
        if skill is None:
            return False
        target = name.strip().lower().replace(" ", "_")
        path = os.path.join(self.skills_dir, f"{target}.json")
        try:
            os.remove(path)
            return True
        except OSError:
            return False

    # ── Helpers ───────────────────────────────────────────────────────────────

    def skill_path(self, name: str) -> str:
        """Return the expected file path for a skill (may or may not exist)."""
        safe = name.strip().lower().replace(" ", "_")
        return os.path.join(self.skills_dir, f"{safe}.json")
