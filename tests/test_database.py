"""Tests for lirox.database — SQLite persistence layer.

These tests use an in-memory or temp-file SQLite database so they are
fully isolated and do not touch the real Lirox data directory.
"""
from __future__ import annotations

import os
import pytest

from lirox.database.store import DatabaseStore
from lirox.database.models import (
    AuditEvent,
    Conversation,
    Fact,
    Project,
    UsageStat,
    UserProfile,
)


# ── Shared fixture ─────────────────────────────────────────────────────────


@pytest.fixture()
def db(tmp_path):
    """Return a fresh DatabaseStore backed by a temp file."""
    return DatabaseStore(str(tmp_path / "test.db"))


# ── User Profile ────────────────────────────────────────────────────────────


class TestUserProfile:
    def test_save_and_load(self, db):
        profile = UserProfile(
            user_id="alice",
            name="Alice",
            agent_name="Lex",
            profession="Engineer",
        )
        db.save_profile(profile)
        loaded = db.load_profile("alice")
        assert loaded is not None
        assert loaded.name == "Alice"
        assert loaded.agent_name == "Lex"

    def test_missing_profile_returns_none(self, db):
        assert db.load_profile("nonexistent") is None

    def test_update_existing_profile(self, db):
        profile = UserProfile(user_id="bob", name="Bob")
        db.save_profile(profile)
        profile.name = "Robert"
        db.save_profile(profile)
        loaded = db.load_profile("bob")
        assert loaded.name == "Robert"

    def test_goals_serialised(self, db):
        profile = UserProfile(user_id="carol", goals=["goal1", "goal2"])
        db.save_profile(profile)
        loaded = db.load_profile("carol")
        assert loaded.goals == ["goal1", "goal2"]

    def test_preferences_serialised(self, db):
        profile = UserProfile(user_id="dave", preferences={"theme": "dark"})
        db.save_profile(profile)
        loaded = db.load_profile("dave")
        assert loaded.preferences == {"theme": "dark"}


# ── Conversations ───────────────────────────────────────────────────────────


class TestConversations:
    def test_add_and_retrieve(self, db):
        msg = Conversation(session_id="s1", role="user", content="Hello!")
        db.add_conversation(msg)
        convs = db.get_conversations(session_id="s1")
        assert len(convs) == 1
        assert convs[0].content == "Hello!"

    def test_conversation_count(self, db):
        for i in range(5):
            db.add_conversation(Conversation(session_id="s2", content=f"msg {i}"))
        assert db.count_conversations() == 5

    def test_filter_by_session(self, db):
        db.add_conversation(Conversation(session_id="a", content="session A"))
        db.add_conversation(Conversation(session_id="b", content="session B"))
        a = db.get_conversations(session_id="a")
        assert len(a) == 1
        assert a[0].content == "session A"

    def test_limit_respected(self, db):
        for i in range(10):
            db.add_conversation(Conversation(session_id="lim", content=f"m{i}"))
        result = db.get_conversations(session_id="lim", limit=3)
        assert len(result) == 3

    def test_search_conversations(self, db):
        db.add_conversation(Conversation(session_id="s", content="I love Python"))
        db.add_conversation(Conversation(session_id="s", content="JavaScript is okay"))
        results = db.search_conversations("Python")
        assert any("Python" in c.content for c in results)


# ── Facts ───────────────────────────────────────────────────────────────────


class TestFacts:
    def test_upsert_new_fact(self, db):
        fact = Fact(content="User likes dark mode")
        db.upsert_fact(fact)
        facts = db.get_facts()
        assert len(facts) == 1
        assert facts[0].content == "User likes dark mode"

    def test_duplicate_increments_times_seen(self, db):
        fact = Fact(content="User is a developer")
        db.upsert_fact(fact)
        db.upsert_fact(fact)
        facts = db.get_facts()
        assert facts[0].times_seen == 2

    def test_count_facts(self, db):
        for i in range(3):
            db.upsert_fact(Fact(content=f"fact {i}"))
        assert db.count_facts() == 3

    def test_filter_by_category(self, db):
        db.upsert_fact(Fact(content="fact A", category="code"))
        db.upsert_fact(Fact(content="fact B", category="life"))
        code_facts = db.get_facts(category="code")
        assert len(code_facts) == 1
        assert code_facts[0].content == "fact A"

    def test_search_facts(self, db):
        db.upsert_fact(Fact(content="User prefers Python over Java"))
        db.upsert_fact(Fact(content="User dislikes meetings"))
        results = db.search_facts("Python")
        assert any("Python" in f.content for f in results)


# ── Projects ─────────────────────────────────────────────────────────────────


class TestProjects:
    def test_upsert_and_retrieve(self, db):
        proj = Project(name="MyApp", description="A test project", language="python")
        db.upsert_project(proj)
        projects = db.get_projects()
        assert len(projects) == 1
        assert projects[0].name == "MyApp"

    def test_update_project(self, db):
        proj = Project(name="App2", description="old")
        db.upsert_project(proj)
        proj.description = "new"
        db.upsert_project(proj)
        projects = db.get_projects()
        assert projects[0].description == "new"

    def test_filter_by_status(self, db):
        db.upsert_project(Project(name="Active", status="active"))
        db.upsert_project(Project(name="Done", status="done"))
        active = db.get_projects(status="active")
        assert len(active) == 1
        assert active[0].name == "Active"

    def test_metadata_serialised(self, db):
        db.upsert_project(Project(name="Meta", metadata={"lang": "rust", "stars": 42}))
        projects = db.get_projects()
        assert projects[0].metadata == {"lang": "rust", "stars": 42}


# ── Usage Statistics ──────────────────────────────────────────────────────────


class TestUsageStats:
    def test_record_and_summarise(self, db):
        stat = UsageStat(provider="groq", model="llama3", total_tokens=100, cost_usd=0.001)
        db.record_usage(stat)
        summary = db.get_usage_summary()
        assert "groq" in summary
        assert summary["groq"]["calls"] == 1
        assert summary["groq"]["total_tokens"] == 100

    def test_aggregate_multiple_calls(self, db):
        for _ in range(3):
            db.record_usage(UsageStat(provider="openai", total_tokens=50))
        summary = db.get_usage_summary()
        assert summary["openai"]["calls"] == 3
        assert summary["openai"]["total_tokens"] == 150


# ── Audit Trail ──────────────────────────────────────────────────────────────


class TestAuditTrail:
    def test_record_and_retrieve(self, db):
        event = AuditEvent(action="file_write", target="/tmp/out.pdf", status="ok")
        db.audit(event)
        trail = db.get_audit_trail()
        assert len(trail) == 1
        assert trail[0].action == "file_write"

    def test_limit_respected(self, db):
        for i in range(20):
            db.audit(AuditEvent(action="llm_call", target=f"call_{i}"))
        trail = db.get_audit_trail(limit=5)
        assert len(trail) == 5


# ── Database stats & backup ─────────────────────────────────────────────────


class TestDatabaseStats:
    def test_stats_returns_dict(self, db):
        stats = db.stats()
        assert "conversations" in stats
        assert "facts" in stats
        assert "projects" in stats

    def test_backup(self, db, tmp_path):
        db.add_conversation(Conversation(content="backup test"))
        dest = str(tmp_path / "backup.db")
        assert db.backup(dest)
        assert os.path.exists(dest)
        assert os.path.getsize(dest) > 0
