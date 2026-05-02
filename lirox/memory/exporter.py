"""Lirox v1.1 — Memory Exporter
Export all learning data as JSON for the /export-memory command.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from lirox.config import APP_VERSION


def export_learnings(output_path: Optional[str] = None) -> str:
    """
    Export all learning data as JSON.
    """
    from lirox.agents.profile import UserProfile
    from lirox.memory.learnings import LearningsStore

    profile = UserProfile()
    learnings = LearningsStore()

    session_summaries = []
    try:
        from lirox.memory.session_store import SessionStore
        store = SessionStore()
        sessions = store.list_sessions(limit=50)
        for s in sessions:
            session_summaries.append({
                "id": getattr(s, "session_id", str(s)),
                "created_at": getattr(s, "created_at", ""),
                "entries": len(getattr(s, "entries", [])),
            })
    except Exception:
        pass

    export_data = {
        "export_date": datetime.now().isoformat(),
        "lirox_version": APP_VERSION,
        "source": "Lirox",
        "profile": profile.data,
        "facts": learnings.data.get("user_facts", []),
        "topics": learnings.data.get("topics", {}),
        "preferences": learnings.data.get("preferences", {}),
        "projects": learnings.data.get("projects", []),
        "dislikes": learnings.data.get("dislikes", []),
        "communication_style": learnings.data.get("communication_style", {}),
        "custom_notes": learnings.data.get("custom_notes", []),
        "sessions": session_summaries,
    }

    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(
            Path.home() / f"lirox_memory_export_{timestamp}.json"
        )

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)

    return output_path
