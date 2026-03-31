"""
Lirox v0.3 — Agent Core (Orchestrator)

The central brain that coordinates all agent components:
- Planner: goal → structured steps
- Executor: runs steps with tool routing
- Reasoner: evaluates results and reflects
- Memory: conversation history with search
- Profile: user identity and learning
- Scheduler: background task scheduling
"""

import json
from lirox.agent.memory import Memory
from lirox.agent.planner import Planner
from lirox.agent.executor import Executor
from lirox.agent.reasoner import Reasoner
from lirox.agent.profile import UserProfile
from lirox.agent.scheduler import TaskScheduler
from lirox.utils.llm import generate_response, smart_router, is_task_request
from lirox.ui.display import (
    AgentSpinner, agent_panel, plan_panel_v3,
    reasoning_panel, confirm_execute, update_plan_step
)
from lirox.config import PLAN_CONFIRM


class LiroxAgent:
    """Central agent orchestrator — coordinates planning, execution, and reasoning."""

    def __init__(self, provider="auto"):
        self.provider = provider
        self.memory = Memory()
        self.planner = Planner(provider)
        self.executor = Executor()
        self.reasoner = Reasoner(provider)
        self.profile = UserProfile()
        self.scheduler = TaskScheduler()

        # Register scheduler callback for background task execution
        self.scheduler.execute_callback = self._execute_scheduled_task

    def set_provider(self, provider):
        self.provider = provider
        self.planner.set_provider(provider)
        self.reasoner.set_provider(provider)

    def _get_system_prompt(self):
        """Build enriched system prompt with v0.3 capabilities."""
        base = self.profile.to_system_prompt()

        # Append v0.3 capability description
        capabilities = (
            " Your capabilities include: planning complex multi-step tasks, "
            "executing tasks using terminal commands, browsing the web for research, "
            "reading and writing files, reflecting on results, and learning from interactions. "
            "When processing complex requests: 1) PLAN: break into steps, "
            "2) EXECUTE: run each step, 3) REFLECT: evaluate results, "
            "4) RESPOND: summarize what was done."
        )
        return base + capabilities

    def _try_learn_from_exchange(self, user_input, response):
        """
        Passively extracts facts about the user from the exchange.
        Runs silently in the background.
        """
        learn_prompt = f"""
        From this conversation exchange, extract any NEW facts about the user 
        that should be remembered long-term. Return a JSON list of strings.
        If nothing new was learned, return an empty list [].
        Only extract concrete facts: names, tools they use, preferences, goals mentioned.

        Exchange:
        User: {user_input}
        Agent: {response}

        Return ONLY valid JSON like: ["fact 1", "fact 2"]
        """
        try:
            raw_facts = generate_response(learn_prompt, "groq", system_prompt="You are a JSON extractor.")
            if "[" in raw_facts and "]" in raw_facts:
                json_part = raw_facts[raw_facts.find("["):raw_facts.rfind("]")+1]
                facts = json.loads(json_part)
                for fact in facts:
                    if isinstance(fact, str) and len(fact) < 200:
                        self.profile.add_learned_fact(fact)
        except Exception:
            pass

    def process_input(self, user_input):
        """
        Main entry point for processing user input (v0.4 Think-Plan-Execute-Reflect).
        """
        from lirox.agent.policy import policy_engine
        
        system_prompt = self._get_system_prompt()
        context = self.memory.get_relevant_context(user_input)
        agent_name = self.profile.data.get("agent_name", "Lirox")

        # 1. THINK: Classify and Route
        best_provider = smart_router(user_input) if self.provider == "auto" else self.provider
        is_task = is_task_request(user_input, best_provider)

        with AgentSpinner(agent_name) as spinner:
            if is_task:
                # 2. PLAN: Goal → Steps
                plan = self.planner.create_plan(user_input, system_prompt=system_prompt)
                
                # Check Execution Policy
                policy = policy_engine.evaluate_risk(plan)
                
                if not policy["auto_execute"]:
                    spinner.stop()
                    # If this is called from Web UI, we might handle confirmation via state
                    # For CLI compatibility, we still ask
                    plan_panel_v3(plan)
                    if not confirm_execute():
                        return "Plan cancelled. Use /execute-plan to run it later."

                # 3. EXECUTE: Plan → Results
                self.reasoner.reset()
                results, summary = self.executor.execute_plan(
                    plan, best_provider, system_prompt=system_prompt
                )

                # 4. REFLECT: Results → Evaluation
                for step in plan["steps"]:
                    step_result = results.get(step["id"], {})
                    self.reasoner.evaluate_step(step, step_result, plan, results)

                reflection = self.reasoner.generate_reasoning_summary(plan, results)
                final_response = summary
            else:
                # ─── CHAT PHASE ───────────────────────────────────────
                full_prompt = f"{context}User: {user_input}\nAssistant:"
                final_response = generate_response(full_prompt, best_provider, system_prompt=system_prompt)

        # Save to memory
        self.memory.save_memory("user", user_input)
        if not any(e in final_response for e in ["API key missing", "Error:", "Timeout"]):
            self.memory.save_memory("assistant", final_response)

        # Learning
        self._try_learn_from_exchange(user_input, final_response)

        return final_response

    # ─── v0.3 Command Methods ─────────────────────────────────────────────────

    def show_plan(self, goal):
        """
        Create and display a plan without executing it.
        For the /plan command.
        """
        system_prompt = self._get_system_prompt()
        best_provider = smart_router(goal) if self.provider == "auto" else self.provider
        plan = self.planner.create_plan(goal, system_prompt=system_prompt)
        plan_panel_v3(plan)
        return plan

    def execute_last_plan(self):
        """
        Execute the last generated plan.
        For the /execute-plan command.
        """
        plan = self.planner.get_last_plan()
        if not plan:
            return "No plan to execute. Use /plan \"goal\" to create one first."

        system_prompt = self._get_system_prompt()
        best_provider = smart_router(plan.get("goal", "")) if self.provider == "auto" else self.provider

        self.reasoner.reset()
        results, summary = self.executor.execute_plan(
            plan, best_provider, system_prompt=system_prompt
        )

        # Evaluate steps
        for step in plan["steps"]:
            step_result = results.get(step["id"], {})
            self.reasoner.evaluate_step(step, step_result, plan, results)

        self.reasoner.generate_reasoning_summary(plan, results)
        return summary

    def get_last_reasoning(self):
        """Return reasoning summary for /reasoning command."""
        return getattr(self.reasoner, "last_reasoning_text", "No reasoning data yet.")

    def get_last_trace(self):
        """Return execution trace for /trace command."""
        return self.executor.get_trace()

    def schedule_task(self, goal, when="in_5_minutes"):
        """Schedule a task for /schedule command."""
        task = self.scheduler.schedule_task(goal, when)
        if "error" in task:
            return f"Scheduling error: {task['error']}"
        return f"Task #{task['id']} scheduled: {goal}\nWhen: {when}\nScheduled for: {task.get('scheduled_for', 'N/A')}"

    def list_scheduled_tasks(self):
        """List all scheduled tasks for /tasks command."""
        return self.scheduler.list_tasks()

    def _execute_scheduled_task(self, goal):
        """Callback for scheduler to execute a task."""
        return self.process_input(goal)
