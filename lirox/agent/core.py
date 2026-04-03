"""
Lirox v0.5 — Agent Core Orchestrator

Coordinates Reasoning, Planning, Execution, Memory, and Profile.
v0.5 Updates:
- Version bump
- Background autonomous learning (non-blocking)
- Stream-aware architecture support
"""

import threading
from lirox.agent.memory import Memory
from lirox.agent.profile import UserProfile
from lirox.agent.learning_engine import LearningEngine
from lirox.utils.llm import generate_response
from lirox.utils.meta_parser import extract_meta
from lirox.config import APP_VERSION


class LiroxAgent:
    """The central brain of the Lirox OS."""

    def __init__(self):
        self.profile   = UserProfile()
        self.memory    = Memory()
        self.learning  = LearningEngine()

        # Version tracking
        self.version = APP_VERSION

        # Start learning session
        self.learning.on_session_start()

    def _get_system_prompt(self) -> str:
        base = self.profile.to_advanced_system_prompt()
        boost = self.learning.get_context_boost()
        return base + boost

    def chat(self, user_input: str, provider: str = "auto") -> str:
        """Simple chat response with context and personalization."""
        system_prompt = self._get_system_prompt()
        context       = self.memory.get_relevant_context(user_input)
        full_prompt   = f"{context}User: {user_input}\nAssistant:"
        
        response = generate_response(full_prompt, provider, system_prompt=system_prompt)
        
        # Strip metadata before saving to memory and passive learning
        clean_text, _ = extract_meta(response)
        
        # Save to memory
        self.memory.save_memory("user", user_input)
        self.memory.save_memory("assistant", clean_text)
        
        # Passive learning: profile facts
        threading.Thread(
            target=self._try_learn_from_exchange,
            args=(user_input, clean_text),
            daemon=True
        ).start()

        # Learning engine: intent/topic/satisfaction tracking
        if hasattr(self, 'learning'):
            threading.Thread(
                target=self.learning.on_interaction,
                args=(user_input, clean_text),
                daemon=True
            ).start()

        return response

    def _try_learn_from_exchange(self, user_msg: str, assistant_msg: str):
        """Passive learning: extract facts about the user from the conversation."""
        prompt = (
            "Extract any NEW, specific facts about the user's preferences, work, "
            "or identity from this exchange. Format as a bullet list of short facts. "
            "If no new facts, reply 'NONE'.\n\n"
            f"User: {user_msg}\n"
            f"Assistant: {assistant_msg}\n\n"
            "Facts:"
        )
        try:
            response = generate_response(prompt, provider="groq", system_prompt="You are a passive observer.")
            if response and "NONE" not in response.upper():
                facts = [f.strip("- ").strip() for f in response.split("\n") if f.strip("- ")]
                for fact in facts:
                    self.profile.add_learned_fact(fact)
        except Exception:
            pass
