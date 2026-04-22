"""Real Context Brain — Awareness of user's actual world.

Provides timestamps, locations, conversation history, learned preferences,
expertise level, and environmental context for better reasoning.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
import json
import os

_logger = logging.getLogger("lirox.context.real_context")


@dataclass
class LocationContext:
    """User's physical location and nearby services."""
    timezone: str = "UTC"  # User's timezone
    location: Optional[str] = None  # City/region
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TimeContext:
    """Time-based awareness."""
    timestamp: str  # ISO format
    timezone: str
    hour: int  # 0-23
    day_of_week: str  # Monday-Sunday
    time_of_day: str  # morning/afternoon/evening/night
    date: str  # YYYY-MM-DD
    
    @staticmethod
    def now(tz_name: str = "UTC") -> TimeContext:
        """Get current time context."""
        try:
            import pytz
            tz = pytz.timezone(tz_name)
            now = datetime.now(tz)
        except Exception:
            now = datetime.now(timezone.utc)
            tz_name = "UTC"
        
        hour = now.hour
        if hour < 12:
            time_of_day = "morning"
        elif hour < 17:
            time_of_day = "afternoon"
        elif hour < 21:
            time_of_day = "evening"
        else:
            time_of_day = "night"
        
        return TimeContext(
            timestamp=now.isoformat(),
            timezone=tz_name,
            hour=hour,
            day_of_week=now.strftime("%A"),
            time_of_day=time_of_day,
            date=now.strftime("%Y-%m-%d"),
        )
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class UserExpertiseContext:
    """Inferred user expertise level and interests."""
    level: str = "beginner"  # beginner/intermediate/advanced/expert
    confidence: float = 0.5  # 0-1, how confident we are
    
    # Topic expertise
    topics: Dict[str, float] = field(default_factory=dict)
    # e.g., {"python": 0.9, "machine_learning": 0.6}
    
    # Skills
    skills: Dict[str, float] = field(default_factory=dict)
    # e.g., {"coding": 0.8, "design": 0.4}
    
    # Inferred from past interactions
    prefers_detail: bool = True
    prefers_examples: bool = True
    prefers_step_by_step: bool = False
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ConversationHistory:
    """Recent conversation context."""
    messages: List[Dict[str, str]] = field(default_factory=list)
    last_topics: List[str] = field(default_factory=list)
    last_tools_used: List[str] = field(default_factory=list)
    last_files_created: List[str] = field(default_factory=list)
    
    def add_exchange(self, query: str, response: str, 
                     tools: List[str] = None, files: List[str] = None):
        """Add a user-agent exchange."""
        self.messages.append({"user": query, "agent": response})
        self.last_tools_used = tools or []
        self.last_files_created = files or []
        
        # Extract topics from query
        topics = extract_topics(query)
        self.last_topics.extend(topics)
        
        # Keep last 20 messages
        self.messages = self.messages[-20:]
        self.last_topics = self.last_topics[-10:]
    
    def get_last_n(self, n: int = 5) -> List[Dict[str, str]]:
        return self.messages[-n:] if self.messages else []
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LearnedFacts:
    """Facts learned about the user."""
    user_name: str = ""
    role: str = ""  # Student, Developer, Designer, etc.
    niche: str = ""  # What they work on
    goals: List[str] = field(default_factory=list)
    preferences: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RealContextData:
    """Complete real-world context for user."""
    user_id: str
    time_context: TimeContext
    location_context: LocationContext
    expertise_context: UserExpertiseContext
    conversation_context: ConversationHistory
    learned_facts: LearnedFacts
    
    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "time": self.time_context.to_dict(),
            "location": self.location_context.to_dict(),
            "expertise": self.expertise_context.to_dict(),
            "conversation": self.conversation_context.to_dict(),
            "facts": self.learned_facts.to_dict(),
        }
    
    def to_context_string(self) -> str:
        """Generate a string for LLM context injection."""
        lines = [
            f"=== USER CONTEXT ===",
            f"User ID: {self.user_id}",
            f"Name: {self.learned_facts.user_name or '(unknown)'}",
            f"Role: {self.learned_facts.role or '(unknown)'}",
            f"",
            f"=== TIME & LOCATION ===",
            f"Current time: {self.time_context.time_of_day} "
            f"({self.time_context.day_of_week})",
            f"Date: {self.time_context.date}",
            f"Timezone: {self.time_context.timezone}",
            f"Location: {self.location_context.location or '(unknown)'}",
            f"",
            f"=== EXPERTISE ===",
            f"Level: {self.expertise_context.level}",
            f"Topics: {', '.join(self.expertise_context.topics.keys()) or '(none yet)'}",
            f"Prefers: {'detailed answers' if self.expertise_context.prefers_detail else 'concise answers'}",
            f"",
            f"=== RECENT ACTIVITY ===",
            f"Last topics: {', '.join(self.conversation_context.last_topics[-3:]) or '(none)'}",
            f"Recent tools: {', '.join(self.conversation_context.last_tools_used) or '(none)'}",
            f"",
            f"=== GOALS ===",
            f"{chr(10).join(f'- {g}' for g in self.learned_facts.goals) or '(no goals set)'}",
        ]
        return "\n".join(lines)


class RealContextBrain:
    """Manages real-world context for user."""
    
    def __init__(self, user_id: str, storage_path: str = "~/.lirox"):
        self.user_id = user_id
        self.storage_path = os.path.expanduser(storage_path)
        self.data = self._load_or_create()
    
    def _load_or_create(self) -> RealContextData:
        """Load context from disk or create new."""
        context_file = os.path.join(self.storage_path, f"{self.user_id}_context.json")
        
        if os.path.exists(context_file):
            try:
                with open(context_file, 'r') as f:
                    saved = json.load(f)
                    return self._deserialize(saved)
            except Exception as e:
                _logger.warning(f"Could not load context: {e}, creating new")
        
        # Create new context
        return RealContextData(
            user_id=self.user_id,
            time_context=TimeContext.now(),
            location_context=LocationContext(),
            expertise_context=UserExpertiseContext(),
            conversation_context=ConversationHistory(),
            learned_facts=LearnedFacts(),
        )
    
    def _deserialize(self, data: dict) -> RealContextData:
        """Deserialize from dict."""
        return RealContextData(
            user_id=data.get("user_id", self.user_id),
            time_context=TimeContext(**data.get("time", {})),
            location_context=LocationContext(**data.get("location", {})),
            expertise_context=UserExpertiseContext(**data.get("expertise", {})),
            conversation_context=ConversationHistory(
                **{k: v for k, v in data.get("conversation", {}).items() 
                   if k in ["messages", "last_topics", "last_tools_used", "last_files_created"]}
            ),
            learned_facts=LearnedFacts(**data.get("facts", {})),
        )
    
    def get_current_context(self) -> RealContextData:
        """Get current context (updates time each call)."""
        self.data.time_context = TimeContext.now(
            self.data.location_context.timezone
        )
        return self.data
    
    def add_exchange(self, query: str, response: str, 
                     tools: List[str] = None, files: List[str] = None):
        """Record a user-agent exchange."""
        self.data.conversation_context.add_exchange(query, response, tools, files)
        self.save()
    
    def update_expertise(self, level: str = None, topics: Dict[str, float] = None):
        """Update expertise context."""
        if level:
            self.data.expertise_context.level = level
        if topics:
            self.data.expertise_context.topics.update(topics)
        self.save()
    
    def update_learned_facts(self, facts: Dict[str, Any]):
        """Update learned facts."""
        for key, value in facts.items():
            if hasattr(self.data.learned_facts, key):
                setattr(self.data.learned_facts, key, value)
        self.save()
    
    def save(self):
        """Save context to disk."""
        os.makedirs(self.storage_path, exist_ok=True)
        context_file = os.path.join(self.storage_path, f"{self.user_id}_context.json")
        try:
            with open(context_file, 'w') as f:
                json.dump(self.data.to_dict(), f, indent=2)
        except Exception as e:
            _logger.error(f"Could not save context: {e}")
    
    def to_context_string(self) -> str:
        """Get context as string for LLM."""
        return self.get_current_context().to_context_string()


def extract_topics(query: str) -> List[str]:
    """Extract topic keywords from query."""
    # Simple keyword extraction (can be improved)
    keywords = [
        "python", "javascript", "machine learning", "ai", "design", "web",
        "database", "api", "frontend", "backend", "devops", "cloud",
        "pdf", "document", "presentation", "spreadsheet", "code",
        "testing", "deployment", "security", "performance"
    ]
    
    query_lower = query.lower()
    found = [kw for kw in keywords if kw in query_lower]
    return found or ["general"]
