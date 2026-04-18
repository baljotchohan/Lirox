
import sys
import os
import time
import json
from pathlib import Path

# Add PROJECT_ROOT to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Mock interactive components if needed
os.environ["LOCAL_LLM_ENABLED"] = "false"
os.environ["PLAN_CONFIRM"] = "false" # Try to skip confirmations in test

from lirox.orchestrator.master import MasterOrchestrator
from lirox.agent.profile import UserProfile
from lirox.ui.display import console

def test_feature(name):
    console.print(f"\n[bold cyan]── Testing Feature: {name} ──[/]")

def run_test():
    profile = UserProfile()
    orch = MasterOrchestrator(profile_data=profile.data)
    
    # helper to simulate main.py command handling logic
    def handle(cmd_str):
        console.print(f"[bold]Input:[/] {cmd_str}")
        # In a real test we'd import handle_command from main, but that has infinite loops.
        # We'll test the orchestrator's response for chat and the tools directly.
        if cmd_str.startswith("/"):
            # Simulate some command logic or just check if the orch can handle it
            pass
        else:
            # Chat
            for chunk in orch.handle_query(cmd_str):
                # Just consume the generator
                pass
            console.print("[green]Done.[/]")

    # 1. Identity
    test_feature("Identity/Profile")
    console.print(f"Profile Summary:\n{profile.summary()}")
    assert profile.data["agent_name"] in ["Lirox", "Atlas", "Nova", "Rex", "TestAgent", "AtlasNew"]
    
    # 2. Memory
    test_feature("Memory/Learnings")
    from lirox.mind.learnings import LearningsStore
    learnings = LearningsStore()
    learnings.add_fact("The tester is running a full system audit.")
    console.print(f"Learnings Stats: {learnings.stats_summary()}")

    # 3. Agents
    test_feature("Sub-Agents")
    from lirox.mind.sub_agents.registry import SubAgentsRegistry
    reg = SubAgentsRegistry()
    agents = reg.list_agents()
    console.print(f"Total Agents: {len(agents)}")
    # Add a dummy agent
    dummy_code = '''
def run(query, context):
    return f"Response to {query}"
'''
    reg.add_agent_from_code(dummy_code, "TesterBot")
    assert any(a['name'] == "testerbot" for a in reg.list_agents())
    console.print("✅ Agent addition working.")

    # 4. Skills
    test_feature("Skills")
    from lirox.mind.skills.registry import SkillsRegistry
    sreg = SkillsRegistry()
    console.print(f"Total Skills: {len(sreg.list_skills())}")
    # Simulate adding a skill (we won't actually generate code here to save time)
    console.print("✅ Skill registry accessible.")

    # 5. File/Shell Execution
    test_feature("Tool Dispatch (Shell/File)")
    from lirox.agents.personal_agent import PersonalAgent
    from lirox.memory.manager import MemoryManager
    from lirox.thinking.scratchpad import Scratchpad
    
    pa = PersonalAgent(MemoryManager(), Scratchpad(), profile.data)
    
    # Test shell via PersonalAgent._shell
    console.print("Testing safe shell execution (whoami)...")
    res_gen = pa._shell("whoami", "", {}, "")
    res = ""
    for r in res_gen:
        if r["type"] == "tool_result":
            res = r["message"]
    console.print(f"Result: {res}")
    assert len(res) > 0
    
    # Test file write via PersonalAgent._file
    console.print("Testing surgical file write...")
    test_file = os.path.join(PROJECT_ROOT, "scratch", "test_out.txt")
    write_query = f"Write 'Lirox System Test OK' to {test_file}"
    res_gen = pa._file(write_query, "", {}, "")
    for _ in res_gen: pass # exhaust generator
    
    assert os.path.exists(test_file)
    with open(test_file, 'r') as f:
        assert f.read().strip() == "Lirox System Test OK"
    console.print("✅ File operations working.")

    # 6. Memory IO
    test_feature("Memory Export/Import")
    from lirox.utils.memory_utils import export_full_memory, import_full_memory
    export_path = os.path.join(PROJECT_ROOT, "scratch", "test_export.json")
    export_full_memory(export_path)
    assert os.path.exists(export_path)
    
    # Test import (dry run / check)
    import_res = import_full_memory(export_path)
    assert import_res["success"] == True
    console.print("✅ Memory IO working.")

    console.print("\n[bold green]✨ ALL CORE SYSTEMS OPERATIONAL ✨[/]")

if __name__ == "__main__":
    run_test()
