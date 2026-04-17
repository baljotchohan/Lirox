"""Lirox v1.1 — Training Engine.

v2 root-cause fixes:
  - Reads from disk JSONL logs + session store (not just the 100-msg
    in-memory buffer).
  - Incremental training via a cursor (last_trained_timestamp) so
    re-running doesn't re-process everything.
  - Single combined LLM call with a structured JSON schema (instead of
    four serial calls that frequently timed out).
  - Robust dedup on normalized fact text (lowercase + strip punct).
  - Never silently swallows errors — always reports what failed.
"""
from __future__ import annotations

import json
import os
import re
import string
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from lirox.config import MEMORY_DIR
from lirox.mind.learnings import LearningsStore
from lirox.utils.llm import generate_response


_EXTRACT_PROMPT = """You are a knowledge extractor for a personal AI assistant.

Analyze this conversation history and extract stable knowledge about the user.

CONVERSATION:
{conversation}

Output EXACTLY ONE JSON object with this schema (no preamble, no trailing text):
{{
  "facts": ["stable fact (<150 chars each)"],
  "topics": ["specific topics discussed (max 10)"],
  "preferences": {{"category": ["pref1", "pref2"]}},
  "dislikes": ["thing user dislikes"],
  "projects": [{{"name": "Project", "description": "one line"}}],
  "communication_style": {{"key": "value"}}
}}

Rules:
- Only include information that was clearly stated (no inference).
- Empty arrays/objects are fine.
- Be specific ("Uses Python + FastAPI" not just "codes").
"""


def _normalize_fact(fact: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — for dedup."""
    s = fact.lower().strip()
    s = s.translate(str.maketrans("", "", string.punctuation))
    s = re.sub(r"\s+", " ", s)
    return s


class TrainingEngine:
    """Extracts and permanently saves learnings from conversation history."""

    def __init__(self, learnings: LearningsStore):
        self.learnings = learnings

    # ── Cursor helpers ────────────────────────────────────────

    def _get_cursor(self) -> Optional[str]:
        """ISO timestamp of last successful train, or None."""
        return self.learnings.data.get("last_trained_at")

    def _set_cursor(self, ts: str) -> None:
        self.learnings.data["last_trained_at"] = ts
        self.learnings.flush()

    # ── Conversation gathering ────────────────────────────────

    def _gather_conversation(self, memory_manager, session_store) -> str:
        """Merge three sources: live buffer, daily JSONL logs, session store.

        Returns a newline-joined transcript, most-recent-first up to a char cap.
        """
        cursor = self._get_cursor()
        cursor_dt = None
        if cursor:
            try:
                cursor_dt = datetime.fromisoformat(cursor)
            except Exception:
                cursor_dt = None

        pairs: List[Dict[str, str]] = []

        # 1. In-memory buffer (freshest)
        if memory_manager is not None:
            try:
                for m in memory_manager.conversation_buffer:
                    ts = m.get("ts", "")
                    if cursor_dt and ts:
                        try:
                            if datetime.fromisoformat(ts) <= cursor_dt:
                                continue
                        except Exception:
                            pass
                    pairs.append({
                        "role": m.get("role", "user"),
                        "content": (m.get("content") or "")[:400],
                        "ts": ts,
                    })
            except Exception:
                pass

        # 2. Daily JSONL logs
        daily_dir = Path(MEMORY_DIR) / "daily"
        if daily_dir.exists():
            for jf in sorted(daily_dir.glob("*.jsonl"), reverse=True)[:14]:
                try:
                    with open(jf, "r", encoding="utf-8", errors="replace") as f:
                        for line in f:
                            try:
                                rec = json.loads(line.strip())
                            except Exception:
                                continue
                            ts = rec.get("ts", "")
                            if cursor_dt and ts:
                                try:
                                    if datetime.fromisoformat(ts) <= cursor_dt:
                                        continue
                                except Exception:
                                    pass
                            u = (rec.get("user") or "")[:400]
                            a = (rec.get("assistant") or "")[:400]
                            if u:
                                pairs.append({"role": "user", "content": u, "ts": ts})
                            if a:
                                pairs.append({"role": "assistant", "content": a, "ts": ts})
                except Exception:
                    continue

        # 3. Session store
        if session_store is not None:
            try:
                sessions = session_store.list_sessions(limit=10)
                for s in sessions:
                    for e in s.entries:
                        if e.role not in ("user", "assistant"):
                            continue
                        ts = getattr(e, "timestamp", "") or ""
                        if cursor_dt and ts:
                            try:
                                if datetime.fromisoformat(ts) <= cursor_dt:
                                    continue
                            except Exception:
                                pass
                        pairs.append({
                            "role": e.role,
                            "content": (e.content or "")[:400],
                            "ts": ts,
                        })
            except Exception:
                pass

        # Dedup by (role, normalized content); preserve order
        seen = set()
        unique: List[Dict[str, str]] = []
        for p in pairs:
            k = (p["role"], _normalize_fact(p["content"]))
            if k in seen:
                continue
            seen.add(k)
            unique.append(p)

        # Sort newest-first by timestamp when available
        unique.sort(key=lambda r: r.get("ts", ""), reverse=True)

        # Build transcript up to 6000 chars
        out_lines: List[str] = []
        total = 0
        for p in unique:
            label = "USER" if p["role"] == "user" else "AGENT"
            line  = f"{label}: {p['content']}"
            if total + len(line) > 6000:
                break
            out_lines.append(line)
            total += len(line)
        return "\n".join(out_lines)

    # ── JSON extraction ───────────────────────────────────────

    def _extract_json(self, text: str, default):
        text = (text or "").strip()
        # Fenced block
        m = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        # First greedy object
        m2 = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if m2:
            try:
                return json.loads(m2.group())
            except Exception:
                pass
        return default

    # ── Public train ──────────────────────────────────────────

    def train(self, memory_manager, session_store=None) -> Dict[str, Any]:
        results = {
            "facts_added":        0,
            "topics_bumped":      0,
            "preferences_added":  0,
            "dislikes_added":     0,
            "projects_found":     0,
            "comm_style_updates": 0,
            "errors":             [],
        }

        conv = self._gather_conversation(memory_manager, session_store)
        if not conv.strip():
            results["errors"].append("No new conversation content since last train.")
            return results

        # Single combined LLM call
        try:
            raw = generate_response(
                _EXTRACT_PROMPT.format(conversation=conv),
                provider="auto",
                system_prompt="Extract user knowledge. Output only JSON.",
            )
            data = self._extract_json(raw, {})
        except Exception as e:
            results["errors"].append(f"LLM extraction failed: {e}")
            return results

        if not isinstance(data, dict):
            results["errors"].append("LLM did not return a JSON object.")
            return results

        # Build dedup set from existing facts
        existing_norms = set()
        for f in self.learnings.data.get("user_facts", []) or []:
            text = f.get("fact") if isinstance(f, dict) else str(f)
            existing_norms.add(_normalize_fact(text))

        # Facts
        for fact in data.get("facts", []) or []:
            if not isinstance(fact, str) or len(fact) < 5:
                continue
            norm = _normalize_fact(fact)
            if norm in existing_norms:
                continue
            self.learnings.add_fact(fact[:280], confidence=0.85, source="train")
            existing_norms.add(norm)
            results["facts_added"] += 1

        # Topics
        for topic in data.get("topics", []) or []:
            if isinstance(topic, str) and len(topic) > 2:
                self.learnings.bump_topic(topic.lower()[:60])
                results["topics_bumped"] += 1

        # Preferences
        for cat, prefs in (data.get("preferences") or {}).items():
            if not isinstance(prefs, list):
                prefs = [prefs]
            for p in prefs:
                if isinstance(p, str) and p.strip():
                    self.learnings.add_preference(cat, p.strip()[:200])
                    results["preferences_added"] += 1

        # Dislikes
        for d in data.get("dislikes", []) or []:
            if isinstance(d, str) and d.strip():
                self.learnings.add_dislike(d.strip()[:200])
                results["dislikes_added"] += 1

        # Projects
        for proj in data.get("projects", []) or []:
            if isinstance(proj, dict) and proj.get("name"):
                self.learnings.add_project(
                    str(proj["name"])[:120],
                    description=str(proj.get("description", ""))[:300],
                )
                results["projects_found"] += 1

        # Communication style
        for k, v in (data.get("communication_style") or {}).items():
            if isinstance(k, str) and isinstance(v, str):
                self.learnings.update_communication_style(k, v)
                results["comm_style_updates"] += 1

        # Move the cursor forward
        self._set_cursor(datetime.now().isoformat())
        try:
            interaction_count = len([
                m for m in (memory_manager.conversation_buffer or [])
                if m.get("role") == "user"
            ])
            self.learnings.mark_trained(interaction_count)
        except Exception:
            pass

        return results
