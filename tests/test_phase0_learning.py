"""Unit tests for Phase 0 - Real Context + Auto Learning."""

import pytest
import os
import json
import tempfile
from pathlib import Path

from lirox.context.real_context import (
    RealContextBrain, TimeContext, LearnedFacts, extract_topics
)
from lirox.learning.background_learner import (
    BackgroundLearner, FactExtractor, PatternDetector, PreferenceInferrer
)


class TestRealContext:
    """Test real context system."""
    
    def test_time_context_creation(self):
        """TimeContext should be created correctly."""
        tc = TimeContext.now()
        assert tc.timezone is not None
        assert tc.day_of_week in ["Monday", "Tuesday", "Wednesday", "Thursday", 
                                   "Friday", "Saturday", "Sunday"]
        assert tc.time_of_day in ["morning", "afternoon", "evening", "night"]
    
    def test_context_brain_creation(self):
        """RealContextBrain should create and manage context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            brain = RealContextBrain("test_user", tmpdir)
            assert brain.user_id == "test_user"
            assert brain.data.user_id == "test_user"
    
    def test_context_persistence(self):
        """Context should persist to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create and save
            brain1 = RealContextBrain("test_user", tmpdir)
            brain1.update_learned_facts({"user_name": "Alice"})
            brain1.save()
            
            # Load again
            brain2 = RealContextBrain("test_user", tmpdir)
            assert brain2.data.learned_facts.user_name == "Alice"
    
    def test_exchange_recording(self):
        """Should record user-agent exchanges."""
        with tempfile.TemporaryDirectory() as tmpdir:
            brain = RealContextBrain("test_user", tmpdir)
            brain.add_exchange("hello", "Hi there!", tools=["chat"])
            
            assert len(brain.data.conversation_context.messages) == 1
            assert brain.data.conversation_context.messages[0]["user"] == "hello"


class TestBackgroundLearning:
    """Test automatic learning system."""
    
    def test_fact_extraction(self):
        """FactExtractor should extract facts from conversation."""
        query = "I'm a software developer and I want to learn machine learning"
        response = "Great! Here's how to get started with ML..."
        
        facts = FactExtractor.extract(query, response)
        assert len(facts) > 0
        assert any("developer" in str(f).lower() for f in facts)
    
    def test_pattern_detection(self):
        """PatternDetector should find recurring patterns."""
        history = [
            {"user": "create a python script", "agent": "..."},
            {"user": "create another python file", "agent": "..."},
            {"user": "python question", "agent": "..."},
        ]
        
        patterns = PatternDetector.detect(history, "python help", "...")
        assert len(patterns) > 0
        assert any("python" in str(p).lower() for p in patterns)
    
    def test_preference_inference(self):
        """PreferenceInferrer should infer user preferences."""
        query = "Please explain in detail how machine learning works"
        response = "Machine learning is..."
        tools = ["documentation_generator"]
        
        prefs = PreferenceInferrer.infer(query, response, tools)
        assert len(prefs) > 0
    
    def test_background_learner_processing(self):
        """BackgroundLearner should process exchanges completely."""
        with tempfile.TemporaryDirectory() as tmpdir:
            brain = RealContextBrain("test_user", tmpdir)
            learner = BackgroundLearner(brain, tmpdir)
            
            result = learner.process_exchange(
                query="I'm learning Python and want to create PDFs",
                response="Here's how to create PDFs in Python...",
                tools_used=["code_generator"],
                files_created=["example.pdf"]
            )
            
            assert result["learned"]["facts"] >= 0
            assert result["learned"]["patterns"] >= 0
    
    def test_topic_extraction(self):
        """Should extract topics from queries."""
        query = "How do I do machine learning in Python?"
        topics = extract_topics(query)
        assert "python" in topics
        assert "machine learning" in topics


class TestIntegration:
    """Integration tests for Phase 0."""
    
    def test_full_learning_cycle(self):
        """Full cycle: create brain → learn → update → save → load."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Step 1: Create brain and learner
            brain = RealContextBrain("integration_test", tmpdir)
            learner = BackgroundLearner(brain, tmpdir)
            
            # Step 2: Simulate exchanges
            brain.add_exchange(
                "I'm a beginner learning Python",
                "Great! Let's start with basics",
                tools=["tutorial"]
            )
            
            # Step 3: Process learning
            result = learner.process_exchange(
                query="create a python script for data processing",
                response="Here's a Python script...",
                tools_used=["code_generator"],
                files_created=["script.py"]
            )
            
            # Step 4: Verify learning happened
            assert result["learned"]["facts"] > 0 or result["learned"]["patterns"] > 0
            
            # Step 5: Save and reload
            brain.save()
            brain2 = RealContextBrain("integration_test", tmpdir)
            
            # Step 6: Verify context persisted
            assert len(brain2.data.conversation_context.messages) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
