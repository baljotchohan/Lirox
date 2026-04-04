"""
Lirox v0.3 — Test Suite

Tests for all v0.3 components:
- Planner (structured plan generation)
- Executor (step execution with retry)
- Reasoner (step evaluation)
- Browser tool (URL fetching, safety)
- File I/O tool (read/write, safety)
- Memory (search, stats)
- Error handling (retry logic)
- Scheduler (add/list tasks)

All LLM calls are mocked — no real API calls during testing.
"""

import os
import json
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock


# ─── ERROR HANDLING TESTS ─────────────────────────────────────────────────────

class TestErrorHandling:
    """Tests for lirox/utils/errors.py"""

    def test_should_retry_timeout(self):
        from lirox.utils.errors import should_retry
        assert should_retry(Exception("Connection timeout")) is True

    def test_should_retry_rate_limit(self):
        from lirox.utils.errors import should_retry
        assert should_retry(Exception("Rate limit exceeded (429)")) is True

    def test_should_not_retry_auth(self):
        from lirox.utils.errors import should_retry
        assert should_retry(Exception("Authentication failed")) is False

    def test_should_retry_tool_error_flag(self):
        from lirox.utils.errors import ToolExecutionError, should_retry
        err = ToolExecutionError("browser", "server error", is_retryable=True)
        assert should_retry(err) is True

    def test_with_retry_succeeds_first_try(self):
        from lirox.utils.errors import with_retry
        result = with_retry(lambda: "success", max_retries=3)
        assert result == "success"

    def test_with_retry_retries_on_transient(self):
        from lirox.utils.errors import with_retry
        call_count = {"n": 0}

        def flaky():
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise Exception("Connection timeout")
            return "ok"

        result = with_retry(flaky, max_retries=3, backoff=0.01)
        assert result == "ok"
        assert call_count["n"] == 3

    def test_with_retry_gives_up_on_permanent(self):
        from lirox.utils.errors import with_retry

        def always_fail():
            raise Exception("Authentication failed")

        with pytest.raises(Exception, match="Authentication failed"):
            with_retry(always_fail, max_retries=3, backoff=0.01)


# ─── PLANNER TESTS ────────────────────────────────────────────────────────────

class TestPlanner:
    """Tests for lirox/agent/planner.py"""

    @patch("lirox.agent.planner.generate_response")
    def test_creates_structured_plan(self, mock_llm):
        """Planner converts goal to structured plan dict."""
        mock_llm.return_value = json.dumps({
            "goal": "Write a blog post",
            "steps": [
                {"id": 1, "task": "Research topic", "tools": ["browser"], "depends_on": [], "expected_output": "Research notes"},
                {"id": 2, "task": "Write draft", "tools": ["llm"], "depends_on": [1], "expected_output": "Blog post draft"},
                {"id": 3, "task": "Save to file", "tools": ["file_io"], "depends_on": [2], "expected_output": "File saved"}
            ],
            "estimated_time": "10 minutes",
            "tools_required": ["browser", "llm", "file_io"]
        })

        from lirox.agent.planner import Planner
        planner = Planner(provider="groq")
        plan = planner.create_plan("Write a blog post")

        assert isinstance(plan, dict)
        assert "steps" in plan
        assert len(plan["steps"]) == 3
        assert all("task" in s for s in plan["steps"])
        assert all("tools" in s for s in plan["steps"])
        assert plan["steps"][1]["depends_on"] == [1]

    @patch("lirox.agent.planner.generate_response")
    def test_handles_markdown_fenced_json(self, mock_llm):
        """Planner extracts JSON from markdown code fences."""
        mock_llm.return_value = '```json\n{"goal": "test", "steps": [{"id": 1, "task": "do it", "tools": ["llm"], "depends_on": [], "expected_output": "done"}], "estimated_time": "1 min", "tools_required": ["llm"]}\n```'

        from lirox.agent.planner import Planner
        planner = Planner(provider="groq")
        plan = planner.create_plan("test")

        assert isinstance(plan, dict)
        assert len(plan["steps"]) == 1

    @patch("lirox.agent.planner.generate_response")
    def test_fallback_on_bad_json(self, mock_llm):
        """Planner falls back to flat list when LLM returns non-JSON."""
        mock_llm.return_value = "1. Do the first thing\n2. Do the second thing\n3. Finish up"

        from lirox.agent.planner import Planner
        planner = Planner(provider="groq")
        plan = planner.create_plan("Do stuff")

        assert isinstance(plan, dict)
        assert "steps" in plan
        assert len(plan["steps"]) == 3
        assert plan["steps"][0]["task"] == "Do the first thing"

    @patch("lirox.agent.planner.generate_response")
    def test_stores_last_plan(self, mock_llm):
        """Planner stores last plan for /execute-plan."""
        mock_llm.return_value = '{"goal": "x", "steps": [{"id": 1, "task": "y"}], "estimated_time": "1m", "tools_required": []}'

        from lirox.agent.planner import Planner
        planner = Planner(provider="groq")
        plan = planner.create_plan("x")

        assert planner.get_last_plan() is not None
        assert planner.get_last_plan()["goal"] == "x"

    def test_guess_tool_terminal(self):
        """Tool guessing detects terminal keywords."""
        from lirox.agent.planner import Planner
        planner = Planner()
        assert planner._guess_tool("Install numpy using pip") == "terminal"
        assert planner._guess_tool("Run the python script") == "terminal"

    def test_guess_tool_browser(self):
        """Tool guessing detects browser keywords."""
        from lirox.agent.planner import Planner
        planner = Planner()
        assert planner._guess_tool("Search the web for AI trends") == "browser"
        assert planner._guess_tool("Fetch the URL content") == "browser"

    def test_guess_tool_file(self):
        """Tool guessing detects file keywords."""
        from lirox.agent.planner import Planner
        planner = Planner()
        assert planner._guess_tool("Write file to outputs/result.txt") == "file_io"
        assert planner._guess_tool("Save to disk") == "file_io"

    def test_guess_tool_default_llm(self):
        """Tool guessing defaults to llm for ambiguous text."""
        from lirox.agent.planner import Planner
        planner = Planner()
        assert planner._guess_tool("Analyze the data and summarize") == "llm"


# ─── SKILL REGISTRY TESTS ────────────────────────────────────────────────────

class TestSkillRegistry:
    """Tests for lirox/skills/registry.py"""

    def test_register_skill(self):
        from lirox.skills import SkillRegistry
        from lirox.skills.bash_skill import BashSkill
        registry = SkillRegistry()
        skill = BashSkill()
        registry.register(skill)
        assert registry.get(skill.name) is not None

    def test_get_enabled_skills(self):
        from lirox.skills import SkillRegistry
        from lirox.skills.bash_skill import BashSkill
        registry = SkillRegistry()
        registry.register(BashSkill())
        assert len(registry.get_enabled()) >= 1

    def test_route_query(self):
        from lirox.skills import SkillRegistry
        from lirox.skills.bash_skill import BashSkill
        registry = SkillRegistry()
        registry.register(BashSkill())
        skill = registry.route("run terminal command ls")
        assert skill is not None

    def test_route_with_scores(self):
        from lirox.skills import SkillRegistry
        from lirox.skills.bash_skill import BashSkill
        registry = SkillRegistry()
        registry.register(BashSkill())
        scores = registry.route_with_scores("run terminal command")
        assert len(scores) >= 1

    def test_disable_skill(self):
        from lirox.skills import SkillRegistry
        from lirox.skills.bash_skill import BashSkill
        registry = SkillRegistry()
        skill = BashSkill()
        registry.register(skill)
        registry.disable(skill.name)
        assert registry.is_enabled(skill.name) is False

    def test_enable_skill(self):
        from lirox.skills import SkillRegistry
        from lirox.skills.bash_skill import BashSkill
        registry = SkillRegistry()
        skill = BashSkill()
        registry.register(skill)
        registry.disable(skill.name)
        registry.enable(skill.name)
        assert registry.is_enabled(skill.name) is True

    def test_auto_discovery(self):
        from lirox.skills import registry
        skills = registry.get_all()
        assert len(skills) > 0

    def test_skill_summary(self):
        from lirox.skills import SkillRegistry
        from lirox.skills.bash_skill import BashSkill
        registry = SkillRegistry()
        registry.register(BashSkill())
        summary = registry.summary()
        assert "bash" in summary


# ─── REASONER TESTS ───────────────────────────────────────────────────────────



class TestReasoner:
    """Tests for lirox/agent/reasoner.py"""

    def test_evaluates_successful_step(self):
        """Reasoner evaluates a successful step correctly."""
        from lirox.agent.reasoner import Reasoner
        reasoner = Reasoner(provider="groq")

        step = {"id": 1, "task": "Analyze data", "tools": ["llm"], "expected_output": "analysis results"}
        result = {"status": "success", "output": "Here are the analysis results with findings."}
        plan = {"goal": "test", "steps": [step]}

        evaluation = reasoner.evaluate_step(step, result, plan, {1: result})

        assert evaluation["success"] is True
        assert evaluation["confidence"] > 0.3
        assert evaluation["recommended_action"] == "continue"

    def test_evaluates_failed_step(self):
        """Reasoner evaluates a failed step and recommends action."""
        from lirox.agent.reasoner import Reasoner
        reasoner = Reasoner(provider="groq")

        step = {"id": 1, "task": "Fetch URL", "tools": ["browser"], "expected_output": "page content"}
        result = {"status": "failed", "output": "", "error": "Connection timeout after 10s"}
        plan = {"goal": "test", "steps": [step]}

        evaluation = reasoner.evaluate_step(step, result, plan, {1: result})

        assert evaluation["success"] is False
        assert evaluation["recommended_action"] == "retry"  # Timeout is retryable

    def test_reflects_on_progress(self):
        """Reasoner reflects on overall plan progress."""
        from lirox.agent.reasoner import Reasoner
        reasoner = Reasoner()

        plan = {
            "goal": "test",
            "steps": [
                {"id": 1, "task": "A"},
                {"id": 2, "task": "B"},
                {"id": 3, "task": "C"}
            ]
        }
        results = {
            1: {"status": "success"},
            2: {"status": "success"},
        }

        reflection = reasoner.reflect_on_progress(plan, results)
        assert reflection["completed"] == 2
        assert reflection["remaining"] == 1
        assert reflection["on_track"] is True

    def test_generates_reasoning_summary(self):
        """Reasoner generates readable summary."""
        from lirox.agent.reasoner import Reasoner
        reasoner = Reasoner()

        step = {"id": 1, "task": "Test step", "tools": ["llm"], "expected_output": "done"}
        result = {"status": "success", "output": "done"}
        plan = {"goal": "test goal", "steps": [step]}

        reasoner.evaluate_step(step, result, plan, {1: result})
        summary = reasoner.generate_reasoning_summary(plan, {1: result})

        # FIX: Check the text attribute, and verify summary is a dictionary
        assert "Reasoning Summary" in reasoner.last_reasoning_text
        assert isinstance(summary, dict)
        assert "evaluations" in summary

    def test_reset_clears_state(self):
        """Reasoner reset clears all evaluations."""
        from lirox.agent.reasoner import Reasoner
        reasoner = Reasoner()
        reasoner.evaluations = [{"test": True}]
        reasoner.last_reasoning = "some text"

        reasoner.reset()
        assert len(reasoner.evaluations) == 0
        assert reasoner.last_reasoning is None


# ─── BROWSER TOOL TESTS ──────────────────────────────────────────────────────

class TestBrowserTool:
    """Tests for lirox/tools/browser.py"""

    def test_blocks_unsafe_localhost(self):
        """Browser blocks localhost URLs."""
        from lirox.tools.browser import BrowserTool
        browser = BrowserTool()
        safe, reason = browser.is_url_safe("http://localhost:8080/admin")
        assert safe is False

    def test_blocks_internal_ip(self):
        """Browser blocks internal IP addresses."""
        from lirox.tools.browser import BrowserTool
        browser = BrowserTool()
        safe, reason = browser.is_url_safe("http://192.168.1.1/router")
        assert safe is False

    def test_blocks_non_http(self):
        """Browser blocks non-HTTP schemes."""
        from lirox.tools.browser import BrowserTool
        browser = BrowserTool()
        safe, _ = browser.is_url_safe("file:///etc/passwd")
        assert safe is False

    def test_allows_https(self):
        """Browser allows HTTPS URLs."""
        from lirox.tools.browser import BrowserTool
        browser = BrowserTool()
        safe, _ = browser.is_url_safe("https://example.com")
        assert safe is True

    def test_extract_text_strips_tags(self):
        """Browser text extraction removes HTML tags."""
        from lirox.tools.browser import BrowserTool
        browser = BrowserTool()
        html = "<html><body><h1>Title</h1><p>Content here.</p></body></html>"
        text = browser.extract_text(html)
        assert "Title" in text
        assert "Content here" in text
        assert "<h1>" not in text

    def test_extract_data_with_selector(self):
        """Browser CSS selector extraction works."""
        from lirox.tools.browser import BrowserTool
        browser = BrowserTool()
        html = '<div class="items"><span class="item">A</span><span class="item">B</span></div>'
        items = browser.extract_data(html, ".item")
        assert items == ["A", "B"]

    @patch("lirox.tools.browser.BrowserTool.fetch_url")
    def test_search_web_returns_results(self, mock_fetch):
        """Browser web search parses DuckDuckGo results."""
        # Mock a simple DDG-like response
        mock_fetch.return_value = """
        <div class="result">
            <a class="result__a" href="https://example.com">Test Result</a>
            <div class="result__snippet">This is a test snippet</div>
        </div>
        """
        from lirox.tools.browser import BrowserTool
        browser = BrowserTool()
        results = browser.search_web("test query")
        assert len(results) >= 1
        assert results[0]["title"] == "Test Result"


# ─── FILE I/O TESTS ──────────────────────────────────────────────────────────



class TestFileIOTool:
    """Tests for lirox/tools/file_io.py"""

    def setup_method(self):
        """Create temp directory for tests."""
        self.test_dir = tempfile.mkdtemp()
        self.orig_dir = os.getcwd()
        os.chdir(self.test_dir)
        os.makedirs("outputs", exist_ok=True)
        # FIX: Patch SAFE_DIRS instead of the removed _PROJECT_ROOT_DIR
        self.patcher = patch("lirox.tools.file_io.SAFE_DIRS", [self.test_dir])
        self.patcher.start()

    def teardown_method(self):
        """Clean up temp directory."""
        self.patcher.stop()
        os.chdir(self.orig_dir)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_write_and_read_file(self):
        """File I/O can write and read back."""
        from lirox.tools.file_io import FileIOTool
        io_tool = FileIOTool()

        result = io_tool.write_file("outputs/test.txt", "Hello Lirox")
        assert "File written" in result

        content = io_tool.read_file("outputs/test.txt")
        assert content == "Hello Lirox"

    def test_blocks_directory_traversal(self):
        """File I/O blocks directory traversal attacks."""
        from lirox.tools.file_io import FileIOTool
        from lirox.utils.errors import ToolExecutionError
        io_tool = FileIOTool()

        with pytest.raises(ToolExecutionError, match="Access denied"):
            io_tool.read_file("../../../etc/passwd")

    def test_append_file(self):
        """File I/O append mode works."""
        from lirox.tools.file_io import FileIOTool
        io_tool = FileIOTool()

        io_tool.write_file("outputs/append_test.txt", "Line 1\n")
        io_tool.append_file("outputs/append_test.txt", "Line 2\n")
        content = io_tool.read_file("outputs/append_test.txt")
        assert "Line 1" in content
        assert "Line 2" in content

    def test_list_files(self):
        """File I/O lists directory contents."""
        from lirox.tools.file_io import FileIOTool
        io_tool = FileIOTool()

        io_tool.write_file("outputs/a.txt", "a")
        io_tool.write_file("outputs/b.txt", "b")
        files = io_tool.list_files("outputs")
        assert len(files) >= 2

    def test_file_exists(self):
        """File I/O checks file existence."""
        from lirox.tools.file_io import FileIOTool
        io_tool = FileIOTool()

        io_tool.write_file("outputs/exists.txt", "x")
        assert io_tool.file_exists("outputs/exists.txt") is True
        assert io_tool.file_exists("outputs/nope.txt") is False

    def test_resolves_tilde_path(self):
        """File I/O resolves ~ to home directory."""
        from lirox.tools.file_io import FileIOTool
        io_tool = FileIOTool()
        resolved = io_tool._resolve_path("~/Desktop/test.txt")
        assert "~" not in resolved
        assert "Desktop" in resolved


# ─── MEMORY TESTS ────────────────────────────────────────────────────────────

class TestMemory:
    """Tests for lirox/agent/memory.py"""

    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.orig_dir = os.getcwd()
        os.chdir(self.test_dir)

    def teardown_method(self):
        os.chdir(self.orig_dir)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_save_and_retrieve(self):
        """Memory saves and retrieves messages."""
        from lirox.agent.memory import Memory
        mem = Memory(storage_file="test_memory.json")

        mem.save_memory("user", "Hello")
        mem.save_memory("assistant", "Hi there!")

        context = mem.get_context()
        assert "Hello" in context
        assert "Hi there!" in context

    def test_search_memory(self):
        """Memory search finds relevant exchanges."""
        from lirox.agent.memory import Memory
        mem = Memory(storage_file="test_memory.json")

        mem.save_memory("user", "I want to learn Python")
        mem.save_memory("assistant", "Python is a great choice")
        mem.save_memory("user", "What about JavaScript?")
        mem.save_memory("assistant", "JavaScript is also popular")

        results = mem.search_memory("Python")
        assert len(results) >= 1
        assert any("Python" in r["content"] for r in results)

    def test_get_stats(self):
        """Memory stats returns correct counts."""
        from lirox.agent.memory import Memory
        mem = Memory(storage_file="test_memory.json")

        mem.save_memory("user", "Hello")
        mem.save_memory("assistant", "Hi")

        stats = mem.get_stats()
        assert stats["total_messages"] == 2
        assert stats["user_messages"] == 1
        assert stats["assistant_messages"] == 1

    def test_clear_memory(self):
        """Memory clear removes all history."""
        from lirox.agent.memory import Memory
        mem = Memory(storage_file="test_memory.json")

        mem.save_memory("user", "Hello")
        mem.clear()

        assert len(mem.history) == 0


# ─── SCHEDULER TESTS ─────────────────────────────────────────────────────────

class TestScheduler:
    """Tests for lirox/agent/scheduler.py"""

    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.orig_dir = os.getcwd()
        os.chdir(self.test_dir)

    def teardown_method(self):
        os.chdir(self.orig_dir)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_schedule_and_list_task(self):
        """Scheduler can add and list tasks."""
        from lirox.agent.scheduler import TaskScheduler
        scheduler = TaskScheduler(storage_file="test_tasks.json")

        task = scheduler.schedule_task("Test goal", "in_5_minutes")
        assert task["id"] == 1
        assert task["status"] == "scheduled"

        listing = scheduler.list_tasks()
        assert "Test goal" in listing

    def test_cancel_task(self):
        """Scheduler can cancel tasks."""
        from lirox.agent.scheduler import TaskScheduler
        scheduler = TaskScheduler(storage_file="test_tasks.json")

        scheduler.schedule_task("Cancel me", "in_5_minutes")
        result = scheduler.cancel_task(1)
        assert "cancelled" in result.lower()

    def test_multiple_tasks(self):
        """Scheduler handles multiple tasks with unique IDs."""
        from lirox.agent.scheduler import TaskScheduler
        scheduler = TaskScheduler(storage_file="test_tasks.json")

        t1 = scheduler.schedule_task("Task A", "in_5_minutes")
        t2 = scheduler.schedule_task("Task B", "in_10_minutes")
        assert t1["id"] != t2["id"]
        assert len(scheduler.tasks) == 2


# ─── TERMINAL SAFETY TESTS ───────────────────────────────────────────────────

class TestTerminalSafety:
    """Tests for lirox/tools/terminal.py — new safety rules."""

    def test_allows_echo(self):
        """Terminal allows echo command."""
        from lirox.tools.terminal import is_safe
        safe, _ = is_safe("echo hello test")
        assert safe is True

    def test_allows_git(self):
        """Terminal allows git commands."""
        from lirox.tools.terminal import is_safe
        safe, _ = is_safe("git status")
        assert safe is True

    def test_allows_chained_commands(self):
        """Terminal allows safe && chains."""
        from lirox.tools.terminal import is_safe
        safe, _ = is_safe("mkdir -p test && ls test")
        assert safe is True

    def test_blocks_dangerous_rm(self):
        """Terminal blocks rm -rf /."""
        from lirox.tools.terminal import is_safe
        safe, _ = is_safe("rm -rf /")
        assert safe is False

    def test_blocks_command_substitution(self):
        """Terminal blocks $() injection."""
        from lirox.tools.terminal import is_safe
        safe, _ = is_safe("echo $(cat /etc/passwd)")
        assert safe is False

    def test_allows_find_command(self):
        """Terminal allows find command."""
        from lirox.tools.terminal import is_safe
        safe, _ = is_safe("find . -name '*.py'")
        assert safe is True

    def test_blocks_eval(self):
        """Terminal blocks eval injection."""
        from lirox.tools.terminal import is_safe
        safe, _ = is_safe("eval 'rm -rf /'")
        assert safe is False

    def test_allows_rm_single_file(self):
        """Terminal allows rm on a single file (not rm -rf /)."""
        from lirox.tools.terminal import is_safe
        safe, _ = is_safe("rm output.txt")
        assert safe is True

    def test_blocks_rm_rf_root(self):
        """Terminal still blocks rm -rf /."""
        from lirox.tools.terminal import is_safe
        safe, _ = is_safe("rm -rf /")
        assert safe is False


# ─── LLM ERROR RESPONSE DETECTION TESTS ─────────────────────────────────────

class TestErrorResponseDetection:
    """Tests for lirox/utils/llm.py — is_error_response()"""

    def test_detects_api_key_missing(self):
        from lirox.utils.llm import is_error_response
        assert is_error_response("OpenAI API key missing. Run /add-api to configure.") is True

    def test_detects_unknown_provider(self):
        from lirox.utils.llm import is_error_response
        assert is_error_response("Unknown provider: foobar") is True

    def test_detects_timeout_error(self):
        from lirox.utils.llm import is_error_response
        assert is_error_response("Error: OpenAI request timed out.") is True

    def test_detects_generic_error(self):
        from lirox.utils.llm import is_error_response
        assert is_error_response("Gemini Error: quota exceeded") is True

    def test_allows_normal_response(self):
        from lirox.utils.llm import is_error_response
        assert is_error_response("Here is a summary of AI trends:\n1. LLMs are growing") is False

    def test_detects_empty_response(self):
        from lirox.utils.llm import is_error_response
        assert is_error_response("") is True
        assert is_error_response(None) is True


# ─── IS_TASK_REQUEST HARDENING TESTS ─────────────────────────────────────────

class TestTaskRequestDetection:
    """Tests for is_task_request hardening."""

    def test_keyword_match_returns_true(self):
        from lirox.utils.llm import is_task_request
        assert is_task_request("create a folder on Desktop") is True

    def test_keyword_match_install(self):
        from lirox.utils.llm import is_task_request
        assert is_task_request("pip install requests") is True

    @patch("lirox.utils.llm.generate_response")
    def test_llm_error_defaults_to_false(self, mock_llm):
        """If LLM call errors, is_task_request defaults to False (chat mode)."""
        mock_llm.return_value = "Groq API key missing. Run /add-api."
        from lirox.utils.llm import is_task_request
        result = is_task_request("what's the weather today")
        assert result is False

    @patch("lirox.utils.llm.generate_response")
    def test_llm_exception_defaults_to_false(self, mock_llm):
        """If LLM call throws, is_task_request defaults to False."""
        mock_llm.side_effect = Exception("Connection refused")
        from lirox.utils.llm import is_task_request
        result = is_task_request("what's the weather today")
        assert result is False


# ─── ENV CONFIG TESTS ────────────────────────────────────────────────────────

class TestEnvConfig:
    """Tests that main config exports correctly."""

    def test_config_has_no_hardcoded_macos(self):
        """Config uses dynamic home directory."""
        from lirox.config import _HOME
        assert _HOME is not None


# ─── MASTER ORCHESTRATOR TESTS ───────────────────────────────────────────────



class TestMasterOrchestrator:
    """Smoke tests for Master Orchestrator (mocked LLM)."""

    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.orig_dir = os.getcwd()
        os.chdir(self.test_dir)
        os.makedirs("outputs", exist_ok=True)

    def teardown_method(self):
        os.chdir(self.orig_dir)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_orchestrator_initialization(self):
        """Master Orchestrator can initialize without crash."""
        from lirox.orchestrator.master import MasterOrchestrator
        orch = MasterOrchestrator()
        assert orch is not None
        assert hasattr(orch, "memory")

    def test_orchestrator_classify_intent(self):
        """Master Orchestrator classifies intents correctly."""
        from lirox.orchestrator.master import MasterOrchestrator, AgentType
        orch = MasterOrchestrator()
        intent = orch.classify_intent("check TSLA price")
        assert intent == AgentType.FINANCE

