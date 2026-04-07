"""3-Tier Memory: Buffer + Daily logs + Long-term facts. Per-agent isolated."""
import json
import os
import threading
from datetime import datetime
from typing import Dict, List, Optional

from lirox.config import MEMORY_DIR, MEMORY_LIMIT, MAX_MEMORY_ENTRY_CHARS


class MemoryManager:
    def __init__(self, agent_name: str = "global"):
        self.agent_name         = agent_name
        self._lock               = threading.Lock()
        self.conversation_buffer: List[Dict] = []
        # Each agent gets its own long-term memory file
        safe_name  = agent_name.replace("/", "_").replace("\\", "_")
        self.lt_path = os.path.join(MEMORY_DIR, f"long_term_{safe_name}.json")
        self._lt     = self._load(self.lt_path) or {"facts": [], "preferences": {}}

    def save_exchange(self, user_msg: str, asst_msg: str):
        ts = datetime.now().isoformat()
        with self._lock:
            self.conversation_buffer.append({"role": "user",      "content": user_msg, "ts": ts})
            self.conversation_buffer.append({"role": "assistant", "content": str(asst_msg)[:MAX_MEMORY_ENTRY_CHARS], "ts": ts})
            if len(self.conversation_buffer) > MEMORY_LIMIT * 2:
                self.conversation_buffer = self.conversation_buffer[-MEMORY_LIMIT:]

        safe_name = self.agent_name.replace("/", "_").replace("\\", "_")
        daily = os.path.join(
            MEMORY_DIR, "daily",
            f"{safe_name}_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        )
        try:
            with open(daily, "a") as f:
                f.write(json.dumps({
                    "user":      user_msg,
                    "assistant": str(asst_msg)[:MAX_MEMORY_ENTRY_CHARS],
                    "ts":        ts
                }) + "\n")
        except Exception as e:
            from lirox.utils.structured_logger import get_logger
            get_logger("lirox.memory").warning(f"Daily write error: {e}")

    def get_relevant_context(self, query: str, max_items: int = 10) -> str:
        """Return only relevant context — never dump all buffer on unrelated queries."""
        with self._lock:
            buffer_snapshot = list(self.conversation_buffer)
        if not buffer_snapshot:
            return ""
        qw = set(query.lower().split())
        scored = []
        for m in buffer_snapshot:
            cw = set(m["content"].lower().split())
            s  = len(qw & cw)
            if query.lower() in m["content"].lower():
                s += 5
            if s > 0:
                scored.append((s, m))
        if not scored:
            return ""  # FIX: don't dump unrelated context
        scored.sort(key=lambda x: x[0], reverse=True)
        rel   = [m for _, m in scored[:max_items]]
        lines = ["--- Context ---"]
        for m in rel:
            label = "User" if m["role"] == "user" else "Assistant"
            lines.append(f"{label}: {m['content']}")
        return "\n".join(lines)

    def search(self, query: str, limit: int = 5) -> str:
        with self._lock:
            buffer_snapshot = list(self.conversation_buffer)
            facts_snapshot  = list(self._lt.get("facts", []))
        results = []
        for m in buffer_snapshot:
            if query.lower() in m["content"].lower():
                results.append(m["content"][:200])
        for f in facts_snapshot:
            if any(w in f.lower() for w in query.lower().split()):
                results.append(f)
        return "\n".join(results[:limit]) if results else ""

    def get_pattern_insights(self, limit: int = 3) -> List[str]:
        """Return the most frequently asked topics (for proactive suggestions)."""
        from collections import Counter
        import re
        with self._lock:
            buffer_snapshot = list(self.conversation_buffer)
        words = []
        for m in buffer_snapshot:
            if m["role"] == "user":
                # Extract meaningful words (>4 chars)
                words.extend(w for w in re.findall(r'\b\w{4,}\b', m["content"].lower())
                             if w not in {'what', 'when', 'where', 'which', 'that', 'this', 'with', 'from', 'about', 'have', 'will', 'your'})
        if not words:
            return []
        top = Counter(words).most_common(limit)
        return [w for w, _ in top]

    def add_fact(self, fact: str):
        with self._lock:
            facts = self._lt.get("facts", [])
            # Exact-match deduplication plus simple fuzzy check (normalized)
            fact_norm = " ".join(sorted(fact.lower().split()))
            for existing in facts:
                if existing == fact:
                    return  # exact duplicate — skip
                existing_norm = " ".join(sorted(existing.lower().split()))
                if fact_norm == existing_norm:
                    return  # same words, different order — skip
            facts.append(fact)
            self._lt["facts"] = facts[-200:]
            lt_snapshot = dict(self._lt)
        self._save(self.lt_path, lt_snapshot)

    def get_stats(self) -> Dict:
        with self._lock:
            buf_size  = len(self.conversation_buffer)
            facts_cnt = len(self._lt.get("facts", []))
        return {
            "buffer_size":       buf_size,
            "long_term_facts":   facts_cnt,
            "agent":             self.agent_name,
        }

    def _load(self, path: str) -> Optional[dict]:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def _save(self, path: str, data: dict):
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass
