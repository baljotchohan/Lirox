from fastapi import APIRouter, HTTPException, Depends
from lirox.server.models import ChatRequest, ProfileUpdate, GoalRequest, KeysUpdate, PlanRequest, SettingsUpdate
from lirox.server.state import get_agent, get_state
from lirox.utils.llm import available_providers
from lirox.config import PROJECT_ROOT, MEMORY_LIMIT
from dotenv import set_key
import os

router = APIRouter(prefix="/api")

@router.get("/health")
def health():
    return {"status": "ok", "version": "0.3.1"}

@router.get("/profile")
def get_profile():
    agent = get_agent()
    return agent.profile.data

@router.post("/profile")
def update_profile(data: ProfileUpdate):
    agent = get_agent()
    if data.agent_name: agent.profile.update("agent_name", data.agent_name)
    if data.user_name: agent.profile.update("user_name", data.user_name)
    if data.niche: agent.profile.update("niche", data.niche)
    if data.tone: agent.profile.update("tone", data.tone)
    if data.user_context: agent.profile.update("user_context", data.user_context)
    return agent.profile.data

@router.post("/goals")
def add_goal(data: GoalRequest):
    agent = get_agent()
    agent.profile.add_goal(data.goal)
    return agent.profile.data

@router.get("/providers")
def get_providers():
    return {
        "available": available_providers(),
        "all": ["gemini", "groq", "openai", "openrouter", "deepseek"]
    }

@router.post("/keys")
def update_keys(data: KeysUpdate):
    env_path = os.path.join(PROJECT_ROOT, "../../.env")
    # Resolve to absolute path
    env_path = os.path.abspath(env_path)
    
    mapping = {
        "gemini": "GEMINI_API_KEY",
        "groq": "GROQ_API_KEY",
        "openai": "OPENAI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY"
    }
    
    updated = []
    for key, env_var in mapping.items():
        val = getattr(data, key)
        if val:
            set_key(env_path, env_var, val)
            os.environ[env_var] = val
            updated.append(key)
    
    return {"status": "success", "updated": updated}

@router.post("/chat")
def chat(data: ChatRequest):
    agent = get_agent()
    state = get_state()
    
    with state.execution_lock:
        response = agent.process_input(data.message)
        return {"response": response}

@router.post("/plan")
def create_plan(data: PlanRequest):
    agent = get_agent()
    state = get_state()
    
    with state.execution_lock:
        plan = agent.show_plan(data.goal)
        state.last_plan = plan
        return plan

@router.post("/execute-plan")
def execute_plan():
    agent = get_agent()
    state = get_state()
    
    if not state.last_plan:
        raise HTTPException(status_code=400, detail="No plan exists to execute.")
        
    with state.execution_lock:
        result = agent.execute_last_plan()
        return {"response": result}

@router.get("/trace")
def get_trace():
    agent = get_agent()
    return {"trace": agent.get_last_trace()}

@router.post("/memory/clear")
def clear_memory():
    agent = get_agent()
    msg = agent.memory.clear()
    return {"message": msg}

@router.get("/settings")
def get_settings():
    agent = get_agent()
    return {
        "allow_terminal_tool": getattr(agent.executor, "allow_terminal_tool", False),
        "memory_limit": MEMORY_LIMIT,
        "default_provider": agent.provider
    }

@router.post("/settings")
def update_settings(data: SettingsUpdate):
    agent = get_agent()
    agent.executor.allow_terminal_tool = data.allow_terminal_tool
    agent.set_provider(data.default_provider)
    # Note: memory_limit is usually fixed at load time in v0.3
    return {"status": "success"}
