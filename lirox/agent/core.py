from lirox.agent.memory import Memory
from lirox.agent.planner import Planner
from lirox.agent.executor import Executor
from lirox.utils.llm import generate_response, smart_router

class LiroxAgent:
    def __init__(self, provider="openai"):
        self.provider = provider
        self.memory = Memory()
        self.planner = Planner(provider)
        self.executor = Executor()

    def set_provider(self, provider):
        self.provider = provider
        self.planner.set_provider(provider)

    def process_input(self, user_input):
        print(f"[*] Processing: {user_input}")
        
        # Get context from memory
        context = self.memory.get_context()
        
        # Detect if it's a task or normal chat
        is_task_prompt = f"Does the following request require a plan of action or terminal commands? Return ONLY 'yes' or 'no'.\n\nRequest: {user_input}"
        is_task = generate_response(is_task_prompt, self.provider).strip().lower()
        
        if "yes" in is_task:
            print("[*] Task detected. Planning steps...")
            plan = self.planner.create_plan(user_input)
            results = self.executor.execute_plan(plan, self.provider)
            
            # Final summary of task
            final_response = f"Task completed.\n\nSummary of results:\n{results}"
        else:
            print("[*] Chat detected. Generating response...")
            full_prompt = f"{context}User: {user_input}\nAssistant:"
            final_response = generate_response(full_prompt, self.provider)

        # Save to memory (only if it's not a common error message)
        self.memory.save_memory("user", user_input)
        
        errors = ["API key missing", "Unknown provider", "Error connecting", "NVIDIA API Error"]
        if not any(err in final_response for err in errors):
            self.memory.save_memory("assistant", final_response)
        
        return final_response
