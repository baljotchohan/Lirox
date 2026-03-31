from lirox.agent.core import LiroxAgent
import threading
import sys

class GlobalState:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        try:
            self.agent = LiroxAgent()
            self.init_error = None
        except Exception as e:
            print(f"[LIROX WARNING] Agent init failed: {e}", file=sys.stderr)
            self.agent = None
            self.init_error = str(e)
        self.execution_lock = threading.Lock()
        self.last_plan = None
        self.last_results = None
        self.pending_confirmation = False
        self.pending_plan = None
        self.current_task_status = "idle"  # idle, thinking, planning, executing, completed
        self.current_thought = ""

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

def get_agent():
    state = GlobalState.get_instance()
    if state.agent is None:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail=f"Agent not initialized: {state.init_error}. Please check your .env configuration."
        )
    return state.agent

def get_state():
    return GlobalState.get_instance()
