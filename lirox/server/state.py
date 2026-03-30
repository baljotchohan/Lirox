from lirox.agent.core import LiroxAgent
import threading

class GlobalState:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.agent = LiroxAgent()
        self.execution_lock = threading.Lock()
        self.last_plan = None
        self.last_results = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

def get_agent():
    return GlobalState.get_instance().agent

def get_state():
    return GlobalState.get_instance()
