"""
Real multi-agent thinking with actual LLM calls
Every agent thinks independently, then they debate
"""

import time
from typing import Dict, List, Any
from lirox.utils.llm import generate_response


class RealThinkingEngine:
    """
    ACTUAL multi-agent reasoning with LLM calls
    Not simulated, not hardcoded - REAL thinking
    """
    
    def __init__(self, provider="auto"):
        self.provider = provider
        self.agents = {
            'Architect': ArchitectAgent(),
            'Builder': BuilderAgent(),
            'Researcher': ResearcherAgent(),
            'Executor': ExecutorAgent(),
            'Verifier': VerifierAgent(),
        }
    
    def think_and_decide(self, task: str, context: str = "") -> Dict[str, Any]:
        """
        Complete thinking pipeline:
        1. Each agent analyzes with REAL LLM call
        2. Agents debate differences
        3. Synthesize final decision
        """
        
        start_time = time.time()
        
        # PHASE 1: EACH AGENT THINKS (REAL LLM CALLS)
        agent_views = {}
        for agent_name, agent in self.agents.items():
            view = agent.analyze(task, context, provider=self.provider)
            agent_views[agent_name] = view
        
        # PHASE 2: DETECT DISAGREEMENTS (REAL ANALYSIS)
        debate = self._run_real_debate(agent_views)
        
        # PHASE 3: SYNTHESIZE (REAL LLM SYNTHESIS)
        synthesis = self._synthesize_decision(agent_views, debate)
        
        elapsed = round(time.time() - start_time, 2)
        
        return {
            'agent_views': agent_views,
            'debate': debate,
            'synthesis': synthesis,
            'decision': synthesis['final_decision'],
            'time_taken': elapsed,
            'reasoning_shown': True,
        }
    
    def _run_real_debate(self, agent_views: Dict[str, Dict]) -> Dict:
        """
        REAL debate - agents challenge each other via LLM
        """
        
        debate_log = []
        
        # Extract positions
        positions = {
            name: view['summary']
            for name, view in agent_views.items()
        }
        
        # Find disagreements
        for agent_a, pos_a in positions.items():
            for agent_b, pos_b in positions.items():
                if agent_a >= agent_b:  # Avoid duplicates
                    continue
                
                # Ask LLM: do these positions conflict?
                conflict_check = generate_response(
                    f"Position A ({agent_a}): {pos_a}\n"
                    f"Position B ({agent_b}): {pos_b}\n\n"
                    "Do these positions conflict? If yes, explain the conflict in one sentence.",
                    provider=self.provider,
                    system_prompt="You are a debate analyzer. Output 'NO CONFLICT' or 'CONFLICT: <explanation>'"
                )
                
                if "CONFLICT:" in conflict_check:
                    conflict_text = conflict_check.replace("CONFLICT:", "").strip()
                    debate_log.append({
                        'agent_a': agent_a,
                        'agent_b': agent_b,
                        'conflict': conflict_text,
                        'resolution': self._resolve_conflict(agent_a, pos_a, agent_b, pos_b)
                    })
        
        return {
            'conflicts': debate_log,
            'summary': f"Found {len(debate_log)} disagreements, all resolved"
        }
    
    def _resolve_conflict(self, agent_a: str, pos_a: str, agent_b: str, pos_b: str) -> str:
        """
        Use LLM to resolve conflict between two positions
        """
        
        resolution = generate_response(
            f"{agent_a} says: {pos_a}\n"
            f"{agent_b} counters: {pos_b}\n\n"
            "What's the best synthesis of these two positions? Give a one-sentence resolution.",
            provider=self.provider,
            system_prompt="You are a mediator finding middle ground between conflicting views."
        )
        
        return resolution.strip()
    
    def _synthesize_decision(self, agent_views: Dict, debate: Dict) -> Dict:
        """
        REAL synthesis using LLM to combine all views
        """
        
        # Build synthesis prompt from all agent views
        views_text = "\n".join([
            f"{name}: {view['summary']}"
            for name, view in agent_views.items()
        ])
        
        conflicts_text = "\n".join([
            f"Conflict: {c['conflict']} → Resolved: {c['resolution']}"
            for c in debate['conflicts']
        ]) if debate['conflicts'] else "No conflicts"
        
        synthesis_prompt = f"""
You are synthesizing multiple expert perspectives into ONE final decision.

AGENT VIEWS:
{views_text}

DEBATES:
{conflicts_text}

Synthesize these into:
1. What we should do (one sentence)
2. Why (2-3 sentences)
3. Confidence level (0-100%)

Output format:
DECISION: <action>
REASONING: <why>
CONFIDENCE: <0-100>
"""
        
        response = generate_response(
            synthesis_prompt,
            provider=self.provider,
            system_prompt="You are a strategic decision synthesizer. Be concise and actionable."
        )
        
        # Parse response
        lines = response.split('\n')
        decision = ""
        reasoning = ""
        confidence = 0
        
        for line in lines:
            if line.startswith("DECISION:"):
                decision = line.replace("DECISION:", "").strip()
            elif line.startswith("REASONING:"):
                reasoning = line.replace("REASONING:", "").strip()
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = int(line.replace("CONFIDENCE:", "").strip().replace("%", ""))
                except:
                    confidence = 75
        
        return {
            'final_decision': decision,
            'reasoning': reasoning,
            'confidence': confidence,
            'all_views_considered': len(agent_views),
        }


class ArchitectAgent:
    """Architect perspective - scalability, design, long-term"""
    
    def analyze(self, task: str, context: str, provider="auto") -> Dict:
        prompt = f"""
Task: {task}
Context: {context}

Analyze from ARCHITECT perspective:
- Will this scale to 1M users?
- Is this the right long-term design?
- What's the technical debt?
- What's the 10-year implication?

Respond with:
SUMMARY: <one sentence>
ANALYSIS: <2-3 bullet points>
CONCERNS: <1-2 sentences>
"""
        
        response = generate_response(
            prompt,
            provider=provider,
            system_prompt="You are a senior software architect focused on scalability and design."
        )
        
        return self._parse_response(response)
    
    def _parse_response(self, text: str) -> Dict:
        lines = text.split('\n')
        result = {'summary': '', 'analysis': '', 'concerns': ''}
        
        for line in lines:
            if line.startswith("SUMMARY:"):
                result['summary'] = line.replace("SUMMARY:", "").strip()
            elif line.startswith("ANALYSIS:"):
                result['analysis'] = line.replace("ANALYSIS:", "").strip()
            elif line.startswith("CONCERNS:"):
                result['concerns'] = line.replace("CONCERNS:", "").strip()
        
        if not result['summary']:
            result['summary'] = text[:100]
        
        return result


class BuilderAgent:
    """Builder perspective - execution, timeline, resources"""
    
    def analyze(self, task: str, context: str, provider="auto") -> Dict:
        prompt = f"""
Task: {task}
Context: {context}

Analyze from BUILDER perspective:
- Can we actually build this?
- How long will it take (realistically)?
- What resources do we need?
- What are the blockers?

Respond with:
SUMMARY: <one sentence>
ANALYSIS: <2-3 bullet points>
CONCERNS: <1-2 sentences>
"""
        
        response = generate_response(
            prompt,
            provider=provider,
            system_prompt="You are a pragmatic engineering lead focused on shipping."
        )
        
        return self._parse_response(response)
    
    def _parse_response(self, text: str) -> Dict:
        lines = text.split('\n')
        result = {'summary': '', 'analysis': '', 'concerns': ''}
        
        for line in lines:
            if line.startswith("SUMMARY:"):
                result['summary'] = line.replace("SUMMARY:", "").strip()
            elif line.startswith("ANALYSIS:"):
                result['analysis'] = line.replace("ANALYSIS:", "").strip()
            elif line.startswith("CONCERNS:"):
                result['concerns'] = line.replace("CONCERNS:", "").strip()
        
        if not result['summary']:
            result['summary'] = text[:100]
        
        return result


class ResearcherAgent:
    """Researcher perspective - data, evidence, best practices"""
    
    def analyze(self, task: str, context: str, provider="auto") -> Dict:
        prompt = f"""
Task: {task}
Context: {context}

Analyze from RESEARCHER perspective:
- What do we know about this topic?
- What are the best practices?
- What does the data say?
- What patterns should we follow?

Respond with:
SUMMARY: <one sentence>
ANALYSIS: <2-3 bullet points>
CONCERNS: <1-2 sentences>
"""
        
        response = generate_response(
            prompt,
            provider=provider,
            system_prompt="You are a research analyst focused on evidence and best practices."
        )
        
        return self._parse_response(response)
    
    def _parse_response(self, text: str) -> Dict:
        lines = text.split('\n')
        result = {'summary': '', 'analysis': '', 'concerns': ''}
        
        for line in lines:
            if line.startswith("SUMMARY:"):
                result['summary'] = line.replace("SUMMARY:", "").strip()
            elif line.startswith("ANALYSIS:"):
                result['analysis'] = line.replace("ANALYSIS:", "").strip()
            elif line.startswith("CONCERNS:"):
                result['concerns'] = line.replace("CONCERNS:", "").strip()
        
        if not result['summary']:
            result['summary'] = text[:100]
        
        return result


class ExecutorAgent:
    """Executor perspective - planning, steps, timeline"""
    
    def analyze(self, task: str, context: str, provider="auto") -> Dict:
        prompt = f"""
Task: {task}
Context: {context}

Analyze from EXECUTOR perspective:
- What are the concrete steps?
- What's the timeline?
- What's the success criteria?
- How do we measure progress?

Respond with:
SUMMARY: <one sentence>
ANALYSIS: <2-3 bullet points>
CONCERNS: <1-2 sentences>
"""
        
        response = generate_response(
            prompt,
            provider=provider,
            system_prompt="You are a project executor focused on concrete plans and milestones."
        )
        
        return self._parse_response(response)
    
    def _parse_response(self, text: str) -> Dict:
        lines = text.split('\n')
        result = {'summary': '', 'analysis': '', 'concerns': ''}
        
        for line in lines:
            if line.startswith("SUMMARY:"):
                result['summary'] = line.replace("SUMMARY:", "").strip()
            elif line.startswith("ANALYSIS:"):
                result['analysis'] = line.replace("ANALYSIS:", "").strip()
            elif line.startswith("CONCERNS:"):
                result['concerns'] = line.replace("CONCERNS:", "").strip()
        
        if not result['summary']:
            result['summary'] = text[:100]
        
        return result


class VerifierAgent:
    """Verifier perspective - quality, testing, validation"""
    
    def analyze(self, task: str, context: str, provider="auto") -> Dict:
        prompt = f"""
Task: {task}
Context: {context}

Analyze from VERIFIER perspective:
- How do we verify this works?
- What could go wrong?
- What tests do we need?
- What's the quality bar?

Respond with:
SUMMARY: <one sentence>
ANALYSIS: <2-3 bullet points>
CONCERNS: <1-2 sentences>
"""
        
        response = generate_response(
            prompt,
            provider=provider,
            system_prompt="You are a quality engineer focused on verification and testing."
        )
        
        return self._parse_response(response)
    
    def _parse_response(self, text: str) -> Dict:
        lines = text.split('\n')
        result = {'summary': '', 'analysis': '', 'concerns': ''}
        
        for line in lines:
            if line.startswith("SUMMARY:"):
                result['summary'] = line.replace("SUMMARY:", "").strip()
            elif line.startswith("ANALYSIS:"):
                result['analysis'] = line.replace("ANALYSIS:", "").strip()
            elif line.startswith("CONCERNS:"):
                result['concerns'] = line.replace("CONCERNS:", "").strip()
        
        if not result['summary']:
            result['summary'] = text[:100]
        
        return result
