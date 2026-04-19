"""Lirox v1.1 — Training Engine

Simple and reliable:
  - Reads from memory buffer + daily JSONL + session store
  - Single LLM call to extract facts/topics/preferences
  - Incremental (cursor-based, never re-processes old data)
  - Robust JSON extraction and dedup
"""
from __future__ import annotations

import json
import re
import string
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from lirox.config import MEMORY_DIR
from lirox.mind.learnings import LearningsStore
from lirox.utils.llm import generate_response


_EXTRACT_PROMPT = """Analyze this conversation and extract stable knowledge about the user.

CONVERSATION:
{conversation}

Output ONLY one JSON object:
{{
  "facts": ["stable fact about the user (<150 chars each)"],
  "topics": ["specific topics discussed (max 10)"],
  "preferences": {{"category": ["pref1", "pref2"]}},
  "dislikes": ["thing user dislikes"],
  "projects": [{{"name": "Project", "description": "one line"}}]
}}

Rules:
- Only include clearly stated information (no inference).
- Be specific ("Uses Python + FastAPI" not just "codes").
- Empty arrays are fine.
"""


def _normalize(fact: str) -> str:
    s = fact.lower().strip()
    s = s.translate(str.maketrans("", "", string.punctuation))
    return re.sub(r"\s+", " ", s)


class TrainingEngine:
    def __init__(self, learnings: LearningsStore):
        self.learnings = learnings

    def _get_cursor(self) -> Optional[str]:
        return self.learnings.data.get("last_trained_at")

    def _set_cursor(self, ts: str) -> None:
        self.learnings.data["last_trained_at"] = ts
        self.learnings.flush()

    def _gather(self, memory_manager, session_store) -> str:
        cursor = self._get_cursor()
        cursor_dt = None
        if cursor:
            try: cursor_dt = datetime.fromisoformat(cursor)
            except: pass

        pairs: List[Dict] = []

        # 1. Memory buffer
        if memory_manager:
            try:
                for m in memory_manager.conversation_buffer:
                    ts = m.get("ts", "")
                    if cursor_dt and ts:
                        try:
                            if datetime.fromisoformat(ts) <= cursor_dt: continue
                        except: pass
                    pairs.append({"role": m.get("role", "user"),
                                  "content": (m.get("content") or "")[:400], "ts": ts})
            except: pass

        # 2. Daily JSONL logs
        daily_dir = Path(MEMORY_DIR) / "daily"
        if daily_dir.exists():
            for jf in sorted(daily_dir.glob("*.jsonl"), reverse=True)[:14]:
                try:
                    with open(jf, "r", encoding="utf-8", errors="replace") as f:
                        for line in f:
                            try: rec = json.loads(line.strip())
                            except: continue
                            ts = rec.get("ts", "")
                            if cursor_dt and ts:
                                try:
                                    if datetime.fromisoformat(ts) <= cursor_dt: continue
                                except: pass
                            u = (rec.get("user") or "")[:400]
                            a = (rec.get("assistant") or "")[:400]
                            if u: pairs.append({"role": "user", "content": u, "ts": ts})
                            if a: pairs.append({"role": "assistant", "content": a, "ts": ts})
                except: continue

        # 3. Session store
        if session_store:
            try:
                for s in session_store.list_sessions(limit=10):
                    for e in s.entries:
                        if e.role not in ("user", "assistant"): continue
                        ts = getattr(e, "ts", "") or ""
                        if cursor_dt and ts:
                            try:
                                if datetime.fromisoformat(ts) <= cursor_dt: continue
                            except: pass
                        pairs.append({"role": e.role, "content": (e.content or "")[:400], "ts": ts})
            except: pass

        # Dedup
        seen = set(); unique = []
        for p in pairs:
            k = (p["role"], _normalize(p["content"]))
            if k in seen: continue
            seen.add(k); unique.append(p)

        unique.sort(key=lambda r: r.get("ts", ""), reverse=True)

        lines = []; total = 0
        for p in unique:
            label = "USER" if p["role"] == "user" else "AGENT"
            line = f"{label}: {p['content']}"
            if total + len(line) > 6000: break
            lines.append(line); total += len(line)
        return "\n".join(lines)

    def _parse_json(self, text: str):
        text = (text or "").strip()
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            try: return json.loads(m.group(1))
            except: pass
        m2 = re.search(r"(\{.*\})", text, re.DOTALL)
        if m2:
            try: return json.loads(m2.group())
            except: pass
        return {}

    def train(self, memory_manager, session_store=None) -> Dict[str, Any]:
        results = {"facts_added": 0, "topics_bumped": 0, "preferences_added": 0,
                    "projects_found": 0, "errors": []}

        conv = self._gather(memory_manager, session_store)
        if not conv.strip():
            results["errors"].append("No new content since last train.")
            return results

        try:
            raw = generate_response(
                _EXTRACT_PROMPT.format(conversation=conv),
                provider="auto", system_prompt="Extract user knowledge. Output only JSON.")
            data = self._parse_json(raw)
        except Exception as e:
            results["errors"].append(f"LLM extraction failed: {e}")
            return results

        if not isinstance(data, dict):
            results["errors"].append("LLM did not return JSON.")
            return results

        existing = set()
        for f in self.learnings.data.get("user_facts", []):
            text = f.get("fact") if isinstance(f, dict) else str(f)
            existing.add(_normalize(text))

        for fact in data.get("facts", []) or []:
            if not isinstance(fact, str) or len(fact) < 5: continue
            if _normalize(fact) in existing: continue
            self.learnings.add_fact(fact[:280], confidence=0.85, source="train")
            existing.add(_normalize(fact))
            results["facts_added"] += 1

        for topic in data.get("topics", []) or []:
            if isinstance(topic, str) and len(topic) > 2:
                self.learnings.bump_topic(topic.lower()[:60])
                results["topics_bumped"] += 1

        for cat, prefs in (data.get("preferences") or {}).items():
            if not isinstance(prefs, list): prefs = [prefs]
            for p in prefs:
                if isinstance(p, str) and p.strip():
                    self.learnings.add_preference(cat, p.strip()[:200])
                    results["preferences_added"] += 1

        for proj in data.get("projects", []) or []:
            if isinstance(proj, dict) and proj.get("name"):
                self.learnings.add_project(str(proj["name"])[:120],
                                            description=str(proj.get("description", ""))[:300])
                results["projects_found"] += 1

        self._set_cursor(datetime.now().isoformat())
        return results
