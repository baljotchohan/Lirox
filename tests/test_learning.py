"""Tests for lirox.learning — fact extraction and learning manager.

LLM calls are mocked so tests run fully offline.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch

from lirox.learning.extractor import (
    FactExtractor,
    ExtractedKnowledge,
    _parse_json,
    _str_list,
    _str_dict_list,
    _project_list,
)
from lirox.learning.manager import LearningManager


# ── JSON helpers ─────────────────────────────────────────────────────────────


class TestParseJson:
    def test_valid_json_object(self):
        parsed, err = _parse_json('{"key": "value"}')
        assert err == ""
        assert parsed == {"key": "value"}

    def test_strips_markdown_fence(self):
        text = '```json\n{"a": 1}\n```'
        parsed, err = _parse_json(text)
        assert err == ""
        assert parsed["a"] == 1

    def test_no_json_returns_error(self):
        _, err = _parse_json("no json here")
        assert err

    def test_extracts_nested_object(self):
        text = 'some text {"name": "Alice"} more text'
        parsed, err = _parse_json(text)
        assert err == ""
        assert parsed["name"] == "Alice"


class TestStrList:
    def test_normal_list(self):
        assert _str_list(["a", "b"]) == ["a", "b"]

    def test_non_list_returns_empty(self):
        assert _str_list("not a list") == []

    def test_filters_empty_strings(self):
        assert _str_list(["a", "", "  "]) == ["a"]


class TestStrDictList:
    def test_normal_dict(self):
        result = _str_dict_list({"coding": ["Python", "Rust"]})
        assert result == {"coding": ["Python", "Rust"]}

    def test_non_dict_returns_empty(self):
        assert _str_dict_list("string") == {}


class TestProjectList:
    def test_valid_projects(self):
        data = [{"name": "MyApp", "description": "A cool app"}]
        result = _project_list(data)
        assert len(result) == 1
        assert result[0]["name"] == "MyApp"

    def test_entry_without_name_skipped(self):
        data = [{"description": "no name here"}]
        assert _project_list(data) == []


# ── FactExtractor ─────────────────────────────────────────────────────────────


class TestFactExtractor:
    _MOCK_RESPONSE = """{
        "facts": ["User codes in Python", "User works remotely"],
        "topics": ["Python", "remote work"],
        "preferences": {"editor": ["VSCode"]},
        "dislikes": ["meetings"],
        "projects": [{"name": "TodoApp", "description": "A todo list app"}]
    }"""

    def test_extract_returns_knowledge(self):
        extractor = FactExtractor()
        with patch("lirox.utils.llm.generate_response", return_value=self._MOCK_RESPONSE):
            result = extractor.extract("User: I code in Python\nAssistant: Great!")
        assert isinstance(result, ExtractedKnowledge)
        assert "User codes in Python" in result.facts
        assert "Python" in result.topics
        assert "VSCode" in result.preferences.get("editor", [])
        assert "meetings" in result.dislikes
        assert result.projects[0]["name"] == "TodoApp"

    def test_empty_conversation_returns_error(self):
        extractor = FactExtractor()
        result = extractor.extract("   ")
        assert result.error

    def test_llm_error_handled(self):
        extractor = FactExtractor()
        with patch("lirox.utils.llm.generate_response", side_effect=Exception("network error")):
            result = extractor.extract("some text")
        assert result.error

    def test_invalid_json_returns_error(self):
        extractor = FactExtractor()
        with patch("lirox.utils.llm.generate_response", return_value="not json at all"):
            result = extractor.extract("some text")
        assert result.error

    def test_is_empty_property(self):
        result = ExtractedKnowledge()
        assert result.is_empty

    def test_total_items_counting(self):
        result = ExtractedKnowledge(
            facts=["f1", "f2"],
            topics=["t1"],
            preferences={"code": ["Python"]},
            projects=[{"name": "A", "description": ""}],
        )
        # 2 facts + 1 topic + 1 pref + 1 project = 5
        assert result.total_items == 5


# ── LearningManager ──────────────────────────────────────────────────────────


class TestLearningManager:
    """LearningManager tests use tmp_path for SQLite and a mocked LearningsStore."""

    def test_recall_facts_returns_list(self, tmp_path):
        mgr = LearningManager(use_db=False)
        # Inject fake facts into the learnings store
        mgr.learnings.data["user_facts"] = [
            {"fact": "fact A", "confidence": 1.0},
            {"fact": "fact B", "confidence": 0.9},
        ]
        facts = mgr.recall_facts()
        assert "fact A" in facts
        assert "fact B" in facts

    def test_stats_returns_dict(self, tmp_path):
        mgr = LearningManager(use_db=False)
        stats = mgr.stats()
        assert "facts" in stats
        assert "topics" in stats
        assert "projects" in stats

    def test_search_knowledge_finds_match(self, tmp_path):
        mgr = LearningManager(use_db=False)
        mgr.learnings.data["user_facts"] = [
            {"fact": "User loves Rust programming"},
        ]
        results = mgr.search_knowledge("Rust")
        assert any("Rust" in r for r in results)

    def test_search_knowledge_no_match(self, tmp_path):
        mgr = LearningManager(use_db=False)
        mgr.learnings.data["user_facts"] = [
            {"fact": "User loves Python"},
        ]
        results = mgr.search_knowledge("Cobol")
        assert results == []

    def test_train_from_text_updates_facts(self, tmp_path):
        mgr = LearningManager(use_db=False)
        _MOCK = '{"facts": ["User is a backend dev"], "topics": ["Go"], "preferences": {}, "dislikes": [], "projects": []}'
        with patch("lirox.utils.llm.generate_response", return_value=_MOCK):
            stats = mgr.train_from_text("User: I write Go code daily")
        assert stats["facts_added"] >= 1

    def test_recall_projects_returns_list(self, tmp_path):
        mgr = LearningManager(use_db=False)
        mgr.learnings.data["projects"] = [{"name": "Proj1", "description": "desc"}]
        projects = mgr.recall_projects()
        assert isinstance(projects, list)
        assert projects[0]["name"] == "Proj1"

    def test_learning_manager_with_db(self, tmp_path):
        """LearningManager integrates with DatabaseStore when use_db=True."""
        import os
        os.environ.setdefault("LIROX_DATA_DIR", str(tmp_path))
        # Override DATA_DIR for the database
        import lirox.database.store as _store_mod
        original_init = _store_mod.DatabaseStore.__init__

        def patched_init(self, db_path=None):
            original_init(self, str(tmp_path / "learning_test.db"))

        with patch.object(_store_mod.DatabaseStore, "__init__", patched_init):
            mgr = LearningManager(use_db=True)
            stats = mgr.stats()
        assert "facts" in stats
