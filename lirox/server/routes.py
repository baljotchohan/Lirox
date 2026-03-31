from fastapi import APIRouter, HTTPException, Depends
from lirox.server.models import ChatRequest, ProfileUpdate, GoalRequest, KeysUpdate, PlanRequest, SettingsUpdate, ConfirmRequest
from lirox.server.state import get_agent, get_state
from lirox.utils.llm import available_providers, is_task_request, smart_router
from lirox.agent.policy import policy_engine
from lirox.config import PROJECT_ROOT, MEMORY_LIMIT
from dotenv import set_key
import os
import threading

router = APIRouter(prefix="/api")

@router.get("/health")
def health():
    return {"status": "ok", "version": "0.4.0-alpha"}

@router.get("/profile")
def get_profile():
    return get_agent().profile.data

@router.post("/profile")
def update_profile(data: ProfileUpdate):
    agent = get_agent()
    for field, value in data.dict(exclude_unset=True).items():
        agent.profile.update(field, value)
    return agent.profile.data

@router.get("/providers")
def get_providers():
    return {"available": available_providers(), "all": ["gemini", "groq", "openai", "openrouter", "deepseek"]}

@router.post("/chat")
def chat(data: ChatRequest):
    agent = get_agent()
    state = get_state()
    
    if state.execution_lock.locked():
        raise HTTPException(status_code=409, detail="Agent is currently busy.")

    # 1. Think & Classify
    provider = data.provider if data.provider != "auto" else smart_router(data.message)
    is_task = is_task_request(data.message, provider)
    
    if not is_task:
        with state.execution_lock:
            state.current_task_status = "thinking"
            state.current_thought = f"Analyzing: {data.message[:50]}..."
            response = agent.process_input(data.message)
            state.current_task_status = "idle"
            state.current_thought = ""
            return {"response": response, "type": "chat"}

    # 2. Planning Phase with Thinking Trace
    with state.execution_lock:
        state.current_task_status = "thinking"
        state.current_thought = agent.reasoner.generate_thought_trace(data.message)
        
        state.current_task_status = "planning"
        plan = agent.planner.create_plan(data.message)
        state.last_plan = plan
        
        # 3. Policy Check
        policy = policy_engine.evaluate_risk(plan)
        if not policy["auto_execute"]:
            state.pending_confirmation = True
            state.pending_plan = plan
            state.current_task_status = "awaiting_confirmation"
            return {
                "type": "task_pending",
                "plan": plan,
                "policy": policy,
                "thought": state.current_thought,
                "message": "This task requires your confirmation before proceeding."
            }

        # 4. Auto-Execution
        state.current_task_status = "executing"
        results, summary = agent.executor.execute_plan(plan, provider)
        
        # Extract sources from results for the UI
        sources = []
        for res in results.values():
            if isinstance(res, dict) and "metadata" in res:
                sources.extend(res["metadata"].get("sources", []))
        
        agent.reasoner.reset()
        for step in plan["steps"]:
            agent.reasoner.evaluate_step(step, results.get(step["id"], {}), plan, results)
        
        reflection = agent.reasoner.generate_reasoning_summary(plan, results)
        state.current_task_status = "completed"
        return {
            "type": "task_complete",
            "response": summary,
            "reflection": reflection,
            "plan": plan,
            "thought": state.current_thought,
            "sources": sources[:6] # Top 6 unique sources
        }

@router.post("/confirm-run")
def confirm_run(data: ConfirmRequest):
    state = get_state()
    agent = get_agent()
    
    if not state.pending_plan:
        raise HTTPException(status_code=400, detail="No pending plan to confirm.")
        
    if not data.confirmed:
        state.pending_plan = None
        state.pending_confirmation = False
        state.current_task_status = "idle"
        return {"message": "Plan rejected."}

    def run_in_background():
        with state.execution_lock:
            state.current_task_status = "executing"
            plan = state.pending_plan
            provider = smart_router(plan["goal"])
            results, summary = agent.executor.execute_plan(plan, provider)
            agent.reasoner.reset()
            for step in plan["steps"]:
                 agent.reasoner.evaluate_step(step, results.get(step["id"], {}), plan, results)
            agent.reasoner.generate_reasoning_summary(plan, results)
            state.pending_plan = None
            state.pending_confirmation = False
            state.current_task_status = "completed"

    thread = threading.Thread(target=run_in_background)
    thread.start()
    return {"message": "Execution started in background."}

@router.get("/status")
def get_status():
    state = get_state()
    agent = get_agent()
    return {
        "status": state.current_task_status,
        "thought": state.current_thought,
        "pending_confirmation": state.pending_confirmation,
        "pending_plan": state.pending_plan,
        "last_reasoning": getattr(agent.reasoner, "last_reasoning", None)
    }

@router.get("/trace")
def get_trace():
    return {"trace": get_agent().get_last_trace()}

@router.get("/settings")
def get_settings():
    agent = get_agent()
    return {
        "allow_terminal_tool": getattr(agent.executor, "allow_terminal_tool", False),
        "memory_limit": MEMORY_LIMIT,
        "default_provider": agent.provider,
        "auto_execute_max_steps": policy_engine.max_auto_steps,
        "auto_execute_max_time": policy_engine.max_auto_time_mins
    }

@router.post("/settings")
def update_settings(data: SettingsUpdate):
    agent = get_agent()
    agent.executor.allow_terminal_tool = data.allow_terminal_tool
    agent.set_provider(data.default_provider)
    policy_engine.max_auto_steps = data.auto_execute_max_steps
    policy_engine.max_auto_time_mins = data.auto_execute_max_time
    return {"status": "success"}
