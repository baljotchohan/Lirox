from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ChatRequest(BaseModel):
    message: str
    provider: Optional[str] = "auto"

class ProfileUpdate(BaseModel):
    agent_name: Optional[str] = None
    user_name: Optional[str] = None
    niche: Optional[str] = None
    tone: Optional[str] = None
    user_context: Optional[str] = None

class GoalRequest(BaseModel):
    goal: str

class KeysUpdate(BaseModel):
    gemini: Optional[str] = None
    groq: Optional[str] = None
    openai: Optional[str] = None
    openrouter: Optional[str] = None
    deepseek: Optional[str] = None
    nvidia: Optional[str] = None

class PlanRequest(BaseModel):
    goal: str

class ConfirmRequest(BaseModel):
    confirmed: bool
    plan_id: Optional[str] = None

class SettingsUpdate(BaseModel):
    allow_terminal_tool: bool
    memory_limit: int
    default_provider: str
    auto_execute_max_steps: Optional[int] = 5
    auto_execute_max_time: Optional[int] = 2
