"""Lirox v1.1 — Background Learning helpers.

Provides stateless helper classes for extracting facts, detecting patterns,
and inferring preferences from individual query/response pairs.

These are used directly by the TrainingEngine (memory/trainer.py).
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Any

_logger = logging.getLogger("lirox.memory.background")


class FactExtractor:
    """Extract explicit facts from conversation."""

    @staticmethod
    def extract(query: str, response: str) -> List[str]:
        """Extract facts from user query and agent response."""
        facts = []

        expertise_patterns = [
            (r"i'm a (\w+)", "role"),
            (r"i work (?:as|on) (\w+)", "role"),
            (r"i'm (?:learning|studying) (\w+)", "learning_topic"),
            (r"my expertise (?:is|in) (\w+)", "expertise"),
        ]

        for pattern, fact_type in expertise_patterns:
            match = re.search(pattern, query.lower())
            if match:
                facts.append(f"[FACT] User {fact_type}: {match.group(1)}")

        if "goal" in query.lower() or "want to" in query.lower():
            facts.append(f"[FACT] User has an objective: {query[:100]}")

        if any(tool in response.lower() for tool in
               ["pdf", "code", "analysis", "database", "api"]):
            facts.append("[FACT] User works with technical tools")

        return facts

    @staticmethod
    def extract_from_response(response: str) -> Dict[str, str]:
        """Extract metadata from response."""
        return {
            "response_length": "long" if len(response) > 500 else "short",
            "has_code": "yes" if "```" in response or "code" in response.lower() else "no",
            "has_examples": "yes" if "example" in response.lower() else "no",
            "has_explanation": "yes" if "explain" in response.lower() else "no",
        }


class PatternDetector:
    """Detect recurring patterns in user behavior."""

    @staticmethod
    def detect(conversation_history: List[Dict], query: str, response: str) -> List[str]:
        """Detect patterns from conversation history."""
        patterns = []
        # Guard against malformed entries (must be dicts)
        safe_history = [m for m in conversation_history if isinstance(m, dict)]
        recent_queries = [
            m.get("user", "") for m in safe_history[-10:]
            if isinstance(m.get("user", ""), str)
        ]
        recent_queries = [q.lower() for q in recent_queries]

        for topic in ["machine learning", "python", "design", "pdf", "document"]:
            count = sum(1 for q in recent_queries if topic in q)
            if count >= 2:
                patterns.append(f"[PATTERN] User frequently asks about {topic}")

        tools_used = []
        for msg in safe_history[-5:]:
            agent_val = msg.get("agent", "")
            if not isinstance(agent_val, str):
                continue
            if "file" in agent_val.lower():
                tools_used.append("file")
            if "pdf" in agent_val.lower():
                tools_used.append("pdf")

        if len(tools_used) >= 2:
            patterns.append("[PATTERN] User frequently creates documents")

        return patterns

    @staticmethod
    def detect_workflow(tools_used: List[str], files_created: List[str]) -> Dict[str, Any]:
        """Detect user's workflow pattern."""
        return {
            "prefers_file_generation": len(files_created) >= 2,
            "uses_multiple_tools": len(tools_used) >= 2,
            "prefers_documents": any("pdf" in f or "docx" in f for f in files_created),
        }


class PreferenceInferrer:
    """Infer user preferences from behavior."""

    @staticmethod
    def infer(query: str, response: str, tools_used: List[str]) -> Dict[str, Any]:
        """Infer preferences from interaction."""
        prefs = {}
        if len(query) > 100:
            prefs["likes_detail"] = True
        else:
            prefs["likes_conciseness"] = True

        if "code" in query.lower():
            prefs["interested_in_code"] = True

        if any(tool in str(tools_used).lower() for tool in ["pdf", "docx", "pptx"]):
            prefs["likes_document_creation"] = True

        if "learn" in query.lower() or "explain" in query.lower():
            prefs["prefers_educational"] = True

        return prefs
