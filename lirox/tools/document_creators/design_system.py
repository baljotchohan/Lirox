"""Design System - Real design thinking for documents.

Multi-agent debate about:
1. What does this topic need design-wise?
2. What palette/colors/structure makes sense?
3. What user preferences matter?
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

_logger = logging.getLogger("lirox.tools.design_system")


class DesignPalette(Enum):
    """Available design palettes."""
    TECHNOLOGY = "technology"      # Blues, cyans, tech look
    CULTURE = "culture"            # Warm, artistic, history
    BUSINESS = "business"          # Corporate, professional
    NATURE = "nature"              # Greens, earth tones
    CREATIVE = "creative"          # Vibrant, artistic
    MINIMAL = "minimal"            # Clean, simple, white


@dataclass
class DesignContext:
    """Context for design decision."""
    topic: str                      # e.g., "artificial intelligence history"
    user_expertise: str = "intermediate"  # beginner/intermediate/advanced
    document_type: str = "presentation"   # presentation/report/spreadsheet
    user_preferences: Dict[str, Any] = None
    

@dataclass
class DesignProposal:
    """A design proposal from an agent."""
    palette: DesignPalette
    structure: str                  # e.g., "timeline", "narrative", "analytical"
    colors: List[str]              # RGB or hex colors
    reasoning: str                 # Why this design?
    confidence: float = 0.5        # 0-1, how confident


@dataclass
class DesignDecision:
    """Final design decision."""
    palette: DesignPalette
    structure: str
    colors: List[str]
    reasoning: str
    agent_consensus: str           # Which agents agreed?
    confidence: float


class TopicAnalyzer:
    """Analyze topic to understand what design it needs."""
    
    @staticmethod
    def analyze(topic: str) -> Dict[str, Any]:
        """
        Analyze topic to determine design requirements.
        
        Returns:
            Dict with:
            - primary_domain: str (technology, business, art, history, nature)
            - sub_domains: List[str]
            - suggests_palette: DesignPalette
            - suggests_structure: str
            - reasoning: str
        """
        topic_lower = topic.lower()
        
        # Determine primary domain based on keywords
        domains = {
            "technology": ["ai", "machine learning", "code", "software", "algorithm", 
                          "neural", "data", "computation", "programming", "tech", "digital", "intelligence", "artificial"],
            "business": ["finance", "sales", "market", "profit", "revenue", "investment", 
                        "strategy", "growth", "business", "corporate", "company"],
            "culture": ["history", "art", "music", "literature", "society", "culture", 
                       "civilization", "heritage", "tradition", "social"],
            "science": ["physics", "chemistry", "biology", "research", "experiment", 
                       "scientific", "quantum", "energy"],
            "nature": ["ecology", "environment", "wildlife", "plants", "weather", "climate", 
                      "natural", "forest", "ocean"],
            "general": [],
        }
        
        # Score each domain
        scores = {}
        for domain, keywords in domains.items():
            score = sum(1 for kw in keywords if kw in topic_lower)
            scores[domain] = score
        
        # Find primary domain
        primary = max(scores, key=scores.get) if max(scores.values()) > 0 else "general"
        
        # Map domain to palette
        domain_to_palette = {
            "technology": DesignPalette.TECHNOLOGY,
            "business": DesignPalette.BUSINESS,
            "culture": DesignPalette.CULTURE,
            "science": DesignPalette.TECHNOLOGY,
            "nature": DesignPalette.NATURE,
            "general": DesignPalette.MINIMAL,
        }
        
        # Determine structure
        structure = "narrative"
        if "history" in topic_lower or "timeline" in topic_lower:
            structure = "timeline"
        elif "compare" in topic_lower or "vs" in topic_lower:
            structure = "comparative"
        elif "process" in topic_lower or "workflow" in topic_lower:
            structure = "procedural"
        elif "analysis" in topic_lower or "research" in topic_lower:
            structure = "analytical"
        
        return {
            "primary_domain": primary,
            "sub_domains": [d for d, score in scores.items() if score > 0],
            "suggests_palette": domain_to_palette[primary],
            "suggests_structure": structure,
            "reasoning": f"Topic primarily {primary}: {scores[primary]} keywords match",
            "scores": scores,
        }


class DesignAgents:
    """Multiple agents debating design choices."""
    
    class ExpertAgent:
        """Subject matter expert perspective."""
        
        @staticmethod
        def propose(context: DesignContext, analysis: Dict[str, Any]) -> DesignProposal:
            """What design does this topic need from a domain expert view?"""
            palette = analysis["suggests_palette"]
            
            if palette == DesignPalette.TECHNOLOGY:
                return DesignProposal(
                    palette=palette,
                    structure=analysis["suggests_structure"],
                    colors=["#0066CC", "#00CCFF", "#1a1a2e"],  # Tech blues
                    reasoning="Technology topics need modern, analytical look with clear structure",
                    confidence=0.9
                )
            elif palette == DesignPalette.CULTURE:
                return DesignProposal(
                    palette=palette,
                    structure=analysis["suggests_structure"],
                    colors=["#8B4513", "#D2691E", "#F4A460"],  # Warm, historic
                    reasoning="Cultural topics need warm, engaging, historical aesthetic",
                    confidence=0.85
                )
            elif palette == DesignPalette.BUSINESS:
                return DesignProposal(
                    palette=palette,
                    structure="analytical",
                    colors=["#1E3A5F", "#2E5984", "#3D7CA8"],  # Corporate blues
                    reasoning="Business topics need professional, trustworthy look",
                    confidence=0.85
                )
            elif palette == DesignPalette.NATURE:
                return DesignProposal(
                    palette=palette,
                    structure="narrative",
                    colors=["#2D5016", "#5C8D3E", "#7CB342"],  # Earth greens
                    reasoning="Nature topics need organic, flowing aesthetic",
                    confidence=0.8
                )
            else:
                return DesignProposal(
                    palette=DesignPalette.MINIMAL,
                    structure="narrative",
                    colors=["#FFFFFF", "#333333", "#666666"],
                    reasoning="General topic, minimal clean design",
                    confidence=0.6
                )
    
    class DesignerAgent:
        """Visual designer perspective."""
        
        @staticmethod
        def propose(context: DesignContext, analysis: Dict[str, Any]) -> DesignProposal:
            """What design works visually for this content?"""
            # Designer agrees with expert on palette but focuses on visual flow
            palette = analysis["suggests_palette"]
            structure = analysis["suggests_structure"]
            
            if structure == "timeline":
                reasoning = "Timeline structure with visual progression"
                if palette == DesignPalette.TECHNOLOGY:
                    colors = ["#0099FF", "#00D4FF", "#00FFFF"]  # Tech gradient
                else:
                    colors = ["#D2B48C", "#CD853F", "#8B4513"]  # Historical gradient
            elif structure == "comparative":
                reasoning = "Split-screen or side-by-side comparison for visual clarity"
                colors = ["#FF6B6B", "#4ECDC4", "#95E1D3"]  # Contrast colors
            elif structure == "analytical":
                reasoning = "Clean, data-focused layout with emphasis on numbers/charts"
                colors = ["#1E88E5", "#43A047", "#FB8C00"]  # Data visualization colors
            else:
                reasoning = "Narrative flow with emotional visual journey"
                colors = ["#6366F1", "#8B5CF6", "#EC4899"]  # Engaging gradient
            
            return DesignProposal(
                palette=palette,
                structure=structure,
                colors=colors,
                reasoning=reasoning,
                confidence=0.75
            )
    
    class UserAdvocateAgent:
        """User preference perspective."""
        
        @staticmethod
        def propose(context: DesignContext, analysis: Dict[str, Any]) -> DesignProposal:
            """What design does the user actually prefer?"""
            palette = analysis["suggests_palette"]
            prefs = context.user_preferences or {}
            
            # Adjust based on user expertise
            if context.user_expertise == "beginner":
                reasoning = "User is beginner, needs clear, simple, step-by-step design"
                structure = "procedural"
            elif context.user_expertise == "advanced":
                reasoning = "User is advanced, can handle complex, detailed design"
                structure = "analytical"
            else:
                structure = analysis["suggests_structure"]
                reasoning = "User is intermediate, balanced design"
            
            return DesignProposal(
                palette=palette,
                structure=structure,
                colors=["#6366F1", "#8B5CF6", "#EC4899"],  # Defaults
                reasoning=reasoning,
                confidence=0.7
            )


class DesignSynthesizer:
    """Synthesize multiple design proposals into one decision."""
    
    @staticmethod
    def synthesize(proposals: Dict[str, DesignProposal]) -> DesignDecision:
        """Merge proposals from all agents."""
        
        # Find consensus palette (majority vote)
        palettes = [p.palette for p in proposals.values()]
        palette_votes = {}
        for p in palettes:
            palette_votes[p] = palette_votes.get(p, 0) + 1
        palette = max(palette_votes, key=palette_votes.get)
        
        # Find consensus structure
        structures = [p.structure for p in proposals.values()]
        structure_votes = {}
        for s in structures:
            structure_votes[s] = structure_votes.get(s, 0) + 1
        structure = max(structure_votes, key=structure_votes.get)
        
        # Merge colors (take from highest confidence proposal)
        best_proposal = max(proposals.values(), key=lambda p: p.confidence)
        colors = best_proposal.colors
        
        # Calculate confidence
        avg_confidence = sum(p.confidence for p in proposals.values()) / len(proposals)
        
        # Consensus agents
        agent_list = list(proposals.keys())
        
        return DesignDecision(
            palette=palette,
            structure=structure,
            colors=colors,
            reasoning=f"Consensus from {', '.join(agent_list)}",
            agent_consensus=f"{len(proposals)} agents agreed on {palette.value}",
            confidence=avg_confidence
        )


class DesignSystem:
    """Complete design system that makes real design decisions."""
    
    @staticmethod
    def decide_design(topic: str, doc_type: str = "presentation",
                      user_expertise: str = "intermediate",
                      user_preferences: Dict[str, Any] = None) -> DesignDecision:
        """
        Make a design decision using multi-agent debate.
        
        Args:
            topic: Document topic (e.g., "history of artificial intelligence")
            doc_type: presentation/report/spreadsheet
            user_expertise: beginner/intermediate/advanced
            user_preferences: User's style preferences
        
        Returns:
            DesignDecision with chosen palette and structure
        """
        # Step 1: Understand the topic
        analysis = TopicAnalyzer.analyze(topic)
        _logger.info(f"Topic analysis: {analysis['primary_domain']} → {analysis['suggests_palette'].value}")
        
        # Step 2: Create context
        context = DesignContext(
            topic=topic,
            user_expertise=user_expertise,
            document_type=doc_type,
            user_preferences=user_preferences
        )
        
        # Step 3: Each agent proposes design
        proposals = {
            "expert": DesignAgents.ExpertAgent.propose(context, analysis),
            "designer": DesignAgents.DesignerAgent.propose(context, analysis),
            "user_advocate": DesignAgents.UserAdvocateAgent.propose(context, analysis),
        }
        
        _logger.info(f"Design proposals: {list(proposals.keys())}")
        for agent_name, proposal in proposals.items():
            _logger.info(f"  {agent_name}: {proposal.palette.value} ({proposal.confidence:.0%})")
        
        # Step 4: Synthesize decision
        decision = DesignSynthesizer.synthesize(proposals)
        _logger.info(f"Final design: {decision.palette.value} + {decision.structure} "
                    f"({decision.confidence:.0%} confidence)")
        
        return decision


def get_palette_name_from_design(decision: DesignDecision) -> str:
    """Convert DesignDecision to palette name for document creators."""
    mapping = {
        DesignPalette.TECHNOLOGY: "technology",
        DesignPalette.CULTURE: "culture",
        DesignPalette.BUSINESS: "business",
        DesignPalette.NATURE: "nature",
        DesignPalette.CREATIVE: "creative",
        DesignPalette.MINIMAL: "minimal",
    }
    return mapping[decision.palette]
