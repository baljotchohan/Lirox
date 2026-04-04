"""
Lirox v2.0 — Autonomous Learning Engine (Phase 6)

Tracks user interaction patterns over time to build a dynamic context
boost that personalises the system prompt on every session:

- Intent clustering: what does the user ask most?
- Time-of-day patterns: when is the user most active?
- Topic extraction: key nouns from recent exchanges
- Satisfaction signals: detects negative follow-ups (corrections, "no", "wrong")
- Predictions: surfaces likely next queries

All data is persisted atomically to a JSON file.
Thread-safe for concurrent use with background workers.
"""

import json
import os
import re
import threading
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from lirox.config import DATA_DIR


# ─── Constants ───────────────────────────────────────────────────────────────

_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "to", "of", "in",
    "on", "at", "by", "for", "with", "about", "as", "from", "that", "this",
    "it", "its", "or", "and", "but", "if", "then", "than", "so", "yet",
    "how", "what", "when", "where", "who", "why", "which", "i", "me", "my",
    "you", "your", "we", "our", "they", "their", "them", "he", "she", "his",
    "her", "not", "no", "nor", "just", "also", "very", "more", "most",
    "some", "any", "all", "each", "every", "both", "few", "please", "me",
    "give", "tell", "get", "find", "make", "let", "like",
}

_NEGATIVE_SIGNALS = {
    "no", "wrong", "incorrect", "not what", "that's not", "that is not",
    "you're wrong", "error", "mistake", "fix", "correct yourself",
    "wrong answer", "bad response", "redo", "again", "retry",
}


# ─── Intent Classifier ───────────────────────────────────────────────────────

def _classify_intent(text: str) -> str:
    lower = text.lower()
    if any(k in lower for k in ["price", "btc", "bitcoin", "crypto", "stock", "eth"]):
        return "finance"
    if any(k in lower for k in ["weather", "temperature", "forecast"]):
        return "weather"
    if any(k in lower for k in ["code", "python", "function", "debug", "error", "script", "api"]):
        return "coding"
    if any(k in lower for k in ["write", "draft", "essay", "email", "blog", "post"]):
        return "writing"
    if any(k in lower for k in ["research", "summarize", "explain", "overview", "history"]):
        return "research"
    if any(k in lower for k in ["plan", "schedule", "goal", "task", "todo"]):
        return "planning"
    if any(k in lower for k in ["news", "latest", "trending", "today", "current"]):
        return "news"
    return "general"


def _extract_topics(text: str, top_n: int = 5) -> List[str]:
    """Extract meaningful nouns/topics from text."""
    words = re.findall(r"[a-zA-Z]{4,}", text.lower())
    meaningful = [w for w in words if w not in _STOP_WORDS]
    counts = Counter(meaningful)
    return [w for w, _ in counts.most_common(top_n)]


def _has_negative_signal(user_input: str) -> bool:
    lower = user_input.lower().strip()
    return any(sig in lower for sig in _NEGATIVE_SIGNALS)


# ─── LearningEngine ──────────────────────────────────────────────────────────

class LearningEngine:
    """
    Tracks and learns from user interactions over time.

    Usage:
        engine = LearningEngine()
        engine.on_session_start()
        engine.on_interaction("what is bitcoin?", "Bitcoin is...")
        boost = engine.get_context_boost()  # inject into system prompt
    """

    DEFAULT_DATA = {
        "version": "2.0.0",
        "total_sessions": 0,
        "total_interactions": 0,
        "intent_counts": {},          # {intent: count}
        "topic_counts": {},           # {topic: count}
        "hour_activity": {},          # {"0"-"23": count}
        "satisfaction_score": 1.0,    # 0.0 – 1.0, decays on negative signals
        "negative_signals": 0,
        "recent_queries": [],         # last 20 queries (ring buffer)
        "recent_topics": [],          # last 30 extracted topics
        "last_session": None,
        "created_at": None,
    }

    def __init__(self, storage_file: str = None):
        if storage_file is None:
            storage_file = os.path.join(DATA_DIR, "learning_engine.json")
        self._path = storage_file
        self._lock = threading.Lock()
        self._data = self._load()

    # ─── Persistence ──────────────────────────────────────────────────────

    def _load(self) -> dict:
        if os.path.exists(self._path):
            try:
                with open(self._path, "r") as f:
                    stored = json.load(f)
                    merged = dict(self.DEFAULT_DATA)
                    merged.update(stored)
                    return merged
            except (json.JSONDecodeError, IOError):
                pass
        data = dict(self.DEFAULT_DATA)
        data["created_at"] = datetime.now().isoformat()
        return data

    def _save(self):
        """Atomic write to prevent corruption."""
        tmp = self._path + ".tmp"
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(tmp, "w") as f:
                json.dump(self._data, f, indent=2)
            os.replace(tmp, self._path)
        except Exception:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    # ─── Public API ───────────────────────────────────────────────────────

    def on_session_start(self):
        """Call once at agent startup."""
        with self._lock:
            self._data["total_sessions"] += 1
            self._data["last_session"] = datetime.now().isoformat()

            # Track hour of activity
            hour = str(datetime.now().hour)
            self._data["hour_activity"][hour] = self._data["hour_activity"].get(hour, 0) + 1

            self._save()

    def on_interaction(self, user_input: str, agent_response: str):
        """
        Record a single exchange. Runs fast; background threading handled by caller.
        """
        with self._lock:
            self._data["total_interactions"] += 1

            # Intent tracking
            intent = _classify_intent(user_input)
            ic = self._data["intent_counts"]
            ic[intent] = ic.get(intent, 0) + 1

            # Topic extraction
            topics = _extract_topics(user_input + " " + agent_response, top_n=3)
            tc = self._data["topic_counts"]
            for t in topics:
                tc[t] = tc.get(t, 0) + 1

            # Recent queries (ring buffer, max 20)
            rq = self._data["recent_queries"]
            rq.append(user_input[:120])
            if len(rq) > 20:
                self._data["recent_queries"] = rq[-20:]

            # Recent topics (ring buffer, max 30)
            rt = self._data["recent_topics"]
            rt.extend(topics)
            if len(rt) > 30:
                self._data["recent_topics"] = rt[-30:]

            # Satisfaction signal
            if _has_negative_signal(user_input):
                self._data["negative_signals"] += 1
                # Decay satisfaction (min 0.2)
                self._data["satisfaction_score"] = max(
                    0.2,
                    self._data["satisfaction_score"] * 0.85
                )
            else:
                # Slowly recover satisfaction
                self._data["satisfaction_score"] = min(
                    1.0,
                    self._data["satisfaction_score"] + 0.02
                )

            self._save()

    def get_context_boost(self) -> str:
        """
        Return a compact text block to inject into the system prompt,
        personalising the agent based on learned patterns.
        """
        with self._lock:
            d = self._data

        # Top intents
        top_intents = sorted(d["intent_counts"].items(), key=lambda x: x[1], reverse=True)[:3]
        intent_str = ", ".join(f"{i} ({c}x)" for i, c in top_intents) if top_intents else "general"

        # Top topics
        top_topics = sorted(d["topic_counts"].items(), key=lambda x: x[1], reverse=True)[:6]
        topic_str = ", ".join(t for t, _ in top_topics) if top_topics else "none yet"

        # Most active hour
        ha = d["hour_activity"]
        if ha:
            active_hour = max(ha, key=ha.get)
            active_time = f"{active_hour}:00"
        else:
            active_time = "unknown"

        # Predictions: surface last 3 unique recent queries
        recent = list(dict.fromkeys(d["recent_queries"]))[-3:]
        pred_str = " | ".join(f'"{q[:50]}"' for q in recent) if recent else "none"

        sat = d["satisfaction_score"]
        sat_note = ""
        if sat < 0.6:
            sat_note = "\n- CAUTION: Recent negative feedback detected. Be more precise and verify facts before answering."

        return (
            f"\nLEARNED USER PATTERNS (v2.0)\n"
            f"- Sessions: {d['total_sessions']} | Interactions: {d['total_interactions']}\n"
            f"- Top intents: {intent_str}\n"
            f"- Frequent topics: {topic_str}\n"
            f"- Most active hour: {active_time}\n"
            f"- Recent queries: {pred_str}\n"
            f"- Satisfaction: {sat:.0%}{sat_note}\n"
        )

    def get_stats_display(self) -> dict:
        """Return a summary dict for /profile display."""
        with self._lock:
            d = self._data
        top_int = sorted(d["intent_counts"].items(), key=lambda x: x[1], reverse=True)[:5]
        top_top = sorted(d["topic_counts"].items(), key=lambda x: x[1], reverse=True)[:5]
        return {
            "total_sessions": d["total_sessions"],
            "total_interactions": d["total_interactions"],
            "satisfaction_score": d["satisfaction_score"],
            "negative_signals": d["negative_signals"],
            "top_intents": top_int,
            "top_topics": top_top,
            "most_active_hour": max(d["hour_activity"], key=d["hour_activity"].get) if d["hour_activity"] else "N/A",
            "last_session": d["last_session"],
        }
