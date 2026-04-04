import asyncio
import json
from lirox.agent.core import LiroxAgent
from lirox.server.state import GlobalState

async def test_research_synthesis():
    print("🧪 Testing Lirox v2.0 Research Synthesis...")
    
    agent = LiroxAgent()
    
    # Test case: Deep research (Should trigger research_topic in browser.py)
    # The new executor.py logic uses any(k in task_lower for k in ["research", "deep dive", ...])
    goal = "Research the latest status of Gemini 1.5 Pro and Gemini 1.5 Flash models"
    
    print(f"📡 Dispatching goal: {goal}")
    
    # Simulate the Think-Plan-Execute-Reflect loop
    plan = agent.planner.create_plan(goal)
    print(f"📋 Plan created with {len(plan['steps'])} steps.")
    
    # Ensure at least one step uses the browser
    has_browser = any("browser" in step.get("tools", []) for step in plan["steps"])
    if not has_browser:
        print("⚠️ Warning: Planner did not select browser tool. Overriding for test.")
        plan["steps"][0]["tools"] = ["browser"]

    # Execute
    results, summary = agent.executor.execute_plan(plan)
    
    print("\n📝 Research Summary:")
    print("-" * 40)
    print(summary)
    print("-" * 40)
    
    # Check if results contain synthesized content
    found_synthesis = False
    for res in results.values():
        if "Synthesized Research" in res.get("output", "") or "Source Quality Score" in res.get("output", ""):
            found_synthesis = True
            break
            
    if found_synthesis:
        print("✅ SUCCESS: Found synthesized content from multi-source research.")
    else:
        print("❌ FAILURE: Synthesized content not found in execution results.")

if __name__ == "__main__":
    asyncio.run(test_research_synthesis())
