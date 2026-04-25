"""
Context Filter
Prevents user-profile contamination in wrong task types.

Core fix: Sikh history PDF should NEVER mention "C++ and GitHub".
"""
import logging
from typing import Any, Dict

_logger = logging.getLogger("lirox.quality.context_filter")


class ContextFilter:
    """Strips context that does not belong in a given task type."""

    def filter(
        self,
        query: str,
        task_type: str,
        user_profile: Dict[str, Any],
        conversation_context: str,
    ) -> Dict[str, Any]:
        """
        Return ONLY context relevant to this task.

        Rules:
        - Historical / educational documents → NO profile (would contaminate)
        - User's own resume / portfolio    → FULL profile
        - Business / technical document    → company + role + tech stack only
        - Chat                             → full profile
        - File / shell operations          → conversation only
        """
        # SAFETY: coerce inputs to correct types
        if not isinstance(user_profile, dict):
            user_profile = {}
        if not isinstance(conversation_context, str):
            conversation_context = str(conversation_context) if conversation_context else ""

        if task_type == "filegen":
            if self._is_historical_or_educational(query):
                # Zero profile — history should not know about the developer's stack
                return {"topic": query, "conversation": conversation_context[:400]}

            if self._is_about_user(query):
                # Full profile — it IS about the user
                return {"profile": user_profile, "conversation": conversation_context[:400]}

            # Default for business/technical documents
            return {
                "company":    user_profile.get("company", ""),
                "role":       user_profile.get("role", user_profile.get("profession", "")),
                "tech_stack": user_profile.get("tech_stack", []),
                "conversation": conversation_context[:400],
            }

        if task_type == "chat":
            return {"profile": user_profile, "conversation": conversation_context}

        # file, shell, web, memory, self — minimal context
        return {"conversation": conversation_context[:300]}

    # ── Classification helpers ───────────────────────────────────────────────

    _HISTORICAL_KW = frozenset([
        "history", "historical", "biography", "timeline", "ancient",
        "medieval", "century", "war", "battle", "religion", "philosophy",
        "culture", "tradition", "document about", "research on", "study of",
        "heritage", "mythology", "civilization", "sikh", "empire", "dynasty",
        "era", "epoch", "scripture", "theology",
    ])

    _USER_KW = frozenset([
        "my resume", "my cv", "my portfolio", "about me", "my profile",
        "my experience", "my background", "for me", "about myself",
        "my skills", "my work",
    ])

    def _is_historical_or_educational(self, query: str) -> bool:
        q = query.lower()
        return any(kw in q for kw in self._HISTORICAL_KW)

    def _is_about_user(self, query: str) -> bool:
        q = query.lower()
        return any(kw in q for kw in self._USER_KW)
