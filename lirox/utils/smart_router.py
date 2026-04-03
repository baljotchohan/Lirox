"""
Lirox v0.8 — Smart Router (Intent Classification & Mode Selection)

The intelligent decision engine that classifies queries and selects execution mode:
- CHAT MODE: Direct LLM response
- RESEARCH MODE: Multi-source research
- BROWSER MODE: Direct page scraping
- HYBRID MODE: Research + Browser verification

Uses semantic matching + keyword detection for maximum accuracy.
"""

import re
import json
from typing import Dict, Tuple, Optional, List
from datetime import datetime
from lirox.utils.llm import generate_response


class SmartRouter:
    """Intelligent query router that selects optimal execution mode."""
    
    # ─── MODE DEFINITIONS ────────────────────────────────────────────────────
    
    MODES = {
        "chat": {
            "description": "Direct LLM response",
            "characteristics": "General questions, explanations, creative tasks",
            "tools_needed": ["llm"],
            "api_cost": "low",
            "speed": "very fast"
        },
        "research": {
            "description": "Multi-source research with synthesis",
            "characteristics": "Deep learning, comprehensive overview, multiple sources",
            "tools_needed": ["research_apis"],
            "api_cost": "medium",
            "speed": "medium"
        },
        "browser": {
            "description": "Direct page scraping",
            "characteristics": "Specific website data, extraction, form filling",
            "tools_needed": ["headless_browser"],
            "api_cost": "low",
            "speed": "medium"
        },
        "hybrid": {
            "description": "Research + Browser verification",
            "characteristics": "Real-time data, verification, live updates",
            "tools_needed": ["research_apis", "headless_browser"],
            "api_cost": "high",
            "speed": "slow"
        }
    }
    
    # ─── KEYWORD DETECTION MAPS ──────────────────────────────────────────────
    
    CHAT_KEYWORDS = {
        "explain": 5, "what is": 5, "how does": 5, "tell me": 4,
        "describe": 5, "define": 5, "why": 4, "how to": 3,
        "creative": 5, "write": 4, "poem": 5, "story": 5,
        "opinion": 5, "think about": 4, "help me": 3,
        "teach me": 3, "understand": 3, "difference": 4,
        "analogy": 5, "example": 3, "summarize": 2,
    }
    
    RESEARCH_KEYWORDS = {
        "research": 10, "investigate": 8, "deep dive": 9, "comprehensive": 7,
        "everything about": 8, "detailed": 6, "history of": 7, "background": 5,
        "detailed analysis": 8, "thorough": 6, "all about": 7, "explain fully": 5,
        "trending": 5, "news about": 6, "latest on": 6, "overview": 4,
        "report": 5, "findings": 5, "evidence": 6, "sources": 5,
    }
    
    BROWSER_KEYWORDS = {
        "extract from": 10, "scrape": 10, "from this website": 9,
        "this page": 8, "this url": 9, "fetch": 7, "open": 5,
        "download from": 8, "get data from": 8, "read this": 6,
        "this link": 7, "visit": 5, "browse": 5, "find in": 6,
        "look at": 4, "form fill": 10, "submit form": 10, "login": 10,
    }
    
    HYBRID_KEYWORDS = {
        "current": 8, "live": 8, "real-time": 10, "now": 6,
        "today": 5, "latest": 7, "price": 8, "stock": 8,
        "crypto": 8, "bitcoin": 8, "ethereum": 8, "verify": 9,
        "is it true": 10, "fact check": 10, "confirm": 8,
        "check if": 8, "is this correct": 8, "up to date": 7,
        "weather": 8, "score": 8, "ranking": 7, "leaderboard": 7,
    }
    
    REAL_TIME_TOPICS = [
        "bitcoin", "ethereum", "crypto", "price", "stock", "weather",
        "score", "game", "news", "trending", "covid", "update",
        "current", "latest", "live", "breaking", "today"
    ]
    
    VERIFICATION_TRIGGERS = [
        "is it true", "fact check", "verify", "confirm", "is this correct",
        "accurate", "reliable", "real", "fake", "hoax", "myth"
    ]
    
    def __init__(self, provider: str = "auto", verbose: bool = False):
        self.provider = provider
        self.verbose = verbose
        self.last_routing = None
        self.routing_history = []
    
    # ─── MAIN ROUTING METHOD ─────────────────────────────────────────────────
    
    def route(self, user_input: str) -> Dict:
        """
        Route a user query to the optimal execution mode.
        
        Returns:
            {
                "mode": "chat|research|browser|hybrid",
                "confidence": 0.0-1.0,
                "reasoning": "why this mode",
                "parameters": {...},
                "fallback_mode": "alternative mode if primary fails"
            }
        """
        # Analyze the query
        analysis = self._analyze_query(user_input)
        
        # Get mode scores
        mode_scores = self._score_all_modes(user_input, analysis)
        
        # Select best mode
        best_mode, confidence = self._select_mode(mode_scores)
        
        # Build routing decision
        routing = {
            "mode": best_mode,
            "confidence": confidence,
            "reasoning": mode_scores[best_mode]["reasoning"],
            "parameters": self._build_parameters(best_mode, user_input, analysis),
            "fallback_mode": self._select_fallback_mode(mode_scores, best_mode),
            "timestamp": datetime.now().isoformat(),
            "query_hash": self._hash_query(user_input),
        }
        
        self.last_routing = routing
        self.routing_history.append(routing)
        
        if self.verbose:
            print(f"\n[SMART ROUTER DEBUG]")
            print(f"Query: {user_input[:80]}...")
            print(f"Mode: {best_mode} (confidence: {confidence:.2%})")
            print(f"Reasoning: {routing['reasoning']}")
            print(f"Mode Scores: {json.dumps({k: v['score'] for k, v in mode_scores.items()}, indent=2)}")
        
        return routing
    
    # ─── QUERY ANALYSIS ──────────────────────────────────────────────────────
    
    def _analyze_query(self, user_input: str) -> Dict:
        """Extract features from query."""
        lower = user_input.lower()
        
        return {
            "length": len(user_input),
            "word_count": len(user_input.split()),
            "has_url": self._contains_url(user_input),
            "urls": self._extract_urls(user_input),
            "has_question": "?" in user_input,
            "has_command": user_input.startswith("/"),
            "is_time_sensitive": self._is_time_sensitive(lower),
            "is_data_point": self._is_data_point_query(lower),
            "is_verification": self._is_verification_query(lower),
            "is_scraping": self._is_scraping_request(lower),
            "keywords_found": self._find_keywords(lower),
            "entities": self._extract_entities(user_input),
        }
    
    def _score_all_modes(self, user_input: str, analysis: Dict) -> Dict:
        """Score each mode based on query features."""
        
        # Initialize scores
        scores = {
            "chat": {"score": 0.0, "reasoning": "", "factors": {}},
            "research": {"score": 0.0, "reasoning": "", "factors": {}},
            "browser": {"score": 0.0, "reasoning": "", "factors": {}},
            "hybrid": {"score": 0.0, "reasoning": "", "factors": {}},
        }
        
        # CHAT MODE SCORING
        chat_score = 0.0
        chat_factors = {}
        
        if not analysis["has_url"] and not analysis["is_data_point"]:
            chat_score += 0.3
            chat_factors["no_url_or_data_point"] = 0.3
        
        if analysis["is_time_sensitive"] == False:
            chat_score += 0.2
            chat_factors["not_time_sensitive"] = 0.2
        
        chat_keywords_score = self._keyword_match_score(
            analysis["keywords_found"], self.CHAT_KEYWORDS
        )
        chat_score += chat_keywords_score * 0.3
        chat_factors[f"chat_keywords ({chat_keywords_score:.2f})"] = chat_keywords_score * 0.3
        
        if analysis["word_count"] < 8 and not analysis["is_verification"]:
            chat_score += 0.2
            chat_factors["short_simple_query"] = 0.2
        
        scores["chat"]["score"] = min(1.0, chat_score)
        scores["chat"]["factors"] = chat_factors
        scores["chat"]["reasoning"] = (
            "User asks a general question requiring direct LLM response. "
            f"Chat keywords found: {list(analysis['keywords_found'].keys())[:3]}. "
            f"No real-time or verification needs detected."
        )
        
        # RESEARCH MODE SCORING
        research_score = 0.0
        research_factors = {}
        
        if "research" in str(analysis["keywords_found"]) or "everything about" in user_input.lower():
            research_score += 0.4
            research_factors["explicit_research_request"] = 0.4
        
        research_keywords_score = self._keyword_match_score(
            analysis["keywords_found"], self.RESEARCH_KEYWORDS
        )
        research_score += research_keywords_score * 0.3
        research_factors[f"research_keywords ({research_keywords_score:.2f})"] = research_keywords_score * 0.3
        
        if analysis["word_count"] > 10:
            research_score += 0.15
            research_factors["detailed_query"] = 0.15
        
        if not analysis["has_url"] and not analysis["is_verification"]:
            research_score += 0.15
            research_factors["no_specific_url"] = 0.15
        
        scores["research"]["score"] = min(1.0, research_score)
        scores["research"]["factors"] = research_factors
        scores["research"]["reasoning"] = (
            "User requests comprehensive research or multi-source information. "
            f"Will gather {3 if research_score < 0.5 else 6} sources "
            f"and synthesize findings."
        )
        
        # BROWSER MODE SCORING
        browser_score = 0.0
        browser_factors = {}
        
        if analysis["has_url"]:
            browser_score += 0.5
            browser_factors["has_url"] = 0.5
        
        browser_keywords_score = self._keyword_match_score(
            analysis["keywords_found"], self.BROWSER_KEYWORDS
        )
        browser_score += browser_keywords_score * 0.3
        browser_factors[f"browser_keywords ({browser_keywords_score:.2f})"] = browser_keywords_score * 0.3
        
        if analysis["is_scraping"]:
            browser_score += 0.2
            browser_factors["scraping_request"] = 0.2
        
        scores["browser"]["score"] = min(1.0, browser_score)
        scores["browser"]["factors"] = browser_factors
        scores["browser"]["reasoning"] = (
            "User wants to extract or scrape content from specific website(s). "
            f"URLs: {len(analysis['urls'])} detected. "
            "Will use headless browser for extraction."
        )
        
        # HYBRID MODE SCORING
        hybrid_score = 0.0
        hybrid_factors = {}
        
        if analysis["is_time_sensitive"]:
            hybrid_score += 0.4
            hybrid_factors["time_sensitive_query"] = 0.4
        
        if analysis["is_verification"]:
            hybrid_score += 0.35
            hybrid_factors["verification_needed"] = 0.35
        
        if analysis["is_data_point"]:
            hybrid_score += 0.25
            hybrid_factors["specific_data_point"] = 0.25
        
        hybrid_keywords_score = self._keyword_match_score(
            analysis["keywords_found"], self.HYBRID_KEYWORDS
        )
        hybrid_score += hybrid_keywords_score * 0.25
        hybrid_factors[f"hybrid_keywords ({hybrid_keywords_score:.2f})"] = hybrid_keywords_score * 0.25
        
        # Boost if multiple trigger conditions met
        trigger_count = sum([
            analysis["is_time_sensitive"],
            analysis["is_verification"],
            analysis["is_data_point"],
            analysis["has_url"]
        ])
        if trigger_count >= 2:
            hybrid_score += 0.15
            hybrid_factors["multiple_hybrid_triggers"] = 0.15
        
        scores["hybrid"]["score"] = min(1.0, hybrid_score)
        scores["hybrid"]["factors"] = hybrid_factors
        scores["hybrid"]["reasoning"] = (
            f"Query requires real-time verification and multiple sources. "
            f"Will research → fetch → verify across sources. "
            f"Triggers: time_sensitive={analysis['is_time_sensitive']}, "
            f"verification={analysis['is_verification']}, "
            f"data_point={analysis['is_data_point']}"
        )
        
        return scores
    
    def _select_mode(self, mode_scores: Dict) -> Tuple[str, float]:
        """Select mode with highest confidence."""
        best_mode = max(mode_scores.items(), key=lambda x: x[1]["score"])
        return best_mode[0], best_mode[1]["score"]
    
    def _select_fallback_mode(self, mode_scores: Dict, primary_mode: str) -> str:
        """Select backup mode if primary fails."""
        fallback_hierarchy = {
            "chat": "research",
            "research": "browser",
            "browser": "chat",
            "hybrid": "research"
        }
        return fallback_hierarchy.get(primary_mode, "chat")
    
    # ─── FEATURE EXTRACTION ──────────────────────────────────────────────────
    
    def _contains_url(self, text: str) -> bool:
        """Check if text contains URL."""
        return bool(re.search(r'https?://', text))
    
    def _extract_urls(self, text: str) -> List[str]:
        """Extract all URLs from text."""
        return re.findall(r'https?://[^\s]+', text)
    
    def _is_time_sensitive(self, query_lower: str) -> bool:
        """Detect if query is time-sensitive."""
        time_indicators = [
            "current", "now", "today", "live", "real-time", "latest",
            "latest", "recent", "today", "tomorrow", "update", "breaking"
        ]
        return any(indicator in query_lower for indicator in time_indicators)
    
    def _is_data_point_query(self, query_lower: str) -> bool:
        """Detect if query asks for specific data point."""
        data_point_indicators = [
            "price", "cost", "how much", "what is the", "temperature",
            "score", "ranking", "weather", "date", "time", "number",
            "how many", "percentage", "rate", "value"
        ]
        return any(indicator in query_lower for indicator in data_point_indicators)
    
    def _is_verification_query(self, query_lower: str) -> bool:
        """Detect if query needs fact verification."""
        return any(trigger in query_lower for trigger in self.VERIFICATION_TRIGGERS)
    
    def _is_scraping_request(self, query_lower: str) -> bool:
        """Detect if query is a scraping request."""
        scraping_triggers = [
            "extract", "scrape", "from this", "from that", "get data",
            "download", "fetch from", "pull from", "read from"
        ]
        return any(trigger in query_lower for trigger in scraping_triggers)
    
    def _find_keywords(self, query_lower: str) -> Dict[str, int]:
        """Find all keywords in query."""
        found = {}
        all_keywords = {
            **self.CHAT_KEYWORDS,
            **self.RESEARCH_KEYWORDS,
            **self.BROWSER_KEYWORDS,
            **self.HYBRID_KEYWORDS,
        }
        for keyword, weight in all_keywords.items():
            if keyword in query_lower:
                found[keyword] = weight
        return found
    
    def _extract_entities(self, text: str) -> List[str]:
        """Extract named entities (topics, people, places)."""
        # Simple extraction - can be enhanced with NER
        entities = []
        
        # Detect named entities (capitalized words)
        for word in text.split():
            if word[0].isupper() and len(word) > 2:
                entities.append(word)
        
        # Detect topics from real-time list
        text_lower = text.lower()
        for topic in self.REAL_TIME_TOPICS:
            if topic in text_lower:
                entities.append(topic)
        
        return list(set(entities))
    
    def _keyword_match_score(self, found_keywords: Dict, target_keywords: Dict) -> float:
        """Score how well query matches keyword set."""
        if not found_keywords:
            return 0.0
        
        total_weight = sum(target_keywords.get(k, 0) for k in found_keywords.keys())
        max_weight = sum(target_keywords.values())
        
        return min(1.0, total_weight / max_weight) if max_weight > 0 else 0.0
    
    def _hash_query(self, query: str) -> str:
        """Generate hash of query for caching."""
        import hashlib
        return hashlib.md5(query.lower().encode()).hexdigest()[:8]
    
    # ─── PARAMETER BUILDING ──────────────────────────────────────────────────
    
    def _build_parameters(self, mode: str, user_input: str, analysis: Dict) -> Dict:
        """Build execution parameters for selected mode."""
        
        base_params = {
            "query": user_input,
            "mode": mode,
            "timeout": 30,
            "retry_count": 2,
        }
        
        if mode == "chat":
            return {
                **base_params,
                "use_llm": True,
                "stream": False,
            }
        
        elif mode == "research":
            return {
                **base_params,
                "depth": "deep" if analysis["word_count"] > 15 else "standard",
                "target_sources": 8 if analysis["word_count"] > 15 else 5,
                "include_citations": True,
                "verify_sources": True,
            }
        
        elif mode == "browser":
            return {
                **base_params,
                "urls": analysis["urls"],
                "extract_type": "all",  # markdown, html, tables, links, all
                "headless": True,
                "javascript_rendering": True,
            }
        
        elif mode == "hybrid":
            return {
                **base_params,
                "research_first": True,
                "verify_sources": True,
                "browser_verification": True,
                "target_sources": 5,
                "extract_type": "markdown",
                "combine_results": True,
            }
        
        return base_params
    
    # ─── UTILITY METHODS ─────────────────────────────────────────────────────
    
    def get_mode_info(self, mode: str) -> Dict:
        """Get detailed info about a mode."""
        return self.MODES.get(mode, {})
    
    def get_routing_history(self, limit: int = 10) -> List[Dict]:
        """Get recent routing decisions."""
        return self.routing_history[-limit:]
    
    def get_statistics(self) -> Dict:
        """Get routing statistics."""
        if not self.routing_history:
            return {}
        
        mode_counts = {}
        for routing in self.routing_history:
            mode = routing["mode"]
            mode_counts[mode] = mode_counts.get(mode, 0) + 1
        
        avg_confidence = sum(r["confidence"] for r in self.routing_history) / len(self.routing_history)
        
        return {
            "total_queries": len(self.routing_history),
            "mode_distribution": mode_counts,
            "average_confidence": avg_confidence,
            "most_common_mode": max(mode_counts, key=mode_counts.get) if mode_counts else None,
        }

