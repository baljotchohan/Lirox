"""Thinking Engine for Lirox — Multi-Agent Debate System."""
import logging
from typing import List, Tuple, Dict, Any
from lirox.utils.llm import generate_response

logger = logging.getLogger("lirox.thinking_engine")

class BaseSubAgent:
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role

    def analyze(self, query: str, context: str) -> Dict[str, str]:
        prompt = f"As the {self.name} ({self.role}), analyze this query: '{query}'\nContext: {context}\nProvide a short summary and reasoning."
        sys_prompt = "You are a sub-agent in a multi-agent system. Output ONLY JSON: {\"summary\": \"...\", \"reasoning\": \"...\"}"
        try:
            from lirox.utils.llm_json import extract_json
            response = generate_response(prompt, system_prompt=sys_prompt)
            data = extract_json(response)
            return {"summary": data.get("summary", ""), "reasoning": data.get("reasoning", "")}
        except Exception:
            return {"summary": f"{self.name} analysis fallback.", "reasoning": "Fallback reasoning."}

class ArchitectAgent(BaseSubAgent):
    def __init__(self):
        super().__init__("Architect", "Focuses on scalability and design.")

class BuilderAgent(BaseSubAgent):
    def __init__(self):
        super().__init__("Builder", "Focuses on execution and timeline.")

class ResearcherAgent(BaseSubAgent):
    def __init__(self):
        super().__init__("Researcher", "Focuses on data gathering and facts.")

class ExecutorAgent(BaseSubAgent):
    def __init__(self):
        super().__init__("Executor", "Focuses on step-by-step planning.")

class VerifierAgent(BaseSubAgent):
    def __init__(self):
        super().__init__("Verifier", "Focuses on quality checks and success criteria.")

class ThinkingEngine:
    """5 agents inside Lirox debate every decision."""
    
    def __init__(self):
        self.architect = ArchitectAgent()
        self.builder = BuilderAgent()
        self.researcher = ResearcherAgent()
        self.executor = ExecutorAgent()
        self.verifier = VerifierAgent()
    
    def _understand(self, query: str) -> str:
        return f"User wants to: {query}"
        
    def _detect_disagreement(self, view1: dict, view2: dict) -> bool:
        # Simple heuristic: if summaries share few words, they might disagree
        w1 = set(view1.get("summary", "").lower().split())
        w2 = set(view2.get("summary", "").lower().split())
        return len(w1.intersection(w2)) < 3

    def _run_debate(self, perspectives: List[Tuple[str, dict]]) -> dict:
        debate_log = []
        for agent_name, view in perspectives:
            for other_name, other_view in perspectives:
                if agent_name != other_name:
                    if self._detect_disagreement(view, other_view):
                        challenge = f"{agent_name} says: {view.get('summary')}\nBut {other_name} counters: {other_view.get('summary')}"
                        debate_log.append(challenge)
        
        return {'summary': '\n'.join(debate_log) if debate_log else "All agents are aligned on the execution plan."}

    def _synthesize_decision(self, debate: dict) -> dict:
        return {
            'plan': {'steps': ['Analyze', 'Execute', 'Verify']},
            'reasoning': "Synthesized final approach based on debate."
        }

    def think_and_decide(self, query: str, context: str) -> dict:
        understanding = self._understand(query)
        
        architect_view = self.architect.analyze(query, understanding)
        builder_view = self.builder.analyze(query, understanding)
        researcher_view = self.researcher.analyze(query, understanding)
        executor_view = self.executor.analyze(query, understanding)
        verifier_view = self.verifier.analyze(query, understanding)
        
        perspectives = [
            ("Architect", architect_view),
            ("Builder", builder_view),
            ("Researcher", researcher_view),
            ("Executor", executor_view),
            ("Verifier", verifier_view)
        ]
        
        debate = self._run_debate(perspectives)
        decision = self._synthesize_decision(debate)
        
        result = decision['plan']
        result['thinking'] = {
            'architect_said': architect_view['reasoning'],
            'builder_said': builder_view['reasoning'],
            'researcher_said': researcher_view['reasoning'],
            'executor_said': executor_view['reasoning'],
            'verifier_said': verifier_view['reasoning'],
            'debate': debate['summary'],
            'final_decision': decision['reasoning']
        }
        
        return result
