"""3-Tier Memory: Buffer + Daily logs + Long-term facts. Per-agent isolated."""
import json
import os
import re
import threading
from collections import Counter, deque
from datetime import datetime
from typing import Dict, Deque, List, Optional

from lirox.config import MEMORY_DIR, MEMORY_LIMIT, MAX_MEMORY_ENTRY_CHARS


class MemoryManager:
    def __init__(self, agent_name: str = "global"):
        self.agent_name         = agent_name
        self._lock               = threading.Lock()
        # RELIABILITY-01 fix: use a bounded deque so the buffer never grows
        # past MEMORY_LIMIT * 2 entries without manual intervention.
        self.conversation_buffer: Deque[Dict[str, str]] = deque(maxlen=MEMORY_LIMIT * 2)
        # Each agent gets its own long-term memory file
        self._safe_name = agent_name.replace("/", "_").replace("\\", "_")
        self.lt_path = os.path.join(MEMORY_DIR, f"long_term_{self._safe_name}.json")
        self._lt     = self._load(self.lt_path) or {"facts": [], "preferences": {}}

    def save_exchange(self, user_msg: str, asst_msg: str):
        ts = datetime.now().isoformat()
        with self._lock:
            self.conversation_buffer.append({"role": "user",      "content": user_msg, "ts": ts})
            self.conversation_buffer.append({"role": "assistant", "content": str(asst_msg)[:MAX_MEMORY_ENTRY_CHARS], "ts": ts})
            # No manual truncation needed — deque(maxlen=...) drops the oldest
            # entries automatically when capacity is exceeded (RELIABILITY-01 fix).

        daily = os.path.join(
            MEMORY_DIR, "daily",
            f"{self._safe_name}_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        )
        try:
            with open(daily, "a") as f:
                f.write(json.dumps({
                    "user":      user_msg,
                    "assistant": str(asst_msg)[:MAX_MEMORY_ENTRY_CHARS],
                    "ts":        ts
                }) + "\n")
        except Exception as e:
            import logging
            logging.getLogger("lirox.memory").warning(f"Daily write error: {e}")

    # Stop-words filtered out before scoring relevance.
    _CONTEXT_STOP_WORDS = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
        'have', 'has', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'can', 'this', 'that', 'with', 'from',
        'for', 'and', 'but', 'or', 'not', 'all', 'any', 'some', 'more',
        'what', 'when', 'where', 'who', 'how', 'why', 'your', 'my', 'our',
        'just', 'like', 'want', 'need', 'help', 'make', 'use', 'get',
    }

    def get_relevant_context(self, query: str, max_items: int = 10) -> str:
        """Return only context items that share >=2 meaningful words with
        the query. Stop words are filtered out before scoring."""
        with self._lock:
            buffer_snapshot = list(self.conversation_buffer)
        if not buffer_snapshot:
            return ""

        qw = {w for w in query.lower().split()
              if len(w) > 3 and w not in self._CONTEXT_STOP_WORDS}
        if not qw:
            return ""

        scored = []
        ql = query.lower()
        for m in buffer_snapshot:
            cl = m["content"].lower()
            cw = {w for w in cl.split()
                  if len(w) > 3 and w not in self._CONTEXT_STOP_WORDS}
            s = len(qw & cw)
            if ql in cl:
                s += 5
            if s >= 2 or (s >= 1 and ql in cl):
                scored.append((s, m))
        if not scored:
            return ""
        scored.sort(key=lambda x: x[0], reverse=True)
        rel = [m for _, m in scored[:max_items]]
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
        import copy
        with self._lock:
            facts = self._lt.get("facts", [])
            fact_norm = " ".join(sorted(fact.lower().split()))
            existing_norms = {" ".join(sorted(f.lower().split())) for f in facts}
            if fact in facts or fact_norm in existing_norms:
                return
            facts.append(fact)
            self._lt["facts"] = facts[-200:]
            # Deep copy while still holding the lock so the snapshot
            # cannot be mutated by a concurrent thread before _save() runs.
            lt_snapshot = copy.deepcopy(self._lt)
        # _save() is intentionally outside the lock to avoid I/O holding the lock.
        # lt_snapshot is a fully independent copy — no aliasing.
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
        # Called only from __init__ before any threads are started.
        # Bug #6: No TOCTOU — open directly and handle FileNotFoundError.
        try:
            with open(path) as f:
                return json.load(f)
        except FileNotFoundError:
            pass
        except Exception:
            pass
        return None

    def _save(self, path: str, data: dict):
        # Bug #7: Log errors instead of silently ignoring them
        try:
            dirname = os.path.dirname(path)
            if dirname:
                os.makedirs(dirname, exist_ok=True)
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            import logging
            logging.getLogger("lirox.memory").error(f"Memory save failed: {path} — {e}")
        except Exception as e:
            import logging
            logging.getLogger("lirox.memory").error(f"Unexpected memory save error: {e}")
