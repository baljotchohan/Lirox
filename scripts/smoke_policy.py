import os
from lirox.agent.policy import policy_engine

def test_policy():
    print("🧪 Testing Lirox v2.0 Policy Engine...")
    
    # Test Case 1: Simple Search (Should auto-execute)
    low_risk_plan = {
        "goal": "Find latest Llama 3 models",
        "steps": [
            {"id": 1, "task": "Search web for Llama 3", "tools": ["browser"]}
        ]
    }
    res1 = policy_engine.evaluate_risk(low_risk_plan)
    assert res1["auto_execute"] is True
    print("✅ Case 1 (Research): Auto-execute allowed.")

    # Test Case 2: Terminal Command (Should NOT auto-execute)
    high_risk_plan = {
        "goal": "Install fastapi",
        "steps": [
            {"id": 1, "task": "Run pip install fastapi", "tools": ["terminal"]}
        ]
    }
    res2 = policy_engine.evaluate_risk(high_risk_plan)
    assert res2["auto_execute"] is False
    assert "terminal" in res2["reason"].lower()
    print("✅ Case 2 (Terminal): Auto-execute blocked (Security).")

    # Test Case 3: Complex Task (Should NOT auto-execute)
    complex_plan = {
        "goal": "Build a website",
        "steps": [{"id": i, "task": f"Step {i}", "tools": ["browser"]} for i in range(10)]
    }
    res3 = policy_engine.evaluate_risk(complex_plan)
    assert res3["auto_execute"] is False
    assert "complex" in res3["reason"].lower()
    print("✅ Case 3 (Complexity): Auto-execute blocked (Threshold).")

if __name__ == "__main__":
    try:
        test_policy()
        print("\n🎉 ALL POLICY TESTS PASSED!")
    except AssertionError as e:
        print(f"❌ TEST FAILED: {str(e)}")
