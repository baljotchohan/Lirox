"""
Lirox v0.8.5 — Autonomous Core Orchestrator

Coordinates the multi-agent loop: Planner → Executor → Researcher → Memory.
"""

import time

from lirox.agent.planner import Planner
from lirox.agent.executor import Executor
from lirox.agent.researcher import Researcher
from lirox.agent.memory import Memory          # FIX 1.8: use canonical Memory
from lirox.tools.browser import BrowserTool


class Orchestrator:
    def __init__(self):
        self.planner = Planner()
        self.executor = Executor()
        self.researcher = Researcher(BrowserTool())
        self.memory = Memory()

    def run_goal(self, goal):
        print(f"[Orchestrator] Running goal: {goal}")
        context = self.memory.get_context(goal)

        # AUTO RESEARCH TRIGGER
        if not context or "unknown" in context.lower():
            print("[Research] Triggered")
            try:
                research_data = self.researcher.research(goal)
                context += f"\nResearch:\n{research_data}"
            except Exception as e:
                print(f"[Research Error] {e}")

        # PLAN
        plan = self.planner.create_plan(goal, context)
        print(f"[Planner] Plan: {plan}")

        # EXECUTE
        results, summary = self.executor.execute_plan(plan)
        print(f"[Executor] Results: {summary}")

        # STORE MEMORY
        self.memory.store(goal, results)
        return results


class LiroxLoop:
    def __init__(self):
        self.orchestrator = Orchestrator()
        self.memory = Memory()

    def run(self, max_iterations: int = 10):
        print("🚀 Lirox Autonomous System Started")
        self.active = True
        iteration = 0

        while self.active and iteration < max_iterations:
            iteration += 1
            goals = self.memory.get_active_goals()

            # SELF TASK GENERATION
            if not goals:
                print("[System] No goals found. Creating default goal...")
                self.memory.add_goal("Explore trending AI topics and generate ideas")
                goals = self.memory.get_active_goals()

            for goal_obj in goals:
                goal = goal_obj["goal"]
                try:
                    results = self.orchestrator.run_goal(goal)
                    if isinstance(results, dict) and any(r.get("status") == "failed" for r in results.values()):
                        print(f"[System] Execution failed on iteration {iteration}. Retrying...")
                        time.sleep(2 * iteration)
                    else:
                        pass
                except Exception as e:
                    print(f"[Error] {e}")
                    time.sleep(3)

            time.sleep(5)

        if iteration >= max_iterations:
            print("[!] Safety Abort: Max autonomous iterations reached.")
            self.active = False


def decide_tool(task, llm):
    response = llm(f"Which tool should be used for this task: {task}?")
    return response


STATE = ["thinking", "planning", "executing"]
