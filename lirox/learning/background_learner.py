"""Background Learning System — Automatic learning after every exchange.

Extracts facts, detects patterns, updates user profile continuously
without requiring manual /train command.
"""
from __future__ import annotations

import logging
import json
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, field
import re
import os

_logger = logging.getLogger("lirox.learning.background_learner")


@dataclass
class ExtractedLearnings:
    """What was learned from an exchange."""
    facts: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)
    preference_updates: Dict[str, Any] = field(default_factory=dict)
    expertise_updates: Dict[str, float] = field(default_factory=dict)
    
    def summary(self) -> Dict[str, int]:
        return {
            "facts": len(self.facts),
            "patterns": len(self.patterns),
            "preferences": len(self.preference_updates),
            "expertise": len(self.expertise_updates),
        }


class FactExtractor:
    """Extract explicit facts from conversation."""
    
    @staticmethod
    def extract(query: str, response: str) -> List[str]:
        """Extract facts from user query and agent response."""
        facts = []
        
        # User expertise indicator patterns
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
        
        # Goal extraction
        if "goal" in query.lower() or "want to" in query.lower():
            facts.append(f"[FACT] User has an objective: {query[:100]}")
        
        # Tool usage indicates capability level
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
    def detect(conversation_history: List[Dict], 
               query: str, response: str) -> List[str]:
        """Detect patterns from conversation history."""
        patterns = []
        
        # Query frequency patterns
        query_lower = query.lower()
        
        # Check if similar query appears in history
        recent_queries = [m.get("user", "").lower() for m in conversation_history[-10:]]
        
        for topic in ["machine learning", "python", "design", "pdf", "document"]:
            count = sum(1 for q in recent_queries if topic in q)
            if count >= 2:
                patterns.append(f"[PATTERN] User frequently asks about {topic}")
        
        # Time pattern (if available in context)
        if "morning" in str(conversation_history) and "afternoon" in str(conversation_history):
            patterns.append("[PATTERN] User is active at different times of day")
        
        # Tool usage pattern
        tools_used = []
        for msg in conversation_history[-5:]:
            if "file" in msg.get("agent", "").lower():
                tools_used.append("file")
            if "pdf" in msg.get("agent", "").lower():
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
        
        # Response length preference
        if len(query) > 100:
            prefs["likes_detail"] = True
        else:
            prefs["likes_conciseness"] = True
        
        # Code preference
        if "code" in query.lower():
            prefs["interested_in_code"] = True
        
        # Document preference
        if any(tool in str(tools_used).lower() for tool in ["pdf", "docx", "pptx"]):
            prefs["likes_document_creation"] = True
        
        # Educational preference
        if "learn" in query.lower() or "explain" in query.lower():
            prefs["prefers_educational"] = True
        
        return prefs


class BackgroundLearner:
    """Main background learning system."""
    
    def __init__(self, context_brain, storage_path: str = "~/.lirox"):
        self.context_brain = context_brain
        self.storage_path = os.path.expanduser(storage_path)
    
    def process_exchange(self, query: str, response: str,
                        tools_used: List[str] = None,
                        files_created: List[str] = None) -> Dict[str, Any]:
        """
        Process a user-agent exchange and automatically learn from it.
        Called after every agent response.
        """
        tools_used = tools_used or []
        files_created = files_created or []
        
        learnings = ExtractedLearnings()
        
        # Step 1: Extract facts
        learnings.facts = FactExtractor.extract(query, response)
        
        # Step 2: Detect patterns
        conversation_history = self.context_brain.data.conversation_context.messages
        learnings.patterns = PatternDetector.detect(
            conversation_history, query, response
        )
        
        # Step 3: Infer preferences
        learnings.preference_updates = PreferenceInferrer.infer(
            query, response, tools_used
        )
        
        # Step 4: Detect workflow and update expertise
        workflow = PatternDetector.detect_workflow(tools_used, files_created)
        learnings.preference_updates.update(workflow)
        
        # Step 5: Update context brain
        self.context_brain.add_exchange(query, response, tools_used, files_created)
        
        # Update expertise level based on conversation depth
        if len(query) > 200:
            learnings.expertise_updates["reasoning_depth"] = 0.8
        
        # Update preferences in context
        self.context_brain.update_learned_facts({
            "preferences": learnings.preference_updates
        })
        
        _logger.info(f"Learning complete: {learnings.summary()}")
        
        return {
            "learned": learnings.summary(),
            "facts_count": len(learnings.facts),
            "patterns_count": len(learnings.patterns),
            "expertise_updates": learnings.expertise_updates,
        }
    
    def get_learning_summary(self) -> Dict[str, Any]:
        """Get summary of what has been learned."""
        return {
            "user_name": self.context_brain.data.learned_facts.user_name,
            "expertise_level": self.context_brain.data.expertise_context.level,
            "topics_known": list(self.context_brain.data.expertise_context.topics.keys()),
            "preferences": self.context_brain.data.learned_facts.preferences,
            "conversation_count": len(self.context_brain.data.conversation_context.messages),
        }
