import json
from lirox.agent.memory import Memory
from lirox.agent.planner import Planner
from lirox.agent.executor import Executor
from lirox.agent.profile import UserProfile
from lirox.utils.llm import generate_response, smart_router, is_task_request
from lirox.ui.display import AgentSpinner, agent_panel, execute_panel, plan_panel, update_plan_step

class LiroxAgent:
    def __init__(self, provider="openai"):
        self.provider = provider
        self.memory = Memory()
        self.planner = Planner(provider)
        self.executor = Executor()
        self.profile = UserProfile()

    def set_provider(self, provider):
        self.provider = provider
        self.planner.set_provider(provider)

    def _get_system_prompt(self):
        """Always pull fresh from profile so updates are reflected immediately."""
        return self.profile.to_system_prompt()

    def _try_learn_from_exchange(self, user_input, response):
        """
        Passively extracts facts about the user from the exchange.
        Runs silently in the background.
        """
        learn_prompt = f"""
        From this conversation exchange, extract any NEW facts about the user 
        that should be remembered long-term. Return a JSON list of strings.
        If nothing new was learned, return an empty list [].
        Only extract concrete facts: names, tools they use, preferences, goals mentioned.

        Exchange:
        User: {user_input}
        Agent: {response}

        Return ONLY valid JSON like: ["fact 1", "fact 2"]
        """
        try:
            # Use fast provider for background learning
            raw_facts = generate_response(learn_prompt, "groq", system_prompt="You are a JSON extractor.")
            # Simple cleaning for common LLM clutter
            if "[" in raw_facts and "]" in raw_facts:
                json_part = raw_facts[raw_facts.find("["):raw_facts.rfind("]")+1]
                facts = json.loads(json_part)
                for fact in facts:
                    if isinstance(fact, str) and len(fact) < 200:
                        self.profile.add_learned_fact(fact)
        except Exception as e:
            # Silent failure for background task
            pass

    def process_input(self, user_input):
        system_prompt = self._get_system_prompt()
        context = self.memory.get_context()
        agent_name = self.profile.data.get("agent_name", "Lirox")

        # Route to best provider based on content
        best_provider = smart_router(user_input) if self.provider == "auto" else self.provider

        with AgentSpinner(agent_name) as spinner:
            # Detect task vs chat
            if is_task_request(user_input, best_provider):
                # Planning phase
                plan = self.planner.create_plan(user_input, system_prompt=system_prompt)
                
                # Turn off spinner for interactive execution display
                spinner.status.stop()
                
                plan_panel(plan)
                results = self.executor.execute_plan(plan, best_provider, system_prompt=system_prompt)
                final_response = f"Task completed. Here's a summary of what I did:\n\n{results}"
            else:
                # Chat phase
                full_prompt = f"{context}User: {user_input}\nAssistant:"
                final_response = generate_response(full_prompt, best_provider, system_prompt=system_prompt)

        # Save to memory
        self.memory.save_memory("user", user_input)
        error_phrases = ["API key missing", "Unknown provider", "Error:", "Timeout"]
        if not any(e in final_response for e in error_phrases):
            self.memory.save_memory("assistant", final_response)

        # Passively learn from the exchange
        self._try_learn_from_exchange(user_input, final_response)

        return final_response
