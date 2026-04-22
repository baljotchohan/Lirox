"""Tests for design system."""

import pytest
from lirox.tools.document_creators.design_system import (
    TopicAnalyzer, DesignSystem, DesignPalette, get_palette_name_from_design
)


class TestTopicAnalyzer:
    """Test topic analysis."""
    
    def test_analyze_ai_history(self):
        """AI history should be detected as technology domain."""
        analysis = TopicAnalyzer.analyze("history of artificial intelligence")
        assert analysis["primary_domain"] == "technology"
        assert analysis["suggests_palette"] == DesignPalette.TECHNOLOGY
    
    def test_analyze_cultural_history(self):
        """Cultural history should be detected as culture domain."""
        analysis = TopicAnalyzer.analyze("history of ancient rome and culture")
        assert analysis["primary_domain"] == "culture"
        assert analysis["suggests_palette"] == DesignPalette.CULTURE
    
    def test_analyze_business(self):
        """Business topic should be detected."""
        analysis = TopicAnalyzer.analyze("company growth and market strategy")
        assert analysis["primary_domain"] == "business"
    
    def test_analyze_nature(self):
        """Nature topic should be detected."""
        analysis = TopicAnalyzer.analyze("ecology and wildlife conservation")
        assert analysis["primary_domain"] == "nature"


class TestDesignSystem:
    """Test complete design system."""
    
    def test_design_ai_topic(self):
        """Design for AI topic should choose technology palette."""
        decision = DesignSystem.decide_design("machine learning and neural networks")
        assert decision.palette == DesignPalette.TECHNOLOGY
        palette_name = get_palette_name_from_design(decision)
        assert palette_name == "technology"
    
    def test_design_has_reasoning(self):
        """Design decision should have reasoning."""
        decision = DesignSystem.decide_design("ancient civilizations")
        assert decision.reasoning is not None
        assert len(decision.reasoning) > 0
    
    def test_design_has_colors(self):
        """Design should include colors."""
        decision = DesignSystem.decide_design("data science project")
        assert decision.colors is not None
        assert len(decision.colors) > 0
    
    def test_design_confidence(self):
        """Design should have confidence score."""
        decision = DesignSystem.decide_design("some topic")
        assert 0 <= decision.confidence <= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
