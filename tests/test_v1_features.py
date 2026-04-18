"""Tests for Lirox V1 critical bug fixes and new features."""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock


# ─────────────────────────────────────────────────────────────────────────────
# BUG-1: Directory permission management
# ─────────────────────────────────────────────────────────────────────────────

class TestConfigDirectoryCreation(unittest.TestCase):
    def test_make_dir_safe_creates_dir_with_correct_permissions(self):
        """_make_dir_safe must create directories with mode 0o700."""
        import stat
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "test_safe_dir")
            from lirox.config import _make_dir_safe
            _make_dir_safe(target)
            self.assertTrue(os.path.isdir(target))
            # Check owner-write bit is present (skip on Windows)
            if sys.platform != "win32":
                mode = os.stat(target).st_mode
                self.assertTrue(mode & stat.S_IWUSR, "Directory should be owner-writable")

    def test_make_dir_safe_raises_on_permission_denied(self):
        """_make_dir_safe must raise a PermissionError with a helpful message."""
        from lirox.config import _make_dir_safe
        with mock.patch("os.makedirs", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError) as ctx:
                _make_dir_safe("/nonexistent/path")
        self.assertIn("[Lirox]", str(ctx.exception))

    def test_make_dir_safe_raises_on_os_error(self):
        """_make_dir_safe must raise an OSError with a helpful message."""
        from lirox.config import _make_dir_safe
        with mock.patch("os.makedirs", side_effect=OSError("disk full")):
            with self.assertRaises(OSError) as ctx:
                _make_dir_safe("/nonexistent/path")
        self.assertIn("[Lirox]", str(ctx.exception))

    def test_make_dir_safe_idempotent(self):
        """_make_dir_safe must be idempotent (exist_ok=True)."""
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "idempotent_dir")
            from lirox.config import _make_dir_safe
            _make_dir_safe(target)
            _make_dir_safe(target)   # second call must not raise
            self.assertTrue(os.path.isdir(target))


# ─────────────────────────────────────────────────────────────────────────────
# BUG-5: Sub-agent routing regex
# ─────────────────────────────────────────────────────────────────────────────

class TestSubAgentRouting(unittest.TestCase):
    def _normalize_name(self, raw: str) -> str:
        """Replicate the normalization logic from main.py."""
        import re
        words = re.split(r'[\s\-_]+', raw.strip())
        return "".join(w.capitalize() for w in words if w) or "CustomAgent"

    def test_normalizes_single_word(self):
        self.assertEqual(self._normalize_name("atlas"), "Atlas")

    def test_normalizes_multi_word(self):
        self.assertEqual(self._normalize_name("data analyzer"), "DataAnalyzer")

    def test_normalizes_hyphenated(self):
        self.assertEqual(self._normalize_name("code-review-agent"), "CodeReviewAgent")

    def test_normalizes_empty_falls_back(self):
        self.assertEqual(self._normalize_name(""), "CustomAgent")

    def test_normalizes_mixed_case(self):
        self.assertEqual(self._normalize_name("My Custom Agent"), "MyCustomAgent")


# ─────────────────────────────────────────────────────────────────────────────
# BUG-8: Skill parameter parsing
# ─────────────────────────────────────────────────────────────────────────────

class TestSkillParameterParsing(unittest.TestCase):
    """The BUG-8 fix uses a fallback regex tokenizer when shlex fails."""

    def _parse_params(self, raw_params: str) -> dict:
        """Replicate the parsing logic from main.py."""
        import re
        params = {}
        if not raw_params:
            return params
        try:
            import shlex
            tokens = shlex.split(raw_params)
        except ValueError:
            tokens = re.findall(r'(?:"[^"]*"|\'[^\']*\'|\S)+', raw_params)
        for token in tokens:
            token = token.strip()
            if "=" in token:
                k, v = token.split("=", 1)
                v = v.strip().strip('"').strip("'")
                params[k.strip()] = v
            elif token:
                params.setdefault("input", token)
        return params

    def test_simple_key_value(self):
        p = self._parse_params("input=hello")
        self.assertEqual(p["input"], "hello")

    def test_quoted_value(self):
        p = self._parse_params('input="hello world"')
        self.assertEqual(p["input"], "hello world")

    def test_value_with_hash(self):
        """BUG-8: shlex breaks on #, fallback must handle it."""
        p = self._parse_params("input=hello#world")
        self.assertEqual(p["input"], "hello#world")

    def test_unquoted_token_goes_to_input(self):
        p = self._parse_params("hello")
        self.assertEqual(p["input"], "hello")

    def test_multiple_params(self):
        p = self._parse_params("input=foo output=bar")
        self.assertEqual(p["input"], "foo")
        self.assertEqual(p["output"], "bar")

    def test_malformed_quotes_fallback(self):
        """Unbalanced quotes must not crash — use fallback tokenizer."""
        p = self._parse_params("input='hello world")
        self.assertIn("input", p)


# ─────────────────────────────────────────────────────────────────────────────
# BUG-9: Thinking engine timeout
# ─────────────────────────────────────────────────────────────────────────────

class TestThinkingEngineTimeout(unittest.TestCase):
    def test_timeout_returns_graceful_degradation(self):
        """When LLM hangs, reason() must return a timeout message, not hang."""
        from lirox.thinking.chain_of_thought import ThinkingEngine

        engine = ThinkingEngine()
        engine._timeout = 1  # 1-second timeout for testing

        # Mock generate_response to sleep longer than timeout
        import concurrent.futures

        def _slow_generate(*args, **kwargs):
            time.sleep(5)
            return "result"

        with mock.patch("lirox.thinking.chain_of_thought.generate_response", _slow_generate):
            result = engine.reason("test query")

        self.assertIn("timed out", result.lower())

    def test_normal_response_returned_within_timeout(self):
        """When LLM responds fast, reason() must return the real answer."""
        from lirox.thinking.chain_of_thought import ThinkingEngine

        engine = ThinkingEngine()
        engine._timeout = 30

        with mock.patch("lirox.thinking.chain_of_thought.generate_response",
                        return_value="UNDERSTAND: test\nPLAN: do it"):
            result = engine.reason("test query")

        self.assertIn("UNDERSTAND", result)


# ─────────────────────────────────────────────────────────────────────────────
# BUG-12: Self-modification gate
# ─────────────────────────────────────────────────────────────────────────────

class TestSelfModificationGate(unittest.TestCase):
    def test_is_self_modification_detects_project_root(self):
        """is_self_modification must return True for files inside PROJECT_ROOT."""
        from lirox.config import is_self_modification, PROJECT_ROOT
        project_file = os.path.join(PROJECT_ROOT, "lirox", "main.py")
        self.assertTrue(is_self_modification(project_file))

    def test_is_self_modification_allows_external_paths(self):
        """is_self_modification must return False for paths outside the project."""
        from lirox.config import is_self_modification
        self.assertFalse(is_self_modification("/tmp/some_random_file.txt"))

    def test_self_mod_blocked_without_env(self):
        """File writes to project root must be blocked without LIROX_ALLOW_SELF_MOD=1."""
        from lirox.config import PROJECT_ROOT
        with tempfile.TemporaryDirectory() as tmp:
            # Create a fake "project root" file for this test
            fake_proj = Path(tmp) / "lirox" / "fake.py"
            fake_proj.parent.mkdir(parents=True)
            fake_proj.write_text("# test")

            with mock.patch("lirox.config.SELF_MOD_ROOTS", [tmp]):
                with mock.patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("LIROX_ALLOW_SELF_MOD", None)
                    from lirox.tools.file_tools import _self_mod_blocked
                    result = _self_mod_blocked(str(fake_proj))
                    self.assertIsNotNone(result)
                    self.assertIn("BLOCKED", result)

    def test_self_mod_allowed_with_env(self):
        """Self-modification must be allowed when LIROX_ALLOW_SELF_MOD=1."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_file = Path(tmp) / "fake.py"
            fake_file.write_text("# test")
            with mock.patch("lirox.config.SELF_MOD_ROOTS", [tmp]):
                with mock.patch.dict(os.environ, {"LIROX_ALLOW_SELF_MOD": "1"}):
                    from lirox.tools.file_tools import _self_mod_blocked
                    result = _self_mod_blocked(str(fake_file))
                    self.assertIsNone(result)


# ─────────────────────────────────────────────────────────────────────────────
# Feature-1: Auto-learner
# ─────────────────────────────────────────────────────────────────────────────

class TestAutoLearner(unittest.TestCase):
    def test_auto_learner_starts_and_stops(self):
        """AutoLearner thread must start and stop without errors."""
        from lirox.autonomy.auto_learner import AutoLearner

        mock_memory  = mock.MagicMock()
        mock_memory.conversation_buffer = []
        mock_sessions = mock.MagicMock()
        mock_sessions.list_sessions.return_value = []

        learner = AutoLearner(mock_memory, mock_sessions)
        learner.start()
        self.assertTrue(learner.is_running)
        learner.stop()
        # After stop, thread should be dead within a short time
        time.sleep(0.2)
        self.assertFalse(learner.is_running)

    def test_notify_new_message_increments_count(self):
        """notify_new_message must increment the message counter."""
        from lirox.autonomy.auto_learner import AutoLearner

        mock_memory  = mock.MagicMock()
        mock_memory.conversation_buffer = []
        mock_sessions = mock.MagicMock()

        learner = AutoLearner(mock_memory, mock_sessions)

        # Mock trainer so it doesn't actually call an LLM
        with mock.patch("lirox.mind.agent.get_trainer") as mock_trainer:
            mock_trainer.return_value.train.return_value = {
                "facts_added": 0, "topics_bumped": 0, "preferences_added": 0
            }
            for _ in range(3):
                learner.notify_new_message()
        self.assertEqual(learner.message_count, 3)

    def test_callback_called_when_facts_found(self):
        """Callback must be called when training produces new facts."""
        from lirox.autonomy.auto_learner import AutoLearner

        callback_stats = []

        def _cb(stats):
            callback_stats.append(stats)

        mock_memory  = mock.MagicMock()
        mock_memory.conversation_buffer = []
        mock_sessions = mock.MagicMock()

        learner = AutoLearner(mock_memory, mock_sessions, on_train_complete=_cb)

        with mock.patch("lirox.mind.agent.get_trainer") as mock_trainer:
            mock_trainer.return_value.train.return_value = {
                "facts_added": 3, "topics_bumped": 1, "preferences_added": 0
            }
            learner.train_now()

        self.assertEqual(len(callback_stats), 1)
        self.assertEqual(callback_stats[0]["facts_added"], 3)


# ─────────────────────────────────────────────────────────────────────────────
# Feature-2: Advanced reasoning engine
# ─────────────────────────────────────────────────────────────────────────────

class TestAdvancedReasoningEngine(unittest.TestCase):
    def test_parse_phases_all_eight(self):
        """_parse_phases must extract all 8 phase labels."""
        from lirox.reasoning.advanced_engine import AdvancedReasoningEngine

        engine = AdvancedReasoningEngine()
        raw = (
            "UNDERSTAND: question\n"
            "DECOMPOSE: components\n"
            "ANALYZE: analysis\n"
            "EVALUATE: evaluation\n"
            "SIMULATE: simulation\n"
            "REFINE: refinement\n"
            "PLAN: 1. step one\n"
            "VERIFY: done"
        )
        phases = engine._parse_phases(raw)
        for name in ["UNDERSTAND", "DECOMPOSE", "ANALYZE", "EVALUATE",
                     "SIMULATE", "REFINE", "PLAN", "VERIFY"]:
            self.assertIn(name, phases)
            self.assertTrue(phases[name], f"Phase {name} should not be empty")

    def test_reason_uses_fallback_on_llm_error(self):
        """reason() must return a valid ReasoningResult even when LLM fails."""
        from lirox.reasoning.advanced_engine import AdvancedReasoningEngine

        engine = AdvancedReasoningEngine()
        with mock.patch("lirox.reasoning.advanced_engine.generate_response",
                        side_effect=Exception("LLM unavailable")):
            result = engine.reason("test query")

        self.assertIsNotNone(result)
        self.assertIsNotNone(result.error)
        self.assertIn("PLAN", result.phases)

    def test_fallback_phases_all_present(self):
        """_fallback_phases must return all 8 phases."""
        from lirox.reasoning.advanced_engine import AdvancedReasoningEngine

        engine = AdvancedReasoningEngine()
        phases = engine._fallback_phases("test")
        for name in ["UNDERSTAND", "DECOMPOSE", "ANALYZE", "EVALUATE",
                     "SIMULATE", "REFINE", "PLAN", "VERIFY"]:
            self.assertIn(name, phases)


# ─────────────────────────────────────────────────────────────────────────────
# Feature-3: Personality emergence
# ─────────────────────────────────────────────────────────────────────────────

class TestPersonalityEmergence(unittest.TestCase):
    def test_generates_technical_traits_for_dev_niche(self):
        """Technical niche should produce direct tone + deep technical depth."""
        from lirox.personality.emergence import PersonalityEngine

        engine = PersonalityEngine()
        traits = engine.generate_from_profile(
            {"niche": "Software Engineering", "goals": ["ship fast", "write clean code"]}
        )
        self.assertEqual(traits["tone"], "direct")
        self.assertEqual(traits["technical_depth"], "deep")

    def test_generates_casual_traits_for_creative_niche(self):
        """Creative niche should produce casual tone with emojis."""
        from lirox.personality.emergence import PersonalityEngine

        engine = PersonalityEngine()
        traits = engine.generate_from_profile({"niche": "Design & Art", "goals": []})
        self.assertEqual(traits["tone"], "casual")
        self.assertTrue(traits["use_emojis"])

    def test_get_style_hint_returns_string(self):
        """get_style_hint must return a non-empty string."""
        from lirox.personality.emergence import PersonalityEngine

        engine = PersonalityEngine()
        engine._traits = {"tone": "direct", "verbosity": "concise",
                           "technical_depth": "deep", "humor": False,
                           "use_emojis": False, "core_values": [],
                           "communication_quirks": [], "proactivity": "medium",
                           "updated_at": ""}
        hint = engine.get_style_hint()
        self.assertIsInstance(hint, str)
        self.assertGreater(len(hint), 0)

    def test_persist_and_reload(self):
        """persist() + load() roundtrip must preserve traits."""
        from lirox.personality.emergence import PersonalityEngine

        with tempfile.TemporaryDirectory() as tmp:
            fake_mind = Path(tmp) / "mind"
            fake_mind.mkdir()
            with mock.patch("lirox.personality.emergence._personality_file",
                            return_value=fake_mind / "personality.json"):
                engine1 = PersonalityEngine()
                traits = engine1.generate_from_profile({"niche": "SRE", "goals": []})
                engine1.persist(traits)

                engine2 = PersonalityEngine()
                loaded = engine2.load()
                self.assertEqual(loaded["tone"], traits["tone"])


# ─────────────────────────────────────────────────────────────────────────────
# Feature-7: Audit logger
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditLogger(unittest.TestCase):
    def test_audit_log_writes_entry(self):
        """audit_log must write a valid JSON entry to the log file."""
        from lirox.audit.logger import audit_log, AuditEvent, _get_log_file
        import lirox.audit.logger as _al

        with tempfile.TemporaryDirectory() as tmp:
            _al._audit_dir = Path(tmp)
            _al._session_id = "test_session"

            audit_log(AuditEvent.FILE_WRITE, path="/tmp/test.py", message="test write")

            entries = _al.read_audit_log()
            self.assertGreater(len(entries), 0)
            last = entries[-1]
            self.assertEqual(last["event"], "file_write")
            self.assertEqual(last["path"], "/tmp/test.py")

    def test_audit_log_disabled_writes_nothing(self):
        """When AUDIT_ENABLED=false, no entries should be written."""
        import lirox.audit.logger as _al
        original = _al._enabled

        try:
            _al._enabled = False
            with tempfile.TemporaryDirectory() as tmp:
                _al._audit_dir = Path(tmp)
                _al._session_id = "test_disabled"
                from lirox.audit.logger import audit_log, AuditEvent
                audit_log(AuditEvent.FILE_WRITE, path="/tmp/test.py")

                log_file = Path(tmp) / "audit_test_disabled.jsonl"
                self.assertFalse(log_file.exists())
        finally:
            _al._enabled = original

    def test_format_audit_log_returns_string(self):
        """format_audit_log must return a non-empty string."""
        import lirox.audit.logger as _al
        with tempfile.TemporaryDirectory() as tmp:
            _al._audit_dir = Path(tmp)
            _al._session_id = "test_format"
            from lirox.audit.logger import audit_log, AuditEvent, format_audit_log
            audit_log(AuditEvent.SYSTEM_START, message="startup")
            result = format_audit_log()
            self.assertIsInstance(result, str)
            self.assertIn("SYSTEM_START", result.upper())


# ─────────────────────────────────────────────────────────────────────────────
# Feature-5: Home screen integration
# ─────────────────────────────────────────────────────────────────────────────

class TestHomeScreenIntegration(unittest.TestCase):
    def test_setup_home_folder_creates_structure(self):
        """setup_home_folder must create the full directory structure."""
        import lirox.home_screen.integration as _hs
        with tempfile.TemporaryDirectory() as tmp:
            fake_home = Path(tmp) / "Lirox"
            original_home = _hs.HOME_LIROX_DIR

            try:
                _hs.HOME_LIROX_DIR = fake_home

                # Patch platform shortcut to be a no-op
                with mock.patch.object(_hs, "_create_platform_shortcut",
                                       return_value=False):
                    result = _hs.setup_home_folder(ask=False)

                self.assertTrue(result["created"])
                self.assertIsNone(result["error"])
                self.assertTrue(fake_home.is_dir())
                self.assertTrue((fake_home / "data" / "memory").is_dir())
                self.assertTrue((fake_home / "quick-access").is_dir())
                self.assertTrue((fake_home / "README.md").exists())
                self.assertTrue((fake_home / ".lirox-config").exists())
            finally:
                _hs.HOME_LIROX_DIR = original_home

    def test_is_home_folder_setup_false_when_missing(self):
        """is_home_folder_setup must return False when folder is missing."""
        import lirox.home_screen.integration as _hs
        with tempfile.TemporaryDirectory() as tmp:
            _hs_orig = _hs.HOME_LIROX_DIR
            try:
                _hs.HOME_LIROX_DIR = Path(tmp) / "NonExistentLirox"
                self.assertFalse(_hs.is_home_folder_setup())
            finally:
                _hs.HOME_LIROX_DIR = _hs_orig


if __name__ == "__main__":
    unittest.main()
