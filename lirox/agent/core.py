"""
Lirox v0.5 — Agent Core Orchestrator

Coordinates Reasoning, Planning, Execution, Memory, and Profile.
v0.5 Updates:
- Version bump
- Background autonomous learning (non-blocking)
- Stream-aware architecture support
"""

import threading
from lirox.agent.planner import Planner
from lirox.agent.executor import Executor
from lirox.agent.reasoner import Reasoner
from lirox.agent.memory import Memory
from lirox.agent.profile import UserProfile
from lirox.agent.scheduler import TaskScheduler
from lirox.utils.llm import generate_response
from lirox.utils.meta_parser import extract_meta
from lirox.config import APP_VERSION


class LiroxAgent:
    """The central brain of the Lirox OS."""

    def __init__(self):
        self.profile   = UserProfile()
        self.memory    = Memory()
        self.planner   = Planner()
        self.executor  = Executor()
        self.reasoner  = Reasoner()
        self.scheduler = TaskScheduler()
        
        # Link scheduler to this agent's task processor
        self.scheduler.execute_callback = self.process_task
        
        # Version tracking
        self.version = APP_VERSION

    def _get_system_prompt(self) -> str:
        return self.profile.to_advanced_system_prompt()

    def chat(self, user_input: str, provider: str = "auto") -> str:
        """Simple chat response with context and personalization."""
        system_prompt = self._get_system_prompt()
        context       = self.memory.get_relevant_context(user_input)
        full_prompt   = f"{context}User: {user_input}\nAssistant:"
        
        response = generate_response(full_prompt, provider, system_prompt=system_prompt)
        
        # Strip metadata before saving to memory and passive learning
        clean_text, _ = extract_meta(response)
        
        # Save to memory
        self.memory.save_memory("user", user_input)
        self.memory.save_memory("assistant", clean_text)
        
        # Passive learning in background thread (non-blocking)
        threading.Thread(
            target=self._try_learn_from_exchange, 
            args=(user_input, clean_text), 
            daemon=True
        ).start()
        
        return response

    def process_task(self, goal: str, provider: str = "auto") -> dict:
        """
        Full autonomous task cycle:
        1. Reason/Think (Reasoning Trace)
        2. Plan (Step-by-step breakdown)
        3. Execute (Parallel/Sequential tools)
        4. Reflect (Evaluate results)
        """
        import time
        start_time = time.time()
        
        system_prompt = self._get_system_prompt()
        
        # 1. Internal Reasoning Trace
        thought = self.reasoner.generate_thought_trace(goal)
        
        # 2. Planning
        plan = self.planner.create_plan(goal, context=thought)
        
        # 3. Execution
        results, summary = self.executor.execute_plan(plan, provider, system_prompt)
        
        # 4. Evaluation & Reflection
        reflection = self.reasoner.generate_reasoning_summary(plan, results)
        
        duration = time.time() - start_time
        
        # Save results to memory and track execution
        self.memory.save_memory("user", f"TASK: {goal}")
        self.memory.save_memory("assistant", f"SUMMARY: {summary}\n\nREFLECTION: {reflection.get('reflection', {}).get('suggestion', '')}")
        
        is_success = "error" not in summary.lower() and "failed" not in summary.lower()
        self.profile.track_task_execution(goal, is_success, duration)
        
        return {
            "goal":       goal,
            "plan":       plan,
            "results":    results,
            "summary":    summary,
            "reflection": reflection,
            "thought":    thought
        }

    def _try_learn_from_exchange(self, user_msg: str, assistant_msg: str):
        """Passive learning: extract facts about the user from the conversation."""
        prompt = (
            "Extract any NEW, specific facts about the user's preferences, work, "
            "or identity from this exchange. Format as a bullet list of short facts. "
            "If no new facts, reply 'NONE'.\n\n"
            f"User: {user_msg}\n"
            f"Assistant: {assistant_msg}\n\n"
            "Facts:"
        )
        try:
            response = generate_response(prompt, provider="groq", system_prompt="You are a passive observer.")
            if response and "NONE" not in response.upper():
                facts = [f.strip("- ").strip() for f in response.split("\n") if f.strip("- ")]
                for fact in facts:
                    self.profile.add_learned_fact(fact)
        except Exception:
            pass
