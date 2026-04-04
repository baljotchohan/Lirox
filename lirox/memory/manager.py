"""3-Tier Memory: Buffer + Daily logs + Long-term facts (Dexter pattern)."""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

from lirox.config import MEMORY_DIR, MEMORY_LIMIT


class MemoryManager:
    def __init__(self):
        self.conversation_buffer: List[Dict] = []
        self.lt_path = os.path.join(MEMORY_DIR, "long_term.json")
        self._lt = self._load(self.lt_path) or {"facts": [], "preferences": {}}

    def save_exchange(self, user_msg: str, asst_msg: str):
        ts = datetime.now().isoformat()
        self.conversation_buffer.append({"role": "user", "content": user_msg, "ts": ts})
        self.conversation_buffer.append(
            {"role": "assistant", "content": str(asst_msg)[:500], "ts": ts}
        )
        if len(self.conversation_buffer) > MEMORY_LIMIT * 2:
            self.conversation_buffer = self.conversation_buffer[-MEMORY_LIMIT:]

        daily = os.path.join(
            MEMORY_DIR, "daily", f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        )
        try:
            with open(daily, "a") as f:
                f.write(
                    json.dumps(
                        {"user": user_msg, "assistant": str(asst_msg)[:500], "ts": ts}
                    )
                    + "\n"
                )
        except Exception:
            pass

    def get_relevant_context(self, query: str, max_items: int = 10) -> str:
        if not self.conversation_buffer:
            return ""
        qw = set(query.lower().split())
        scored = []
        for m in self.conversation_buffer:
            cw = set(m["content"].lower().split())
            s = len(qw & cw)
            if query.lower() in m["content"].lower():
                s += 5
            if s > 0:
                scored.append((s, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        rel = [m for _, m in scored[:max_items]] or self.conversation_buffer[-(max_items * 2):]
        lines = ["--- Context ---"]
        for m in rel:
            role_label = "User" if m["role"] == "user" else "Assistant"
            lines.append(f"{role_label}: {m['content']}")
        return "\n".join(lines)

    def search(self, query: str, limit: int = 5) -> str:
        results = []
        for m in self.conversation_buffer:
            if query.lower() in m["content"].lower():
                results.append(m["content"][:200])
        for f in self._lt.get("facts", []):
            if any(w in f.lower() for w in query.lower().split()):
                results.append(f)
        return "\n".join(results[:limit]) if results else ""

    def add_fact(self, fact: str):
        facts = self._lt.get("facts", [])
        if fact not in facts:
            facts.append(fact)
            self._lt["facts"] = facts[-200:]
            self._save(self.lt_path, self._lt)

    def get_stats(self) -> Dict:
        return {
            "buffer_size": len(self.conversation_buffer),
            "long_term_facts": len(self._lt.get("facts", [])),
            "user_profile_fields": 0,
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
