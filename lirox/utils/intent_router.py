"""
Lirox v0.6 — Smart Command Intent Router

Automatically detects user intent and routes to appropriate handler.
Learns over time what the user typically wants.
"""

import re
from typing import Tuple


class IntentRouter:
    """Routes user input to the most appropriate command."""
    
    # Intent detection patterns
    RESEARCH_PATTERNS = [
        r"research\s+", r"find\s+(info|sources|articles)", r"look\s+up",
        r"investigate", r"study\s+", r"analyze\s+(the\s+)?latest",
        r"what'?s\s+(new|latest|happening)", r"tell\s+me\s+about",
        r"how\s+(does|do)", r"explain", r"summarize", r"overview",
        r"what\s+are\s+(the\s+)?latest", r"search\s+for",
    ]
    
    TASK_PATTERNS = [
        r"create\s+", r"write\s+", r"generate\s+", r"build\s+",
        r"install\s+", r"setup\s+", r"configure\s+", r"run\s+",
        r"execute\s+", r"deploy\s+", r"organize\s+", r"clean\s+",
        r"fix\s+", r"debug\s+", r"optimize\s+",
    ]
    
    MEMORY_PATTERNS = [
        r"remember\s+", r"save\s+(this|that)", r"note\s+", r"learn\s+",
        r"add\s+(goal|preference)", r"set\s+", r"update\s+profile",
    ]
    
    CHAT_PATTERNS = [
        r"^(how|why|when|where|what|who|which)", r"tell\s+me",
        r"what\s+do\s+you", r"can\s+you", r"help\s+", r"advice",
        r"opinion", r"think\s+(about|of)", r"suggest",
    ]
    
    def __init__(self):
        self.user_intent_history = []
        self.command_frequency = {}
    
    def detect_intent(self, user_input: str) -> Tuple[str, str, float]:
        """
        Detect user intent from input.
        
        Returns:
            (intent_type, suggested_command, confidence_0_to_1)
        """
        user_lower = user_input.lower().strip()
        
        # Check if explicit command
        if user_lower.startswith("/"):
            return ("command", user_lower.split()[0], 1.0)
        
        # Check research intent
        research_score = self._score_patterns(user_lower, self.RESEARCH_PATTERNS)
        if research_score > 0.6:
            query = self._extract_query(user_input)
            return ("research", f'/research "{query}"', research_score)
        
        # Check task intent
        task_score = self._score_patterns(user_lower, self.TASK_PATTERNS)
        if task_score > 0.6:
            return ("task", None, task_score)
        
        # Check memory/learning intent
        memory_score = self._score_patterns(user_lower, self.MEMORY_PATTERNS)
        if memory_score > 0.6:
            return ("memory", None, memory_score)
        
        # Check chat intent
        chat_score = self._score_patterns(user_lower, self.CHAT_PATTERNS)
        if chat_score > 0.4:
            return ("chat", None, chat_score)
        
        # Default
        default = "task" if task_score > 0.2 else "chat"
        return (default, None, 0.5)
    
    def _score_patterns(self, text: str, patterns: list) -> float:
        """Score how well text matches a list of patterns."""
        matches = sum(1 for pattern in patterns if re.search(pattern, text, re.IGNORECASE))
        return min(matches / len(patterns) * 1.5, 1.0) if patterns else 0.0
    
    def _extract_query(self, user_input: str) -> str:
        """Extract the core query from user input."""
        text = re.sub(r"^(research|find|look\s+up|investigate|study|analyze)\s+", "", 
                     user_input, flags=re.IGNORECASE)
        text = re.sub(r"[?!.]+$", "", text.strip())
        return text[:100]
    
    def learn_from_choice(self, intent: str, command: str):
        """Learn which commands user prefers for certain intents."""
        key = f"{intent}:{command}"
        self.command_frequency[key] = self.command_frequency.get(key, 0) + 1
        self.user_intent_history.append((intent, command))
    
    def suggest_next_command(self, last_intent: str) -> str:
        """Suggest what command user might want next."""
        if last_intent == "research":
            return "💡 Tip: Type /sources to view source details or /tier for research tier info"
        elif last_intent == "task":
            return "💡 Tip: Type /trace to see execution logs or /memory to save findings"
        return None


# Global router instance
router = IntentRouter()
