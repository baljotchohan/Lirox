import time

from lirox.agent.planner import Planner
from lirox.agent.executor import Executor
from lirox.agent.researcher import Researcher
from lirox.tools.browser import BrowserTool

class Memory:
    def __init__(self):
        self.data = {
            "goals": [],
            "history": [],
            "learnings": []
        }

    def add_goal(self, goal):
        self.data["goals"].append({
            "goal": goal,
            "status": "active"
        })

    def get_active_goals(self):
        return [g for g in self.data["goals"] if g["status"] == "active"]

    def store(self, goal, result):
        self.data["history"].append({
            "goal": goal,
            "result": result
        })

    def get_context(self, goal):
        return str(self.data["history"][-5:])

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

    def run(self):
        print("🚀 Lirox Autonomous System Started")
        while True:
            goals = self.memory.get_active_goals()
            
            # SELF TASK GENERATION
            if not goals:
                print("[System] No goals found. Creating default goal...")
                self.memory.add_goal("Explore trending AI topics and generate ideas")
                goals = self.memory.get_active_goals()
            
            for goal_obj in goals:
                goal = goal_obj["goal"]
                try:
                    self.orchestrator.run_goal(goal)
                except Exception as e:
                    print(f"[Error] {e}")
            
            time.sleep(30)  # loop delay

def decide_tool(task, llm):
    response = llm(f"Which tool should be used for this task: {task}?")
    return response

STATE = ["thinking", "planning", "executing"]

if __name__ == "__main__":
    memory = Memory()
    
    # INITIAL GOAL
    memory.add_goal("Grow a YouTube channel to 1M subscribers using AI automation")

    loop = LiroxLoop()
    loop.run()
