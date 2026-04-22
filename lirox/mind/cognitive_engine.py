import json
import time
import re
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple, Callable
from collections import defaultdict
import traceback


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: CORE DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

class Complexity(Enum):
    """Query complexity tiers — determines reasoning depth."""
    TRIVIAL = auto()      # "hi", "thanks" → skip reasoning entirely
    SIMPLE = auto()       # "what is X?" → single-pass reasoning
    MODERATE = auto()     # "explain X vs Y" → multi-step reasoning
    COMPLEX = auto()      # "create a presentation on X" → full pipeline
    EXPERT = auto()       # "design a system that..." → deep multi-pass reasoning
    RESEARCH = auto()     # "analyze and compare..." → extended reasoning with verification


class Intent(Enum):
    """Detected user intent categories."""
    GREETING = auto()
    FAREWELL = auto()
    ACKNOWLEDGMENT = auto()
    FACTUAL_QUERY = auto()
    EXPLANATION = auto()
    COMPARISON = auto()
    OPINION = auto()
    CREATIVE_WRITING = auto()
    CODE_GENERATION = auto()
    CODE_DEBUG = auto()
    FILE_READ = auto()
    FILE_WRITE = auto()
    FILE_EDIT = auto()
    PRESENTATION = auto()
    PDF_CREATION = auto()
    SYSTEM_COMMAND = auto()
    WEB_SEARCH = auto()
    ANALYSIS = auto()
    PLANNING = auto()
    CONVERSATION = auto()
    MULTI_TASK = auto()
    UNKNOWN = auto()


class ConfidenceLevel(Enum):
    """How confident the engine is in its reasoning."""
    CERTAIN = "certain"          # 95%+ — direct facts, simple operations
    HIGH = "high"                # 80-95% — well-understood domain
    MODERATE = "moderate"        # 60-80% — some ambiguity
    LOW = "low"                  # 40-60% — significant uncertainty
    SPECULATIVE = "speculative"  # <40% — best guess, should flag to user


@dataclass
class ThoughtNode:
    """
    A single unit of reasoning in the thought chain.
    Each node represents one cognitive step with its inputs,
    processing, and outputs.
    """
    step_id: int
    phase: str                           # Which cognitive phase this belongs to
    description: str                     # What this step does
    input_data: Any = None               # What this step received
    output_data: Any = None              # What this step produced
    confidence: float = 1.0              # 0.0-1.0 confidence in this step
    duration_ms: float = 0.0             # How long this step took
    children: List['ThoughtNode'] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "step": self.step_id,
            "phase": self.phase,
            "description": self.description,
            "confidence": self.confidence,
            "duration_ms": self.duration_ms,
            "children": [c.to_dict() for c in self.children],
            "metadata": self.metadata,
        }


@dataclass
class ReasoningTrace:
    """
    The complete reasoning trace for a single query.
    This is the internal "thinking" that Lirox does before responding.
    """
    query: str
    complexity: Complexity = Complexity.SIMPLE
    intent: Intent = Intent.UNKNOWN
    thought_chain: List[ThoughtNode] = field(default_factory=list)
    selected_strategy: Optional[str] = None
    tool_plan: List[Dict[str, Any]] = field(default_factory=list)
    verification_results: List[Dict[str, Any]] = field(default_factory=list)
    self_corrections: List[str] = field(default_factory=list)
    final_confidence: float = 1.0
    total_duration_ms: float = 0.0
    reasoning_depth: int = 0              # How many passes of reasoning were done
    
    def add_thought(self, phase: str, description: str, **kwargs) -> ThoughtNode:
        node = ThoughtNode(
            step_id=len(self.thought_chain) + 1,
            phase=phase,
            description=description,
            **kwargs
        )
        self.thought_chain.append(node)
        return node
    
    def get_summary(self) -> str:
        """Generate a human-readable summary of the reasoning trace."""
        lines = []
        for node in self.thought_chain:
            indent = "  " if not node.children else ""
            conf = f" [{node.confidence:.0%}]" if node.confidence < 1.0 else ""
            lines.append(f"{indent}[{node.phase}] {node.description}{conf}")
            for child in node.children:
                lines.append(f"    └─ {child.description}")
        return "\n".join(lines)


@dataclass
class CognitiveContext:
    """
    Accumulated context from the conversation and environment.
    This is what the reasoning engine "knows" when processing a query.
    """
    user_name: str = ""
    workspace: str = ""
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    available_tools: List[str] = field(default_factory=list)
    recent_files: List[str] = field(default_factory=list)
    recent_tool_results: List[Dict[str, Any]] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    session_facts: Dict[str, Any] = field(default_factory=dict)  # Facts learned during session
    error_history: List[str] = field(default_factory=list)        # Recent errors to avoid repeating
    
    def get_last_n_messages(self, n: int = 5) -> List[Dict[str, str]]:
        return self.conversation_history[-n:] if self.conversation_history else []
    
    def add_session_fact(self, key: str, value: Any):
        self.session_facts[key] = value
    
    def get_session_fact(self, key: str, default=None):
        return self.session_facts.get(key, default)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: INTENT & COMPLEXITY CLASSIFIER
# ─────────────────────────────────────────────────────────────────────────────

class IntentClassifier:
    """
    Advanced intent detection and complexity classification.
    Uses pattern matching, keyword analysis, and structural analysis
    to determine what the user wants and how complex the task is.
    """
    
    # ── Pattern Definitions ──
    
    GREETING_PATTERNS = {
        "hi", "hello", "hey", "sup", "yo", "hola", "namaste",
        "good morning", "good afternoon", "good evening", "good night",
        "what's up", "whats up", "howdy", "greetings",
    }
    
    FAREWELL_PATTERNS = {
        "bye", "goodbye", "see you", "later", "night", "cya",
        "take care", "peace", "exit", "quit",
    }
    
    ACKNOWLEDGMENT_PATTERNS = {
        "ok", "okay", "sure", "thanks", "thank you", "thx", "ty",
        "got it", "understood", "cool", "nice", "great", "awesome",
        "perfect", "yes", "no", "yep", "nope", "alright",
    }
    
    FILE_WRITE_KEYWORDS = {
        "create", "make", "write", "generate", "build", "produce",
        "save", "export", "output", "draft",
    }
    
    FILE_TYPE_KEYWORDS = {
        "presentation": Intent.PRESENTATION,
        "pptx": Intent.PRESENTATION,
        "slides": Intent.PRESENTATION,
        "deck": Intent.PRESENTATION,
        "powerpoint": Intent.PRESENTATION,
        "pdf": Intent.PDF_CREATION,
        "document": Intent.FILE_WRITE,
        "docx": Intent.FILE_WRITE,
        "word": Intent.FILE_WRITE,
        "report": Intent.FILE_WRITE,
        "file": Intent.FILE_WRITE,
        "spreadsheet": Intent.FILE_WRITE,
        "xlsx": Intent.FILE_WRITE,
        "excel": Intent.FILE_WRITE,
    }
    
    CODE_KEYWORDS = {
        "code", "function", "class", "script", "program", "algorithm",
        "implement", "develop", "api", "endpoint", "database",
        "python", "javascript", "typescript", "react", "html", "css",
        "java", "rust", "go", "ruby", "php", "swift", "kotlin",
        "app", "application", "website", "server", "cli", "tool",
        "module", "package", "library", "framework",
    }
    
    DEBUG_KEYWORDS = {
        "fix", "bug", "error", "crash", "broken", "not working",
        "debug", "issue", "problem", "wrong", "fails",
    }
    
    ANALYSIS_KEYWORDS = {
        "analyze", "analyse", "compare", "evaluate", "assess",
        "review", "audit", "examine", "investigate", "study",
        "breakdown", "break down", "deep dive",
    }
    
    EXPLANATION_TRIGGERS = {
        "what is", "what are", "what's", "explain", "describe",
        "tell me about", "how does", "how do", "why does", "why do",
        "what does", "define", "meaning of",
    }
    
    PLANNING_KEYWORDS = {
        "plan", "strategy", "roadmap", "design", "architect",
        "structure", "organize", "outline", "blueprint",
    }
    
    CREATIVE_KEYWORDS = {
        "story", "poem", "essay", "article", "blog", "letter",
        "email", "message", "speech", "script", "narrative",
    }
    
    @classmethod
    def classify(cls, query: str, context: CognitiveContext) -> Tuple[Intent, Complexity]:
        q = query.strip()
        q_lower = q.lower()
        words = q_lower.split()
        word_count = len(words)
        
        # ── Phase 1: Trivial Pattern Matching ──
        if q_lower in cls.GREETING_PATTERNS or (word_count <= 2 and any(g in q_lower for g in cls.GREETING_PATTERNS)):
            return Intent.GREETING, Complexity.TRIVIAL
        
        if q_lower in cls.FAREWELL_PATTERNS or any(f in q_lower for f in cls.FAREWELL_PATTERNS):
            return Intent.FAREWELL, Complexity.TRIVIAL
        
        if q_lower in cls.ACKNOWLEDGMENT_PATTERNS:
            return Intent.ACKNOWLEDGMENT, Complexity.TRIVIAL
        
        # ── Phase 2: File Operation Detection ──
        has_write_keyword = any(kw in q_lower for kw in cls.FILE_WRITE_KEYWORDS)
        
        detected_file_intent = None
        for keyword, intent in cls.FILE_TYPE_KEYWORDS.items():
            if keyword in q_lower:
                detected_file_intent = intent
                break
        
        if has_write_keyword and detected_file_intent:
            return detected_file_intent, Complexity.COMPLEX
        
        read_patterns = ["read", "open", "show", "display", "list", "what's in", "tell me about my"]
        file_indicators = ["file", "folder", "directory", "downloads", "desktop", "documents"]
        if any(rp in q_lower for rp in read_patterns) and any(fi in q_lower for fi in file_indicators):
            return Intent.FILE_READ, Complexity.MODERATE
        
        # ── Phase 3: Code Operations ──
        has_code_kw = any(kw in q_lower for kw in cls.CODE_KEYWORDS)
        has_debug_kw = any(kw in q_lower for kw in cls.DEBUG_KEYWORDS)
        
        if has_debug_kw and has_code_kw:
            return Intent.CODE_DEBUG, Complexity.COMPLEX
        if has_debug_kw:
            return Intent.CODE_DEBUG, Complexity.MODERATE
        if has_code_kw and has_write_keyword:
            return Intent.CODE_GENERATION, Complexity.COMPLEX
        
        # ── Phase 4: Analysis & Research ──
        has_analysis_kw = any(kw in q_lower for kw in cls.ANALYSIS_KEYWORDS)
        if has_analysis_kw:
            if word_count > 20:
                return Intent.ANALYSIS, Complexity.RESEARCH
            elif word_count > 10:
                return Intent.ANALYSIS, Complexity.EXPERT
            else:
                return Intent.ANALYSIS, Complexity.COMPLEX
        
        # ── Phase 5: Explanation Queries ──
        if any(q_lower.startswith(trigger) for trigger in cls.EXPLANATION_TRIGGERS):
            if word_count > 15:
                return Intent.EXPLANATION, Complexity.COMPLEX
            elif word_count > 8:
                return Intent.EXPLANATION, Complexity.MODERATE
            else:
                return Intent.EXPLANATION, Complexity.SIMPLE
        
        # ── Phase 6: Comparison Detection ──
        comparison_markers = [" vs ", " versus ", " compared to ", " or ", " better ", " difference between"]
        if any(cm in q_lower for cm in comparison_markers):
            return Intent.COMPARISON, Complexity.MODERATE
        
        # ── Phase 7: Planning ──
        if any(kw in q_lower for kw in cls.PLANNING_KEYWORDS):
            return Intent.PLANNING, Complexity.COMPLEX
        
        # ── Phase 8: Creative Writing ──
        if any(kw in q_lower for kw in cls.CREATIVE_KEYWORDS) and has_write_keyword:
            return Intent.CREATIVE_WRITING, Complexity.COMPLEX
        
        # ── Phase 9: Multi-Task Detection ──
        task_separators = [" and then ", " after that ", " also ", " plus ", " additionally "]
        if any(sep in q_lower for sep in task_separators) and word_count > 12:
            return Intent.MULTI_TASK, Complexity.EXPERT
        
        # ── Phase 10: Fallback ──
        if word_count > 30:
            return Intent.CONVERSATION, Complexity.COMPLEX
        elif word_count > 15:
            return Intent.CONVERSATION, Complexity.MODERATE
        elif word_count > 5:
            return Intent.FACTUAL_QUERY, Complexity.SIMPLE
        else:
            return Intent.CONVERSATION, Complexity.SIMPLE


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: QUERY ANALYZER — Deep Understanding
# ─────────────────────────────────────────────────────────────────────────────

class QueryAnalyzer:
    @staticmethod
    def analyze(query: str, intent: Intent, context: CognitiveContext) -> Dict[str, Any]:
        q_lower = query.lower()
        analysis = {
            "raw_query": query,
            "intent": intent.name,
            "word_count": len(query.split()),
            "has_question_mark": "?" in query,
            "has_urgency": False,
            "entities": [],
            "constraints": [],
            "implicit_requirements": [],
            "output_format": None,
            "target_path": None,
            "topic": None,
            "personalization": {},
            "creativity_level": "standard",
            "quality_expectations": "professional",
        }
        
        # ── Entity Extraction ──
        path_pattern = r'[A-Za-z]:\\[^\s]+|\/[^\s]+'
        paths = re.findall(path_pattern, query)
        if paths:
            analysis["target_path"] = paths[0]
            analysis["entities"].extend([{"type": "path", "value": p} for p in paths])
        
        words = query.split()
        for i, word in enumerate(words):
            if i > 0 and word[0].isupper() and word.lower() not in {"i", "the", "a", "an"}:
                analysis["entities"].append({"type": "name_or_noun", "value": word})
        
        topic_triggers = ["about", "on", "regarding", "for", "titled", "called"]
        for trigger in topic_triggers:
            pattern = rf'\b{trigger}\b\s+(.+?)(?:\s+(?:with|in|using|by|for)\b|$)'
            match = re.search(pattern, q_lower)
            if match:
                analysis["topic"] = match.group(1).strip().rstrip(".,!?")
                break
        
        if any(w in q_lower for w in ["short", "brief", "concise", "quick"]):
            analysis["constraints"].append("brevity")
        if any(w in q_lower for w in ["detailed", "comprehensive", "thorough", "in-depth"]):
            analysis["constraints"].append("depth")
        if any(w in q_lower for w in ["long", "extensive", "full"]):
            analysis["constraints"].append("extensive")
        
        if "bullet" in q_lower:
            analysis["output_format"] = "bullets"
        elif "table" in q_lower:
            analysis["output_format"] = "table"
        elif "step by step" in q_lower or "step-by-step" in q_lower:
            analysis["output_format"] = "steps"
        
        if intent == Intent.PRESENTATION:
            analysis["implicit_requirements"] = [
                "visual_design", "color_palette", "varied_layouts",
                "professional_formatting", "minimum_8_slides", "title_and_closing_slides"
            ]
            analysis["quality_expectations"] = "high"
            analysis["creativity_level"] = "creative"
        
        elif intent == Intent.PDF_CREATION:
            analysis["implicit_requirements"] = [
                "cover_page", "section_headers", "visual_hierarchy",
                "page_numbers", "professional_typography"
            ]
            analysis["quality_expectations"] = "high"
        
        elif intent == Intent.CODE_GENERATION:
            analysis["implicit_requirements"] = ["working_code", "error_handling", "comments", "clean_structure"]
        
        urgency_words = ["asap", "urgent", "quickly", "fast", "immediately", "now", "hurry"]
        if any(uw in q_lower for uw in urgency_words):
            analysis["has_urgency"] = True
        
        if "my name" in q_lower or "add my name" in q_lower:
            analysis["personalization"]["include_user_name"] = True
        
        if context.user_name:
            analysis["personalization"]["user_name"] = context.user_name
        
        if any(w in q_lower for w in ["creative", "unique", "innovative", "stunning", "beautiful"]):
            analysis["creativity_level"] = "high_creative"
        elif any(w in q_lower for w in ["simple", "basic", "minimal", "plain"]):
            analysis["creativity_level"] = "minimal"
        
        if any(w in q_lower for w in ["visual", "visuals", "images", "graphics", "illustrations", "design"]):
            analysis["implicit_requirements"].append("visual_elements")
        
        return analysis


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: STRATEGY ENGINE — Multi-Path Planning
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Strategy:
    name: str
    description: str
    steps: List[str]
    tools_needed: List[str]
    estimated_quality: float
    estimated_time: float
    risk_level: float
    creativity_score: float
    
    @property
    def composite_score(self) -> float:
        return (
            self.estimated_quality * 0.40 +
            self.creativity_score * 0.25 +
            (1.0 - self.risk_level) * 0.20 +
            max(0, 1.0 - self.estimated_time / 30.0) * 0.15
        )


class StrategyEngine:
    @staticmethod
    def generate_strategies(intent: Intent, analysis: Dict[str, Any], context: CognitiveContext) -> List[Strategy]:
        strategies = []
        topic = analysis.get("topic", "the topic")
        creativity = analysis.get("creativity_level", "standard")
        
        if intent == Intent.PRESENTATION:
            strategies.append(Strategy(
                name="comprehensive_showcase",
                description=f"Full 10-12 slide showcase on {topic} with varied layouts",
                steps=[
                    "Select topic-appropriate color palette",
                    "Generate detailed content outline (10-12 sections)",
                    "Design slide layout sequence (no repeats)",
                    "Generate rich content per slide",
                    "Build PPTX with visual elements on every slide",
                    "Add title and closing slides",
                ],
                tools_needed=["create_presentation"],
                estimated_quality=0.95, estimated_time=8.0, risk_level=0.15,
                creativity_score=0.85 if creativity != "minimal" else 0.5,
            ))
            strategies.append(Strategy(
                name="concise_impact",
                description=f"Focused 6-8 slide deck on {topic} with bolder designs",
                steps=[
                    "Select bold color palette", "Identify key themes",
                    "Design high-impact layouts", "Generate focused content",
                    "Build PPTX", "Add title and closing slides",
                ],
                tools_needed=["create_presentation"],
                estimated_quality=0.88, estimated_time=5.0, risk_level=0.10,
                creativity_score=0.90,
            ))
            if creativity == "high_creative":
                strategies.append(Strategy(
                    name="storytelling_narrative",
                    description=f"Narrative-driven deck for {topic}",
                    steps=["Craft narrative arc", "Select cinematic palette", "Design story chapters", "Write narrative", "Build PPTX"],
                    tools_needed=["create_presentation"],
                    estimated_quality=0.92, estimated_time=10.0, risk_level=0.25, creativity_score=0.98,
                ))
        
        elif intent == Intent.PDF_CREATION:
            strategies.append(Strategy(
                name="professional_report",
                description=f"Comprehensive report on {topic}",
                steps=["Structure sections", "Build cover page", "Write prose paragraphs", "Add visual dividers", "Generate PDF"],
                tools_needed=["create_pdf"],
                estimated_quality=0.93, estimated_time=6.0, risk_level=0.15, creativity_score=0.80,
            ))
            if "visual_elements" in analysis.get("implicit_requirements", []):
                strategies.append(Strategy(
                    name="visual_magazine",
                    description=f"Magazine-style PDF on {topic}",
                    steps=["Generate data heavy content", "Design infographic sections", "Build visual cover", "Create PDF"],
                    tools_needed=["create_pdf"],
                    estimated_quality=0.90, estimated_time=8.0, risk_level=0.20, creativity_score=0.92,
                ))
        
        elif intent in (Intent.CODE_GENERATION, Intent.CODE_DEBUG):
            strategies.append(Strategy(
                name="direct_implementation",
                description="Write clean code with error handling",
                steps=["Analyze requirements", "Design interfaces", "Implement logic", "Verify code"],
                tools_needed=["write_file"] if intent == Intent.CODE_GENERATION else ["read_file", "edit_file"],
                estimated_quality=0.90, estimated_time=5.0, risk_level=0.15, creativity_score=0.50,
            ))
        
        elif intent == Intent.ANALYSIS:
            strategies.append(Strategy(
                name="structured_analysis",
                description=f"Systematic analysis of {topic}",
                steps=["Define criteria", "Gather facts", "Analyze", "Conclude"],
                tools_needed=[],
                estimated_quality=0.92, estimated_time=5.0, risk_level=0.10, creativity_score=0.60,
            ))

        elif intent == Intent.FILE_WRITE:
            # Covers DOCX, XLSX, and general document creation
            q_lower = analysis.get("raw_query", "").lower()
            if any(w in q_lower for w in ["excel", "xlsx", "spreadsheet", "xls", "sheet", "table", "data"]):
                strategies.append(Strategy(
                    name="data_spreadsheet",
                    description=f"Structured Excel spreadsheet on {topic} with headers and data rows",
                    steps=[
                        "Define columns and data schema",
                        "Generate representative data rows",
                        "Apply header styling and alternating row colors",
                        "Auto-fit column widths",
                        "Save and verify",
                    ],
                    tools_needed=["create_spreadsheet"],
                    estimated_quality=0.92, estimated_time=4.0, risk_level=0.10, creativity_score=0.55,
                ))
            else:
                strategies.append(Strategy(
                    name="rich_word_document",
                    description=f"Formatted Word document on {topic} with headings and prose",
                    steps=[
                        "Outline document structure",
                        "Write introduction section",
                        "Write body sections with supporting detail",
                        "Add conclusion",
                        "Save and verify",
                    ],
                    tools_needed=["create_document"],
                    estimated_quality=0.91, estimated_time=5.0, risk_level=0.10, creativity_score=0.70,
                ))
        
        if not strategies:
            strategies.append(Strategy(
                name="direct_response",
                description="Direct, well-reasoned response",
                steps=["Reason through", "Compose answer"],
                tools_needed=[],
                estimated_quality=0.85, estimated_time=2.0, risk_level=0.05, creativity_score=0.50,
            ))
        
        return strategies
    
    @staticmethod
    def select_best(strategies: List[Strategy], preferences: Dict[str, Any] = None) -> Strategy:
        if not strategies:
            raise ValueError("No strategies to select from")
        if len(strategies) == 1:
            return strategies[0]
        if preferences:
            creativity_pref = preferences.get("creativity_level", "standard")
            for s in strategies:
                if creativity_pref == "high_creative":
                    s.creativity_score *= 1.2
                elif creativity_pref == "minimal":
                    s.creativity_score *= 0.7
        ranked = sorted(strategies, key=lambda s: s.composite_score, reverse=True)
        return ranked[0]


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: TOOL PLANNER — Smart Tool Orchestration
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ToolCall:
    tool_name: str
    parameters: Dict[str, Any]
    purpose: str
    depends_on: Optional[int] = None
    fallback_tool: Optional[str] = None
    is_optional: bool = False
    estimated_duration: float = 1.0


class ToolPlanner:
    @classmethod
    def plan(cls, intent: Intent, analysis: Dict[str, Any], strategy: Strategy, available_tools: List[str]) -> List[ToolCall]:
        plan = []
        if intent == Intent.FILE_READ:
            target = analysis.get("target_path", "")
            plan.append(ToolCall(tool_name="list_files", parameters={"path": target}, purpose=f"List {target}"))
        elif intent == Intent.PRESENTATION:
            topic = analysis.get("topic", "Untitled")
            user_name = analysis.get("personalization", {}).get("user_name", "")
            plan.append(ToolCall(
                tool_name="create_presentation",
                parameters={"topic": topic, "user_name": user_name, "strategy": strategy.name, "creativity": analysis.get("creativity_level", "standard"), "min_slides": 8},
                purpose=f"Create PPTX on {topic}",
                estimated_duration=5.0,
            ))
        elif intent == Intent.PDF_CREATION:
            topic = analysis.get("topic", "Untitled")
            user_name = analysis.get("personalization", {}).get("user_name", "")
            has_visuals = "visual_elements" in analysis.get("implicit_requirements", [])
            plan.append(ToolCall(
                tool_name="create_pdf",
                parameters={"topic": topic, "user_name": user_name, "style": "visual_magazine" if has_visuals else "professional_report", "min_pages": 4},
                purpose=f"Create PDF on {topic}",
                estimated_duration=4.0,
            ))
        elif intent == Intent.FILE_WRITE:
            topic = analysis.get("topic", "Untitled")
            user_name = analysis.get("personalization", {}).get("user_name", "")
            q_lower = analysis.get("raw_query", "").lower()
            if any(w in q_lower for w in ["excel", "xlsx", "spreadsheet", "xls", "sheet", "table", "data"]):
                plan.append(ToolCall(
                    tool_name="create_spreadsheet",
                    parameters={"topic": topic, "user_name": user_name, "strategy": strategy.name},
                    purpose=f"Create XLSX spreadsheet on {topic}",
                    estimated_duration=3.0,
                ))
            else:
                plan.append(ToolCall(
                    tool_name="create_document",
                    parameters={"topic": topic, "user_name": user_name, "strategy": strategy.name},
                    purpose=f"Create DOCX document on {topic}",
                    estimated_duration=4.0,
                ))
        elif intent == Intent.CODE_GENERATION:
            plan.append(ToolCall(tool_name="write_file", parameters={"content": "", "path": analysis.get("target_path", "")}, purpose="Write generated code"))
        elif intent in (Intent.FILE_EDIT, Intent.CODE_DEBUG):
            target = analysis.get("target_path", "")
            if target:
                plan.append(ToolCall(tool_name="read_file", parameters={"path": target}, purpose=f"Read {target}"))
                plan.append(ToolCall(tool_name="edit_file", parameters={"path": target, "changes": []}, purpose=f"Apply fixes to {target}", depends_on=1))
        return plan


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: SELF-VERIFICATION ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class VerificationEngine:
    @staticmethod
    def verify_response(query: str, intent: Intent, response: str, analysis: Dict[str, Any], tool_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        results = {"passed": True, "issues": [], "suggestions": [], "quality_score": 1.0}
        if not response or len(response.strip()) < 5:
            results["passed"] = False
            results["issues"].append("Response empty")
            results["quality_score"] -= 0.5
        topic = analysis.get("topic", "")
        if topic and topic.lower() not in response.lower() and len(response) > 50:
            results["suggestions"].append(f"Not addressing {topic}")
            results["quality_score"] -= 0.1
        if tool_results and not any(tr.get("summary", "") in response for tr in tool_results):
            results["suggestions"].append("Tool results missing")
        if intent in (Intent.PRESENTATION, Intent.PDF_CREATION, Intent.FILE_WRITE):
            file_results = []
            for tr in tool_results:
                if "path" in tr or "file" in str(tr).lower() or tr.get("tool", "") in ("create_pdf", "create_document", "create_presentation", "create_spreadsheet", "create_xlsx", "create_docx"):
                    file_results.append(tr)
            if not file_results:
                results["passed"] = False
                results["issues"].append("File creation failed")
                results["quality_score"] -= 0.3
        file_size_pattern = r'\((\d+[\,\.]*\d*)\s*(bytes|KB|MB)\)'
        if re.findall(file_size_pattern, response) and not tool_results:
            results["issues"].append("Fake sizes mentioned")
            results["quality_score"] -= 0.3
        return results
    
    @staticmethod
    def suggest_corrections(issues: List[str], original_response: str, intent: Intent) -> List[str]:
        corrections = []
        for issue in issues:
            if "empty" in issue.lower(): corrections.append("Regenerate response detail")
            elif "file" in issue.lower(): corrections.append("Do not hallucinate file sizes without context")
        return corrections


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: PROMPT COMPOSER
# ─────────────────────────────────────────────────────────────────────────────

class PromptComposer:
    BASE_IDENTITY = "You are Lirox, an advanced personal AI agent operating as an intelligent terminal OS. Direct, confident, and creative."
    
    REASONING_MODIFIERS = {
        Complexity.TRIVIAL: "",
        Complexity.SIMPLE: "Think step by step if needed, but keep the answer concise.",
        Complexity.MODERATE: "Think carefully: 1. Identify key aspects 2. Structure your response 3. Answer directly",
        Complexity.COMPLEX: "Deep reasoning: 1. Break down 2. Consider tradeoffs 3. Precision 4. Verification",
        Complexity.EXPERT: "Expert level analysis needed. Map full problem space.",
        Complexity.RESEARCH: "Research grade reasoning. Gather multi-perspective evidence.",
    }
    
    INTENT_INSTRUCTIONS = {
        Intent.PRESENTATION: "PRESENTATION RULES: 8 slides minimum, topic-specific palettes, visual elements, no generic text dumps.",
        Intent.PDF_CREATION: "PDF RULES: Cover page, styled headers, callout boxes, 4 pages prose minimum.",
        Intent.CODE_GENERATION: "CODE RULES: Error handling, comments on WHY, clean docstrings.",
    }
    
    @classmethod
    def compose(cls, intent: Intent, complexity: Complexity, analysis: Dict[str, Any], strategy: Optional[Strategy], context: CognitiveContext) -> Dict[str, str]:
        parts = [cls.BASE_IDENTITY, cls.REASONING_MODIFIERS.get(complexity, ""), cls.INTENT_INSTRUCTIONS.get(intent, "")]
        if context.user_name: parts.append(f"User Name: {context.user_name}")
        if context.workspace: parts.append(f"Workspace: {context.workspace}")
        if strategy: parts.append(f"Strategy: {strategy.description}")
        return {"system": "\n\n".join(filter(None, parts)), "user": analysis["raw_query"] + (f"\nTopic: {analysis.get('topic')}" if analysis.get("topic") else "")}


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: COGNITIVE ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class CognitiveEngine:
    def __init__(self, context: CognitiveContext, llm_call: Callable, tool_executor: Callable, display: Any = None):
        self.context = context
        self.llm_call = llm_call
        self.tool_executor = tool_executor
        self.display = display
        self.trace = None
    
    def process(self, query: str) -> Dict[str, Any]:
        start_time = time.time()
        self.trace = ReasoningTrace(query=query)
        
        try:
            intent, complexity = IntentClassifier.classify(query, self.context)
            self.trace.intent = intent; self.trace.complexity = complexity
            if self.display: self.display.start(query, intent.name)
            
            if complexity == Complexity.TRIVIAL:
                response = self._handle_trivial(query, intent)
                self._finalize(start_time)
                return {"response": response, "trace": self.trace, "tools_used": [], "files_created": []}
            
            analysis = QueryAnalyzer.analyze(query, intent, self.context)
            if self.display: self.display.add_step("🔍", f"Analyzed: {analysis.get('topic', query[:50])}", "done")
            
            strategy = None
            if complexity.value >= Complexity.COMPLEX.value:
                strategies = StrategyEngine.generate_strategies(intent, analysis, self.context)
                strategy = StrategyEngine.select_best(strategies, analysis)
                if self.display: self.display.add_planning(strategy.name)
            
            tool_plan = []
            if strategy and strategy.tools_needed:
                tool_plan = ToolPlanner.plan(intent, analysis, strategy, self.context.available_tools)
            
            prompts = PromptComposer.compose(intent, complexity, analysis, strategy, self.context)
            
            tool_results = []
            files_created = []  # FIX-3: track files created by tools
            for tc in tool_plan:
                if self.display: self.display.add_tool_call(tc.tool_name, tc.purpose)
                try:
                    result = self.tool_executor(tc.tool_name, tc.parameters)
                    tool_results.append({"tool": tc.tool_name, "success": True, "result": result, "summary": str(result)[:200]})
                    if self.display: self.display.add_tool_result(tc.tool_name, str(result)[:100])
                    # FIX-3: collect file paths from receipts
                    if hasattr(result, 'path') and result.path:
                        files_created.append(str(result.path))
                except Exception as e:
                    tool_results.append({"tool": tc.tool_name, "success": False, "error": str(e)})
                    if self.display: self.display.add_step("🔧", f"{tc.tool_name} FAILED: {e}", "error")
            
            if tool_results:
                tool_context = "\n\nTool Execution Results:\n"
                for tr in tool_results:
                    if tr["success"]:
                        result = tr.get("result")
                        # FileReceipt objects have structured fields
                        if hasattr(result, 'message'):
                            tool_context += f"✓ {tr['tool']}: {result.message}\n"
                            if hasattr(result, 'path'):
                                tool_context += f"  File: {result.path}\n"
                            if hasattr(result, 'bytes_written'):
                                tool_context += f"  Size: {result.bytes_written:,} bytes\n"
                        else:
                            tool_context += f"✓ {tr['tool']}: {str(result)[:200]}\n"
                    else:
                        tool_context += f"✗ {tr['tool']}: FAILED — {tr.get('error', 'unknown')}\n"
                tool_context += "\nBased on these results, give the user a clear confirmation of what was done."
                prompts["user"] += tool_context
                
            if self.display: self.display.add_step("🤖", "Generating...", "running")
            llm_response = self.llm_call(system_prompt=prompts["system"], user_message=prompts["user"], conversation_history=self.context.get_last_n_messages())
            response_text = str(llm_response)
            
            if complexity.value >= Complexity.MODERATE.value:
                verification = VerificationEngine.verify_response(query, intent, response_text, analysis, tool_results)
                if not verification["passed"] and self.trace.reasoning_depth < 2:
                    self.trace.reasoning_depth += 1
                    corrections = VerificationEngine.suggest_corrections(verification["issues"], response_text, intent)
                    if self.display: self.display.add_step("🔄", "Self-correcting...", "running")
                    corrected = self.llm_call(
                        system_prompt=prompts["system"],
                        user_message=prompts["user"] + "\n\nCorrect issues: " + "; ".join(corrections),
                        conversation_history=self.context.get_last_n_messages()
                    )
                    response_text = str(corrected)
            
            self._finalize(start_time)
            return {"response": response_text, "trace": self.trace, "tools_used": [tr["tool"] for tr in tool_results if tr["success"]], "files_created": files_created}
            
        except Exception as e:
            self._finalize(start_time)
            return {"response": f"Error: {e}", "trace": self.trace, "tools_used": [], "files_created": [], "error": str(e)}

    def _handle_trivial(self, query: str, intent: Intent) -> str:
        if intent == Intent.FAREWELL: return "See you later! 👋"
        elif intent == Intent.ACKNOWLEDGMENT: return "Got it. What's next?"
        return self.llm_call(system_prompt="Be concise.", user_message=query, conversation_history=[])
        
    def _finalize(self, start_time: float):
        if self.display: self.display.finish()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: CONTEXT AGGREGATOR — rich context passing between stages
# ─────────────────────────────────────────────────────────────────────────────

class ContextAggregator:
    """Accumulates and merges context from multiple reasoning stages.

    Keeps the most recent conversation history, tool results, and session
    facts in a single object so that every downstream component has access
    to everything the engine has learned so far.
    """

    def __init__(self, context: CognitiveContext):
        self._ctx = context
        self._stage_outputs: List[Dict[str, Any]] = []

    def record_stage(self, stage: str, output: Any, metadata: Dict[str, Any] = None):
        """Record the output of a named reasoning stage."""
        self._stage_outputs.append({
            "stage": stage,
            "output": output,
            "metadata": metadata or {},
        })

    def get_stage_output(self, stage: str) -> Optional[Any]:
        """Return the most recent output of *stage*, or None if not recorded."""
        for entry in reversed(self._stage_outputs):
            if entry["stage"] == stage:
                return entry["output"]
        return None

    def enrich_context(self, tool_results: List[Dict[str, Any]], response: str = ""):
        """Feed tool results and partial response back into the context."""
        self._ctx.recent_tool_results.extend(tool_results)
        # Keep only the last 10 tool results to avoid ballooning context
        self._ctx.recent_tool_results = self._ctx.recent_tool_results[-10:]
        if response:
            self._stage_outputs.append({"stage": "response_draft", "output": response, "metadata": {}})

    def build_context_string(self, max_chars: int = 2000) -> str:
        """Produce a concise text summary of accumulated context for LLM prompts."""
        parts: List[str] = []
        if self._ctx.user_name:
            parts.append(f"User: {self._ctx.user_name}")
        if self._ctx.workspace:
            parts.append(f"Workspace: {self._ctx.workspace}")
        for tr in self._ctx.recent_tool_results[-3:]:
            tool = tr.get("tool", "?")
            if tr.get("success"):
                parts.append(f"Recent tool success: {tool} — {str(tr.get('result', ''))[:100]}")
            else:
                parts.append(f"Recent tool failure: {tool} — {tr.get('error', '?')[:80]}")
        text = "\n".join(parts)
        return text[:max_chars]

    @property
    def context(self) -> CognitiveContext:
        return self._ctx


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10: DEEP REASONING ENGINE — multi-pass reasoning with self-correction
# ─────────────────────────────────────────────────────────────────────────────

class DeepReasoningEngine:
    """Multi-pass reasoning with iterative refinement and self-correction.

    Algorithm:
      1. Pass 1 — initial reasoning: classify, analyse, select strategy.
      2. Pass 2 — verification:      check output against intent constraints.
      3. Pass 3 — self-correction:   re-reason if Pass 2 found issues.

    Designed to be used *instead of* the simple single-pass flow in
    ``CognitiveEngine`` for EXPERT and RESEARCH complexity queries.
    """

    MAX_PASSES = 3

    def __init__(self, context: CognitiveContext, llm_call: Callable):
        self.context = context
        self.llm_call = llm_call
        self.aggregator = ContextAggregator(context)
        self._pass_count = 0

    def reason(self, query: str, intent: Intent, complexity: Complexity,
               analysis: Dict[str, Any], strategy: Optional[Strategy],
               tool_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Perform deep multi-pass reasoning WITH REAL CONTEXT.

        Returns a dict with ``response``, ``passes``, ``corrections``, and
        ``final_confidence``.
        
        NOW INCLUDES: Real context integration, learned preferences, user expertise
        """
        
        # ── PHASE 1: GET REAL CONTEXT ──
        try:
            from lirox.context.real_context import RealContextBrain
            context_brain = RealContextBrain(user_id=getattr(self.context, 'user_name', 'default'))
            real_context = context_brain.get_current_context()
            context_string = real_context.to_context_string()
        except Exception as e:
            _logger.warning(f"Could not load real context: {e}")
            real_context = None
            context_string = ""
        
        prompts = PromptComposer.compose(intent, complexity, analysis, strategy, self.context)

        # Inject accumulated context
        ctx_string = self.aggregator.build_context_string()
        if ctx_string:
            prompts["system"] = prompts["system"] + "\n\nConversation context:\n" + ctx_string
        
        # ── PHASE 2: INJECT REAL CONTEXT ──
        if context_string:
            prompts["system"] = prompts["system"] + "\n\n" + context_string

        # Inject tool results
        if tool_results:
            tool_ctx = "\n\nTool Results:\n" + "\n".join(
                f"- {tr['tool']}: {'SUCCESS — ' + tr['summary'] if tr['success'] else 'FAILED — ' + tr['error']}"
                for tr in tool_results
            )
            prompts["user"] = prompts["user"] + tool_ctx

        passes: List[Dict[str, Any]] = []
        corrections: List[str] = []
        response_text = ""

        for pass_num in range(1, self.MAX_PASSES + 1):
            self._pass_count = pass_num
            response_text = str(self.llm_call(
                system_prompt=prompts["system"],
                user_message=prompts["user"],
                conversation_history=self.context.get_last_n_messages(),
            ))

            verification = VerificationEngine.verify_response(
                query, intent, response_text, analysis, tool_results)
            passes.append({"pass": pass_num, "verification": verification, "response": response_text})
            self.aggregator.enrich_context(tool_results, response_text)

            if verification["passed"] or pass_num == self.MAX_PASSES:
                break

            # Self-correction: build a correction prompt
            issues = verification["issues"]
            correction_hints = VerificationEngine.suggest_corrections(issues, response_text, intent)
            corrections.extend(correction_hints)
            correction_note = (
                "The previous response had these issues:\n"
                + "\n".join(f"- {i}" for i in issues)
                + "\n\nPlease correct them: " + "; ".join(correction_hints)
            )
            prompts["user"] = prompts["user"] + "\n\n" + correction_note

        quality = passes[-1]["verification"].get("quality_score", 1.0)
        
        # ── PHASE 3: TRIGGER BACKGROUND LEARNING ──
        try:
            from lirox.learning.background_learner import BackgroundLearner
            if real_context:
                learner = BackgroundLearner(context_brain)
                learning_result = learner.process_exchange(
                    query=query,
                    response=response_text,
                    tools_used=getattr(analysis, 'tools', []),
                    files_created=getattr(analysis, 'files', []),
                )
                _logger.info(f"Background learning: {learning_result}")
        except Exception as e:
            _logger.warning(f"Background learning failed: {e}")
        
        return {
            "response": response_text,
            "passes": len(passes),
            "corrections": corrections,
            "final_confidence": max(0.0, min(1.0, quality)),
        }


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 11: VERIFICATION LOOP — post-generation quality checks
# ─────────────────────────────────────────────────────────────────────────────

class VerificationLoop:
    """Post-generation verification loop that checks created artifacts.

    For file-creation intents, uses ``FileVerificationEngine`` to confirm
    files are on disk with adequate size.  For other intents, delegates to
    ``VerificationEngine.verify_response``.
    """

    @staticmethod
    def run(query: str, intent: Intent, response: str,
            analysis: Dict[str, Any], tool_results: List[Dict[str, Any]],
            files_created: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run the full post-generation verification loop.

        Returns a dict with ``passed``, ``issues``, ``file_checks``,
        and ``quality_score``.
        """
        result: Dict[str, Any] = {
            "passed": True,
            "issues": [],
            "file_checks": [],
            "quality_score": 1.0,
        }

        # 1. Response-level verification
        resp_check = VerificationEngine.verify_response(
            query, intent, response, analysis, tool_results)
        result["quality_score"] = resp_check.get("quality_score", 1.0)
        result["issues"].extend(resp_check.get("issues", []))
        if not resp_check.get("passed", True):
            result["passed"] = False

        # 2. File-level verification (lazy import to avoid circular deps)
        if files_created:
            try:
                from lirox.verify.file_verification import FileVerificationEngine
                for fpath in files_created:
                    check = FileVerificationEngine.verify(fpath)
                    result["file_checks"].append({"path": fpath, **check})
                    if not check["passed"]:
                        result["passed"] = False
                        result["issues"].extend(check["issues"])
            except Exception as e:
                result["issues"].append(f"File verification error: {e}")

        return result

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: THINKING DISPLAY
# ─────────────────────────────────────────────────────────────────────────────

class ThinkingDisplay:
    _MAX_STATUS_LEN = 70  # max chars shown in the inline status line

    def __init__(self, console):
        self.console = console
        self.live = None
        self.start_time = None
        self.complexity = None
        self._steps: list = []  # stored for /expand thinking
        self.elapsed: float = 0.0  # stored for /expand thinking

    def start(self, query: str, intent_name: str):
        from rich.live import Live
        from rich.text import Text
        self.start_time = time.time()
        self._steps = []
        self.elapsed = 0.0
        _, self.complexity = IntentClassifier.classify(query, CognitiveContext())
        if self.complexity == Complexity.TRIVIAL:
            return
        # Single animated line for all non-trivial queries
        self.live = Live(
            Text("  ⟳ thinking...", style="dim #a78bfa"),
            console=self.console,
            refresh_per_second=10,
            transient=True,
        )
        self.live.start()

    def add_step(self, icon: str, message: str, status: str = "running"):
        if self.live is None:
            return
        self._steps.append({"icon": icon, "message": message, "status": status})
        from rich.text import Text
        short_msg = message[:self._MAX_STATUS_LEN]
        if status == "running":
            self.live.update(Text(f"  ⟳ {icon} {short_msg}...", style="dim #a78bfa"))
        elif status == "done":
            self.live.update(Text(f"  ✓ {icon} {short_msg}", style="dim #10b981"))
        elif status == "error":
            self.live.update(Text(f"  ✗ {icon} {short_msg}", style="dim #ef4444"))
        else:
            self.live.update(Text(f"  · {icon} {short_msg}", style="dim"))
        self.live.refresh()

    def add_tool_call(self, tool_name: str, description: str):
        self.add_step("🔧", f"{tool_name}: {description}", "running")

    def add_tool_result(self, tool_name: str, res: str):
        self.add_step("📋", f"{tool_name} → {res}", "done")

    def add_planning(self, strategy_name: str):
        self.add_step("📋", f"Strategy: {strategy_name}", "done")

    def finish(self):
        self.elapsed = time.time() - self.start_time if self.start_time else 0.0
        if self.complexity == Complexity.TRIVIAL:
            return
        if self.live:
            self.live.stop()
            self.live = None
        # Print compact single-line summary (Claude-style collapsible hint)
        step_count = len(self._steps)
        cplx = self.complexity.name.lower() if self.complexity else "moderate"
        detail = f"· {cplx}"
        if step_count > 0:
            detail += f" · {step_count} step{'s' if step_count != 1 else ''}"
        detail += f" · {self.elapsed:.1f}s"
        self.console.print(
            f"  [bold #a78bfa]⟳ Thinking[/]  "
            f"[dim]{detail}  — /expand thinking for details[/dim]"
        )

class ReasoningPatterns: pass
class SessionMemory: pass
