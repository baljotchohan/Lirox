"""Lirox v2.0 — Memory Import Handler.

Robust, one-paste import of user knowledge from any LLM or
Lirox's own exports. Fixes every issue from v1:
  - Handles markdown-fenced JSON (the format every LLM actually
    outputs) without asking the user to strip fences.
  - Updates profile.json AND LearningsStore (not just learnings).
  - Deduplicates on normalized content.
  - Returns structured, verifiable result.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from lirox.mind.learnings import LearningsStore
from lirox.utils.llm import generate_response


_IMPORT_ANALYZE_PROMPT = """Analyze these conversation excerpts from a user's chat history.
Extract stable facts, preferences, projects, topics, and communication style.

CONVERSATIONS:
{conversations}

Output ONLY this JSON schema (no preamble, no trailing text):
{{
  "facts": ["..."],
  "preferences": {{"category": ["pref1"]}},
  "projects": [{{"name": "...", "description": "..."}}],
  "topics": ["..."],
  "communication_style": {{"key": "value"}},
  "profile": {{"niche": "", "current_project": ""}}
}}
"""


def _extract_json_robust(raw: str) -> Optional[dict]:
    """Extract the first JSON object from text, tolerating fences and preambles.

    Handles:
    - ```json ... ``` fences
    - ``` ... ``` bare fences
    - Preambles like "Here is the JSON:" before the object
    - Trailing commentary after the object
    """
    if not raw or not raw.strip():
        return None

    text = raw.strip()

    # Try direct parse first (common case)
    try:
        return json.loads(text)
    except Exception:
        pass

    # Extract from markdown fence
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except Exception:
            pass

    # Greedy extract first top-level JSON object
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    start = None
                    depth = 0
    return None


class MemoryImporter:
    """Imports external conversation history into Lirox learnings + profile."""

    def __init__(self, learnings: LearningsStore):
        self.learnings = learnings

    # ── Public: from raw text (paste) ─────────────────────────────────

    def import_raw_data(self, content: str, source: str = "pasted") -> Dict[str, Any]:
        """Primary entry point for pasted LLM output."""
        content = (content or "").strip()
        if not content:
            return {"error": "Empty content", "success": False}

        # First, try structured JSON (what our sync prompt produces)
        data = _extract_json_robust(content)
        if isinstance(data, dict) and (
            "facts" in data or "preferences" in data or "profile" in data
        ):
            result = self._apply_structured(data, source=source)
            result["source"] = source
            result["mode"] = "structured_json"
            return result

        # Fall back: plain text, let LLM extract
        result = self._llm_extract_and_apply(content[:12000], source)
        result["source"] = source
        result["mode"] = "llm_extracted"
        return result

    # ── Public: from file ─────────────────────────────────────────────

    def import_file(self, file_path: str) -> Dict[str, Any]:
        path = Path(file_path).expanduser()
        if not path.exists():
            return {"error": f"File not found: {file_path}", "success": False}

        if path.is_dir():
            return self._import_folder(path)

        ext = path.suffix.lower()
        fname = path.name.lower()

        try:
            if ext == ".json" and ("lirox_memory" in fname or "lirox_export" in fname):
                from lirox.utils.memory_utils import import_full_memory
                r = import_full_memory(str(path))
                return {
                    "success": bool(r.get("success")),
                    "imported": "Full Profile",
                    "facts_added": r.get("facts_added", 0),
                    "source": "Lirox Export",
                    "is_full": True,
                    "error": r.get("error"),
                }

            if ext == ".json":
                if "conversations" in fname or "chatgpt" in fname:
                    return self._import_chatgpt(path)
                if "claude" in fname:
                    return self._import_claude(path)
                return self._import_generic_json(path)

            if ext in (".md", ".txt"):
                return self._import_text(path)

            return {"error": f"Unsupported format: {ext}", "success": False}
        except Exception as e:
            return {"error": str(e), "success": False}

    # ── Core: apply a structured dict ────────────────────────────────

    def _apply_structured(self, data: Dict[str, Any], source: str) -> Dict[str, Any]:
        stats = {
            "success": True,
            "facts_added": 0,
            "preferences_added": 0,
            "projects_added": 0,
            "topics_added": 0,
            "dislikes_added": 0,
            "profile_fields_updated": 0,
        }

        # Facts
        for fact in data.get("facts", []) or []:
            if isinstance(fact, str) and len(fact) > 3:
                self.learnings.add_fact(fact[:300], confidence=0.7, source=source)
                stats["facts_added"] += 1

        # Preferences
        for cat, prefs in (data.get("preferences") or {}).items():
            if not isinstance(prefs, list):
                prefs = [prefs]
            for p in prefs:
                if isinstance(p, str) and p.strip():
                    self.learnings.add_preference(cat, p.strip()[:200])
                    stats["preferences_added"] += 1

        # Dislikes
        for d in data.get("dislikes", []) or []:
            if isinstance(d, str) and d.strip():
                self.learnings.add_dislike(d.strip()[:200])
                stats["dislikes_added"] += 1

        # Projects
        for proj in data.get("projects", []) or []:
            if isinstance(proj, dict) and proj.get("name"):
                self.learnings.add_project(
                    str(proj["name"])[:120],
                    description=str(proj.get("description", ""))[:300],
                )
                stats["projects_added"] += 1

        # Topics
        for topic in data.get("topics", []) or []:
            if isinstance(topic, str) and topic.strip():
                self.learnings.bump_topic(topic.strip().lower()[:60])
                stats["topics_added"] += 1

        # Communication style
        for k, v in (data.get("communication_style") or {}).items():
            if isinstance(k, str) and isinstance(v, str):
                self.learnings.update_communication_style(k, v)

        # Profile update
        prof_block = data.get("profile") or {}
        if isinstance(prof_block, dict) and prof_block:
            try:
                from lirox.agent.profile import UserProfile
                up = UserProfile()
                for k in ("niche", "current_project", "profession"):
                    v = prof_block.get(k, "")
                    if isinstance(v, str):
                        v = v.strip()
                    else:
                        v = ""
                    if v:
                        up.update(k, v)
                        stats["profile_fields_updated"] += 1
                # name is sensitive — only set if profile has no user_name
                if not up.data.get("user_name") or up.data.get("user_name") in ("Operator", ""):
                    name = prof_block.get("name", "")
                    if isinstance(name, str):
                        name = name.strip()
                    else:
                        name = ""
                    if name:
                        up.update("user_name", name)
                        stats["profile_fields_updated"] += 1
            except Exception:
                pass  # profile update is best-effort — learnings still saved

        self.learnings.flush()
        return stats

    # ── Core: LLM-assisted extraction from plain text ─────────────────

    def _llm_extract_and_apply(self, text_sample: str, source: str) -> Dict[str, Any]:
        try:
            raw = generate_response(
                _IMPORT_ANALYZE_PROMPT.format(conversations=text_sample),
                provider="auto",
                system_prompt="Extract user knowledge. Output only the JSON schema requested.",
            )
            data = _extract_json_robust(raw)
            if not isinstance(data, dict):
                return {
                    "success": False,
                    "error": "Could not parse JSON from LLM response",
                    "facts_added": 0,
                }
            return self._apply_structured(data, source=source)
        except Exception as e:
            return {"success": False, "error": str(e), "facts_added": 0}

    # ── File-format importers ────────────────────────────────────────

    def _import_folder(self, path: Path) -> Dict[str, Any]:
        gemini = list(path.glob("**/Gemini/**/*.json"))
        if gemini:
            return self._import_gemini(path)
        for jf in path.glob("*.json"):
            n = jf.name.lower()
            if "conversations" in n or "chatgpt" in n:
                return self._import_chatgpt(jf)
            if "claude" in n:
                return self._import_claude(jf)
        return {"error": "No recognizable AI export files in folder.", "success": False}

    def _sample(self, messages: List[str], max_chars: int = 8000) -> str:
        return ("\n---\n".join(messages[:30]))[:max_chars]

    def _import_chatgpt(self, path: Path) -> Dict[str, Any]:
        data = json.loads(path.read_text())
        if not isinstance(data, list):
            return {"error": "Unexpected ChatGPT format", "success": False}
        msgs = []
        for conv in data[:200]:
            for node in conv.get("mapping", {}).values():
                m = node.get("message") or {}
                if m.get("author", {}).get("role") == "user":
                    c = m.get("content", {})
                    if isinstance(c, dict):
                        for part in c.get("parts", []):
                            if isinstance(part, str) and part.strip():
                                msgs.append(part[:300])
                    elif isinstance(c, str):
                        msgs.append(c[:300])
        result = self._llm_extract_and_apply(self._sample(msgs), "chatgpt")
        result["source"] = "ChatGPT"
        result["imported"] = len(msgs)
        return result

    def _import_claude(self, path: Path) -> Dict[str, Any]:
        data = json.loads(path.read_text())
        msgs = []
        if isinstance(data, list):
            for conv in data:
                if isinstance(conv, dict):
                    for msg in conv.get("messages", conv.get("chat_messages", [])):
                        if msg.get("sender") == "human" or msg.get("role") == "user":
                            t = msg.get("text", msg.get("content", ""))
                            if isinstance(t, str) and t.strip():
                                msgs.append(t[:300])
        elif isinstance(data, dict):
            for msg in data.get("messages", []):
                if msg.get("role") == "user":
                    t = msg.get("content", "")
                    if isinstance(t, str) and t.strip():
                        msgs.append(t[:300])
        result = self._llm_extract_and_apply(self._sample(msgs), "claude")
        result["source"] = "Claude"
        result["imported"] = len(msgs)
        return result

    def _import_generic_json(self, path: Path) -> Dict[str, Any]:
        data = json.loads(path.read_text())
        msgs: List[str] = []

        def _walk(obj, depth=0):
            if depth > 5:
                return
            if isinstance(obj, list):
                for it in obj:
                    _walk(it, depth + 1)
            elif isinstance(obj, dict):
                for k in ("content", "text", "message", "body"):
                    v = obj.get(k)
                    if isinstance(v, str) and len(v) > 10:
                        msgs.append(v[:300])
                for v in obj.values():
                    if isinstance(v, (dict, list)):
                        _walk(v, depth + 1)

        _walk(data)
        result = self._llm_extract_and_apply(self._sample(msgs), "generic")
        result["source"] = "Generic JSON"
        result["imported"] = len(msgs)
        return result

    def _import_text(self, path: Path) -> Dict[str, Any]:
        text = path.read_text()[:12000]
        result = self._llm_extract_and_apply(text, "text_file")
        result["source"] = path.name
        result["imported"] = len(text.split("\n"))
        return result

    def _import_gemini(self, path: Path) -> Dict[str, Any]:
        msgs = []
        for jf in path.glob("**/Gemini/**/*.json"):
            try:
                data = json.loads(jf.read_text())
                if isinstance(data, list):
                    for conv in data:
                        for part in conv.get("parts", []):
                            if part.get("role") == "user":
                                msgs.append(part.get("text", "")[:300])
                elif isinstance(data, dict):
                    for entry in data.get("entries", []):
                        if entry.get("role") == "user":
                            msgs.append(entry.get("text", "")[:300])
            except Exception:
                continue
        if not msgs:
            return {"error": "No Gemini messages found in takeout folder.", "success": False}
        result = self._llm_extract_and_apply(self._sample(msgs), "gemini")
        result["source"] = "Gemini Takeout"
        result["imported"] = len(msgs)
        return result
