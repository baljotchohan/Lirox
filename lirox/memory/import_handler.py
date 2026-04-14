"""
Lirox v0.5 — Memory Import Handler

Imports conversation history and facts from:
- ChatGPT (conversations.json export)
- Claude (claude_conversations.json export)
- Gemini (Takeout/Gemini/ folder)
- Plain text / markdown files
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple

from lirox.mind.learnings import LearningsStore
from lirox.utils.llm import generate_response


_IMPORT_ANALYZE_PROMPT = """
Analyze these conversation excerpts from a user's chat history.
Extract key facts, preferences, projects, and patterns about the user.

CONVERSATIONS:
{conversations}

Output JSON:
{{
  "facts": ["fact about user"],
  "preferences": {{"category": ["preference"]}},
  "projects": [{{"name": "...", "description": "..."}}],
  "topics": ["topic1", "topic2"],
  "communication_style": {{"key": "value"}}
}}
"""


class MemoryImporter:
    """Imports external conversation history into Lirox learnings."""

    def __init__(self, learnings: LearningsStore):
        self.learnings = learnings

    def import_file(self, file_path: str) -> Dict[str, Any]:
        """
        Auto-detect file format and import. Handles files and directories.
        """
        path = Path(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}"}

        if path.is_dir():
            return self._import_folder(path)

        ext = path.suffix.lower()
        fname = path.name.lower()

        try:
            # Check for Lirox internal export format first
            if ext == ".json" and ("lirox_memory" in fname or "lirox_export" in fname):
                from lirox.utils.memory_utils import import_full_memory
                full_res = import_full_memory(str(path))
                if full_res.get("success"):
                    return {
                        "imported": "Full Profile",
                        "facts_added": full_res.get("facts_added", 0),
                        "source": "Lirox Export",
                        "is_full": True
                    }
                else:
                    return {"error": full_res.get("error", "Unknown internal import error")}

            if ext == ".json":
                if "conversations" in fname or "chatgpt" in fname:
                    return self._import_chatgpt(path)
                elif "claude" in fname:
                    return self._import_claude(path)
                else:
                    return self._import_generic_json(path)
            elif ext in (".md", ".txt"):
                return self._import_text(path)
            else:
                return {"error": f"Unsupported format: {ext}"}
        except Exception as e:
            return {"error": str(e)}

    def _import_folder(self, path: Path) -> Dict[str, Any]:
        """Scan folder for relevant AI exports."""
        # Check for Gemini Takeout
        gemini_files = list(path.glob("**/Gemini/**/*.json"))
        if gemini_files:
             return self._import_gemini(path)
        
        # Check for Claude/ChatGPT files in folder
        json_files = list(path.glob("*.json"))
        for jf in json_files:
            if "conversations" in jf.name.lower() or "chatgpt" in jf.name.lower():
                return self._import_chatgpt(jf)
            if "claude" in jf.name.lower():
                return self._import_claude(jf)
                
        return {"error": "No recognizable AI export files found in directory."}


    def _extract_text_samples(self, messages: List[str], max_chars: int = 8000) -> str:
        """Get a representative sample of conversation text."""
        combined = "\n---\n".join(messages[:30])
        return combined[:max_chars]

    def _analyze_and_save(self, text_sample: str, source: str) -> Dict[str, Any]:
        """Use LLM to analyze conversation and extract learnings."""
        results = {"facts_added": 0, "topics_added": 0, "projects_added": 0}

        try:
            raw = generate_response(
                _IMPORT_ANALYZE_PROMPT.format(conversations=text_sample),
                provider="auto",
                system_prompt="Extract user knowledge. Output only JSON.",
            )
            from lirox.utils.llm import strip_code_fences
            raw = strip_code_fences(raw, lang="json")
            
            # Robust JSON extraction
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                # Fallback: find the first { and last }
                match = re.search(r"(\{.*\})", raw, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                else:
                    raise ValueError("Could not parse JSON from LLM response")


            for fact in data.get("facts", []):
                if isinstance(fact, str) and len(fact) > 5:
                    self.learnings.add_fact(fact, confidence=0.6, source=source)
                    results["facts_added"] += 1

            for cat, prefs in data.get("preferences", {}).items():
                for p in (prefs or []):
                    if isinstance(p, str):
                        self.learnings.add_preference(cat, p)

            for proj in data.get("projects", []):
                if isinstance(proj, dict) and proj.get("name"):
                    self.learnings.add_project(proj["name"], proj.get("description", ""))
                    results["projects_added"] += 1

            for topic in data.get("topics", []):
                if isinstance(topic, str):
                    self.learnings.bump_topic(topic)
                    results["topics_added"] += 1

            for k, v in data.get("communication_style", {}).items():
                if isinstance(k, str) and isinstance(v, str):
                    self.learnings.update_communication_style(k, v)

        except Exception as e:
            results["error"] = str(e)

        return results

    def _import_chatgpt(self, path: Path) -> Dict[str, Any]:
        """Import ChatGPT conversations.json export."""
        data = json.loads(path.read_text())
        if not isinstance(data, list):
            return {"error": "Unexpected ChatGPT format"}

        messages = []
        # Support scanning more conversations to get better coverage
        for conv in data[:200]:  # Increased from 50
            for node in conv.get("mapping", {}).values():
                msg = node.get("message")
                if msg and msg.get("author", {}).get("role") == "user":
                    content = msg.get("content", {})
                    if isinstance(content, dict):
                        for part in content.get("parts", []):
                            if isinstance(part, str) and part.strip():
                                messages.append(part[:300])
                    elif isinstance(content, str):
                        messages.append(content[:300])

        sample = self._extract_text_samples(messages)
        result = self._analyze_and_save(sample, "chatgpt")
        result["imported"] = len(messages)
        result["source"] = "ChatGPT"
        return result

    def _import_claude(self, path: Path) -> Dict[str, Any]:
        """Import Claude conversation export."""
        data = json.loads(path.read_text())
        messages = []

        # Claude exports vary — handle both formats
        if isinstance(data, list):
            for conv in data:
                if isinstance(conv, dict):
                    for msg in conv.get("messages", conv.get("chat_messages", [])):
                        if msg.get("sender") == "human" or msg.get("role") == "user":
                            text = msg.get("text", msg.get("content", ""))
                            if isinstance(text, str) and text.strip():
                                messages.append(text[:300])
        elif isinstance(data, dict):
            for msg in data.get("messages", []):
                if msg.get("role") == "user":
                    text = msg.get("content", "")
                    if isinstance(text, str) and text.strip():
                        messages.append(text[:300])

        sample = self._extract_text_samples(messages)
        result = self._analyze_and_save(sample, "claude")
        result["imported"] = len(messages)
        result["source"] = "Claude"
        return result

    def _import_generic_json(self, path: Path) -> Dict[str, Any]:
        """Try to import any JSON file with messages."""
        data = json.loads(path.read_text())
        messages = []

        def find_messages(obj, depth=0):
            if depth > 5:
                return
            if isinstance(obj, list):
                for item in obj:
                    find_messages(item, depth + 1)
            elif isinstance(obj, dict):
                for key in ("content", "text", "message", "body"):
                    val = obj.get(key)
                    if isinstance(val, str) and len(val) > 10:
                        messages.append(val[:300])
                for v in obj.values():
                    if isinstance(v, (dict, list)):
                        find_messages(v, depth + 1)

        find_messages(data)
        sample = self._extract_text_samples(messages)
        result = self._analyze_and_save(sample, "generic")
        result["imported"] = len(messages)
        result["source"] = "Generic JSON"
        return result

    def _import_text(self, path: Path) -> Dict[str, Any]:
        """Import plain text or markdown conversation."""
        text = path.read_text()[:12000]
        result = self._analyze_and_save(text, "text_file")
        result["imported"] = len(text.split("\n"))
        result["source"] = path.name
        return result
    def _import_gemini(self, path: Path) -> Dict[str, Any]:
        """Import Gemini Takeout export."""
        messages = []
        # Gemini JSON files often have a 'conversations' list with 'parts'
        for jf in path.glob("**/Gemini/**/*.json"):
            try:
                data = json.loads(jf.read_text())
                if isinstance(data, list):  # Format 1
                    for conv in data:
                        for part in conv.get("parts", []):
                            if part.get("role") == "user":
                                messages.append(part.get("text", "")[:300])
                elif isinstance(data, dict):  # Format 2
                    for entry in data.get("entries", []):
                        if entry.get("role") == "user":
                            messages.append(entry.get("text", "")[:300])
            except Exception:
                continue

        if not messages:
            return {"error": "No Gemini messages found in takeout folder."}

        sample = self._extract_text_samples(messages)
        result = self._analyze_and_save(sample, "gemini")
        result["imported"] = len(messages)
        result["source"] = "Gemini Takeout"
        return result
