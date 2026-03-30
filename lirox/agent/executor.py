"""
Lirox v0.3 — Enhanced Executor

Executes structured plans step-by-step with:
- Tool routing (terminal, browser, file_io, llm)
- Dependency checking between steps
- Context chaining (step N output → step N+1 input)
- Retry logic with exponential backoff
- Per-step status tracking and execution trace
"""

import time
from lirox.tools.terminal import run_command
from lirox.tools.browser import BrowserTool
from lirox.tools.file_io import FileIOTool
from lirox.utils.llm import generate_response
from lirox.utils.errors import (
    ToolExecutionError, PlanExecutionError,
    with_retry, should_retry
)
from lirox.ui.display import execute_panel, update_plan_step
from lirox.config import MAX_RETRIES, RETRY_BACKOFF


# Keywords that suggest a terminal command is needed (fallback heuristic)
COMMAND_TRIGGERS = [
    "run", "create", "install", "mkdir", "directory", "folder",
    "cat", "touch", "pip", "npm", "python", "execute", "launch", "open"
]


class Executor:
    """Executes structured plans step-by-step with error recovery."""

    def __init__(self):
        self.browser = BrowserTool()
        self.file_io = FileIOTool()
        self.last_trace = []  # Execution trace for /trace command

    def execute_plan(self, plan, provider="openai", system_prompt=None):
        """
        Execute all steps in a structured plan.

        Args:
            plan: Plan dict from Planner (with structured steps)
            provider: LLM provider to use
            system_prompt: System prompt for LLM calls

        Returns:
            Tuple of (results_dict, summary_string)
        """
        results = {}
        self.last_trace = []
        steps = plan.get("steps", [])

        for step in steps:
            step_id = step["id"]
            update_plan_step(step_id, step["task"], status="progress")
            start_time = time.time()

            # Check dependencies are met
            if not self._check_dependencies(step, results):
                result = {
                    "status": "skipped",
                    "output": "Skipped: dependency step failed",
                    "duration": 0
                }
                results[step_id] = result
                update_plan_step(step_id, step["task"], status="skipped")
                self._add_trace(step, result)
                continue

            # Execute with retry logic
            try:
                result = self._execute_with_retry(step, results, provider, system_prompt)
            except Exception as e:
                result = {
                    "status": "failed",
                    "output": "",
                    "error": str(e),
                    "duration": time.time() - start_time
                }

            result["duration"] = round(time.time() - start_time, 2)
            results[step_id] = result

            # Update UI
            status = "success" if result["status"] == "success" else "failed"
            update_plan_step(step_id, step["task"], status=status)

            # Add to trace
            self._add_trace(step, result)

        # Generate summary
        summary = self._summarize_results(plan, results, provider, system_prompt)
        return results, summary

    def _execute_with_retry(self, step, previous_results, provider, system_prompt):
        """
        Execute a single step with retry logic.
        Retries up to MAX_RETRIES times for transient errors.
        """
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                output = self._execute_step(step, previous_results, provider, system_prompt)
                return {
                    "status": "success",
                    "output": output,
                    "attempt": attempt + 1
                }
            except ToolExecutionError as e:
                last_error = e
                if e.is_retryable and attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_BACKOFF * (2 ** attempt)
                    time.sleep(wait_time)
                    continue
                break
            except Exception as e:
                last_error = e
                if should_retry(e) and attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_BACKOFF * (2 ** attempt)
                    time.sleep(wait_time)
                    continue
                break

        return {
            "status": "failed",
            "output": "",
            "error": str(last_error),
            "attempts": MAX_RETRIES
        }

    def _execute_step(self, step, previous_results, provider, system_prompt):
        """
        Execute a single step by routing to the correct tool.

        Args:
            step: Step dict from plan
            previous_results: Dict of {step_id: result} for completed steps
            provider: LLM provider
            system_prompt: System prompt

        Returns:
            Output string from the step execution
        """
        # Build context from previous step outputs
        context = self._build_context(step, previous_results)
        tools = step.get("tools", ["llm"])

        # Route to the appropriate tool
        if "terminal" in tools:
            return self._run_terminal_step(step, context, provider, system_prompt)
        elif "browser" in tools:
            return self._run_browser_step(step, context, provider, system_prompt)
        elif "file_io" in tools:
            return self._run_file_step(step, context, provider, system_prompt)
        else:
            # Default: LLM reasoning step
            return self._run_llm_step(step, context, provider, system_prompt)

    def _run_terminal_step(self, step, context, provider, system_prompt):
        """Extract and execute a terminal command from a step."""
        cmd_prompt = (
            f"Extract the exact terminal command to execute from this task. "
            f"Return ONLY the raw command. No explanation, no backticks, no extra text.\n\n"
            f"Task: {step['task']}\n"
            f"Context: {context[:500] if context else 'None'}"
        )
        command = generate_response(cmd_prompt, provider, system_prompt=system_prompt)
        command = command.strip().strip("`\"' \n")

        # Filter out non-command responses
        if not command or len(command) > 500 or "\n" in command:
            return f"Could not extract a valid command from: {step['task']}"

        execute_panel(command)
        result = run_command(command)
        return result

    def _run_browser_step(self, step, context, provider, system_prompt):
        """Execute a browser/web step — search or fetch."""
        task_lower = step["task"].lower()

        # Determine if this is a search or a specific URL fetch
        if any(k in task_lower for k in ["search", "find", "lookup", "research"]):
            # Web search
            search_query = step["task"]
            results = self.browser.search_web(search_query, num_results=5)

            if not results:
                return "No search results found."

            # Format results
            formatted = []
            for i, r in enumerate(results, 1):
                formatted.append(f"{i}. {r['title']}\n   {r['url']}\n   {r['snippet']}")

            # Fetch top result for detailed content
            top_url = results[0].get("url", "") if results else ""
            page_text = ""
            if top_url:
                try:
                    page_text = self.browser.summarize_page(top_url)
                except Exception:
                    page_text = ""

            return (
                "Search Results:\n" +
                "\n\n".join(formatted) +
                (f"\n\n--- Top Result Content ---\n{page_text[:2000]}" if page_text else "")
            )

        elif "http" in task_lower:
            # Extract URL from task
            import re
            url_match = re.search(r'https?://\S+', step["task"])
            if url_match:
                url = url_match.group(0).rstrip(".,;)")
                content = self.browser.summarize_page(url)
                return f"Content from {url}:\n{content}"

        # Fallback: use LLM to determine what to search
        search_prompt = (
            f"What search query should I use to complete this task? "
            f"Return ONLY the search query, nothing else.\n\n"
            f"Task: {step['task']}"
        )
        query = generate_response(search_prompt, provider, system_prompt=system_prompt)
        query = query.strip().strip("\"'")
        results = self.browser.search_web(query, num_results=5)

        if results:
            formatted = [f"- {r['title']}: {r['snippet']}" for r in results]
            return f"Search for '{query}':\n" + "\n".join(formatted)

        return f"No results found for: {query}"

    def _run_file_step(self, step, context, provider, system_prompt):
        """Execute a file I/O step — read, write, or list."""
        task_lower = step["task"].lower()

        if any(k in task_lower for k in ["read", "open", "load"]):
            # Try to extract filename from task
            file_prompt = (
                f"Extract the file path from this task. Return ONLY the path.\n\n"
                f"Task: {step['task']}"
            )
            path = generate_response(file_prompt, provider, system_prompt=system_prompt)
            path = path.strip().strip("\"'` \n")
            try:
                return self.file_io.read_file(path)
            except ToolExecutionError as e:
                return str(e)

        elif any(k in task_lower for k in ["write", "save", "create file", "output"]):
            # Determine what to write and where
            content_to_write = context if context else step.get("task", "")

            # Use LLM to generate content if context is not the content itself
            if not context or len(context) < 50:
                write_prompt = (
                    f"Generate the content for this task. Return ONLY the content to write.\n\n"
                    f"Task: {step['task']}\n"
                    f"Context: {context[:1000] if context else 'None'}"
                )
                content_to_write = generate_response(write_prompt, provider, system_prompt=system_prompt)

            # Determine filename
            path_prompt = (
                f"Extract or suggest a filename for saving this content. "
                f"Return ONLY the file path (use outputs/ directory). No explanation.\n\n"
                f"Task: {step['task']}"
            )
            path = generate_response(path_prompt, provider, system_prompt=system_prompt)
            path = path.strip().strip("\"'` \n")

            # Default to outputs/ if no path extracted
            if "/" not in path and "\\" not in path:
                path = f"outputs/{path}"

            try:
                return self.file_io.write_file(path, content_to_write)
            except ToolExecutionError as e:
                return str(e)

        elif any(k in task_lower for k in ["list", "ls", "directory"]):
            try:
                files = self.file_io.list_files(".")
                return "\n".join(files)
            except ToolExecutionError as e:
                return str(e)

        # Fallback to LLM step
        return self._run_llm_step(step, context, provider, system_prompt)

    def _run_llm_step(self, step, context, provider, system_prompt):
        """Execute a pure reasoning/writing step via LLM."""
        reasoning_prompt = (
            f"Complete this task step and provide a concise, useful result.\n\n"
            f"Task: {step['task']}\n"
            f"Expected output: {step.get('expected_output', 'A clear result')}\n"
        )
        if context:
            reasoning_prompt += f"\nContext from previous steps:\n{context[:3000]}"

        return generate_response(reasoning_prompt, provider, system_prompt=system_prompt)

    def _build_context(self, step, previous_results):
        """Build context string from outputs of dependency steps."""
        depends_on = step.get("depends_on", [])
        if not depends_on:
            return ""

        context_parts = []
        for dep_id in depends_on:
            dep_result = previous_results.get(dep_id, {})
            if dep_result.get("status") == "success":
                output = dep_result.get("output", "")
                # Truncate long outputs
                if len(output) > 1500:
                    output = output[:1500] + "... [truncated]"
                context_parts.append(f"[Step {dep_id} output]: {output}")

        return "\n\n".join(context_parts)

    def _check_dependencies(self, step, results):
        """
        Check if all dependency steps completed successfully.
        Returns False if any required dependency failed.
        """
        depends_on = step.get("depends_on", [])
        for dep_id in depends_on:
            dep_result = results.get(dep_id, {})
            if dep_result.get("status") not in ("success", None):
                # Dependency failed — but only block if it was critical
                if dep_result.get("status") == "failed":
                    return False
        return True

    def _summarize_results(self, plan, results, provider, system_prompt):
        """Generate a human-readable summary of the entire execution."""
        lines = []
        successes = 0
        total = len(results)

        for step in plan.get("steps", []):
            step_id = step["id"]
            result = results.get(step_id, {})
            status = result.get("status", "unknown")
            duration = result.get("duration", 0)

            icon = "✓" if status == "success" else "✗" if status == "failed" else "⊘"
            lines.append(f"{icon} Step {step_id}: {step['task'][:60]} ({duration}s)")

            if status == "success":
                successes += 1

        summary = (
            f"📊 EXECUTION SUMMARY\n\n"
            f"Goal: {plan.get('goal', 'Unknown')}\n"
            f"Result: {successes}/{total} steps completed\n\n"
        ) + "\n".join(lines)

        # Ask LLM for a brief narrative summary if all steps succeeded
        if successes == total and total > 0:
            # Collect all outputs for summary
            all_outputs = []
            for step in plan.get("steps", []):
                result = results.get(step["id"], {})
                output = result.get("output", "")[:500]
                all_outputs.append(f"Step {step['id']} ({step['task']}): {output}")

            try:
                summary_prompt = (
                    f"Summarize what was accomplished in 2-3 sentences.\n\n"
                    f"Goal: {plan.get('goal', '')}\n"
                    f"Results:\n" + "\n".join(all_outputs)
                )
                narrative = generate_response(summary_prompt, provider, system_prompt=system_prompt)
                summary += f"\n\n{narrative}"
            except Exception:
                pass

        return summary

    def _add_trace(self, step, result):
        """Add step execution details to the trace log."""
        self.last_trace.append({
            "step_id": step["id"],
            "task": step["task"],
            "tools": step.get("tools", []),
            "status": result.get("status", "unknown"),
            "output_preview": result.get("output", "")[:200],
            "error": result.get("error", ""),
            "duration": result.get("duration", 0),
            "attempts": result.get("attempt", result.get("attempts", 1))
        })

    def get_trace(self):
        """Return the execution trace for /trace command."""
        if not self.last_trace:
            return "No execution trace available. Run a task first."

        lines = ["🔍 EXECUTION TRACE", ""]
        for entry in self.last_trace:
            icon = "✓" if entry["status"] == "success" else "✗" if entry["status"] == "failed" else "⊘"
            lines.append(f"{icon} Step {entry['step_id']}: {entry['task']}")
            lines.append(f"  Tools: {', '.join(entry['tools'])}")
            lines.append(f"  Status: {entry['status']} | Duration: {entry['duration']}s | Attempts: {entry['attempts']}")
            if entry["output_preview"]:
                preview = entry["output_preview"][:100].replace("\n", " ")
                lines.append(f"  Output: {preview}")
            if entry["error"]:
                lines.append(f"  Error: {entry['error'][:100]}")
            lines.append("")

        return "\n".join(lines)
