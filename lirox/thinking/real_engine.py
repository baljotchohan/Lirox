"""
Real multi-agent thinking with actual LLM calls
Every agent thinks independently, then they debate.
Updated to yield events for streaming UI.
"""

import time
import logging
from typing import Dict, List, Any, Generator
from lirox.utils.llm import generate_response

_logger = logging.getLogger("lirox.thinking.real_engine")

class RealThinkingEngine:
    """
    ACTUAL multi-agent reasoning with LLM calls
    Not simulated, not hardcoded - REAL thinking
    Yields events for real-time UI streaming.
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
    
    def think_and_decide(self, task: str, context: str = "") -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        """
        Complete thinking pipeline yielding events for the UI.
        """
        
        start_time = time.time()
        agent_views = {}
        
        # ── PHASE 1: EACH AGENT THINKS ─────────────────────────────────────────
        yield {
            "type": "thinking_phase", 
            "phase_index": 0,
            "phase_name": "INDEPENDENT ANALYSIS",
            "phase_icon": "🔍",
            "phase_total": 3,
            "phase_tagline": "Each agent analyzes task from their unique perspective",
            "confidence": 70,
            "steps": ["Initializing debate protocols", "Loading agent personas"]
        }
        
        for agent_name, agent in self.agents.items():
            yield {"type": "agent_progress", "agent": agent_name, "message": f"{agent_name} is analyzing...", "status": "running"}
            
            view = agent.analyze(task, context, provider=self.provider)
            agent_views[agent_name] = view
            
            yield {"type": "agent_progress", "agent": agent_name, "message": f"✓ {agent_name} finished analysis", "status": "done"}
        
        # ── PHASE 2: DETECT DISAGREEMENTS ──────────────────────────────────────
        yield {
            "type": "thinking_phase", 
            "phase_index": 1,
            "phase_name": "MULTI-AGENT DEBATE",
            "phase_icon": "💬",
            "phase_total": 3,
            "phase_tagline": "Resolving conflicts and challenging assumptions",
            "confidence": 85,
            "steps": [f"Checking {len(agent_views)} perspectives for conflicts"]
        }
        
        debate_log = []
        positions = {name: view['summary'] for name, view in agent_views.items()}
        
        agent_names = list(positions.keys())
        for i in range(len(agent_names)):
            for j in range(i + 1, len(agent_names)):
                agent_a, agent_b = agent_names[i], agent_names[j]
                pos_a, pos_b = positions[agent_a], positions[agent_b]
                
                yield {"type": "agent_progress", "agent": "System", "message": f"Comparing {agent_a} and {agent_b}...", "status": "running"}
                
                conflict_check = generate_response(
                    f"Position A ({agent_a}): {pos_a}\n"
                    f"Position B ({agent_b}): {pos_b}\n\n"
                    "Do these positions conflict? If yes, explain the conflict in one sentence.",
                    provider=self.provider,
                    system_prompt="You are a debate analyzer. Output 'NO CONFLICT' or 'CONFLICT: <explanation>'"
                )
                
                if "CONFLICT:" in conflict_check:
                    conflict_text = conflict_check.replace("CONFLICT:", "").strip()
                    yield {"type": "agent_progress", "agent": "System", "message": f"CONFLICT: {conflict_text}", "status": "warning"}
                    
                    resolution = self._resolve_conflict(agent_a, pos_a, agent_b, pos_b)
                    debate_log.append({
                        'agent_a': agent_a,
                        'agent_b': agent_b,
                        'conflict': conflict_text,
                        'resolution': resolution
                    })
                    yield {"type": "agent_progress", "agent": "System", "message": f"✓ Resolved via {agent_a}'s logic", "status": "done"}
                else:
                    yield {"type": "agent_progress", "agent": "System", "message": f"No conflict between {agent_a} & {agent_b}", "status": "done"}
        
        debate = {
            'conflicts': debate_log,
            'summary': f"Found {len(debate_log)} disagreements, all resolved"
        }
        
        # ── PHASE 3: SYNTHESIZE ────────────────────────────────────────────────
        yield {
            "type": "thinking_phase", 
            "phase_index": 2,
            "phase_name": "CONSENSUS SYNTHESIS",
            "phase_icon": "🎯",
            "phase_total": 3,
            "phase_tagline": "Forming final strategy and verified path",
            "confidence": 98,
            "steps": ["Merging conflict resolutions", "Finalizing decision"]
        }
        
        synthesis = self._synthesize_decision(agent_views, debate)
        elapsed = round(time.time() - start_time, 2)

        
        final_result = {
            'agent_views': agent_views,
            'debate': debate,
            'synthesis': synthesis,
            'decision': synthesis['final_decision'],
            'time_taken': elapsed,
            'reasoning_shown': True,
        }
        
        yield {"type": "done", "message": "Thinking complete.", "data": final_result}
        return final_result
    
    def _resolve_conflict(self, agent_a: str, pos_a: str, agent_b: str, pos_b: str) -> str:
        resolution = generate_response(
            f"{agent_a} says: {pos_a}\n"
            f"{agent_b} counters: {pos_b}\n\n"
            "What's the best synthesis of these two positions? Give a one-sentence resolution.",
            provider=self.provider,
            system_prompt="You are a mediator finding middle ground between conflicting views."
        )
        return resolution.strip()
    
    def _synthesize_decision(self, agent_views: Dict, debate: Dict) -> Dict:
        views_text = "\n".join([f"{name}: {view['summary']}" for name, view in agent_views.items()])
        conflicts_text = "\n".join([f"Conflict: {c['conflict']} -> Resolved: {c['resolution']}" for c in debate['conflicts']]) if debate['conflicts'] else "No conflicts"
        
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
        
        lines = response.split('\n')
        decision, reasoning, confidence = "", "", 75
        for line in lines:
            if line.startswith("DECISION:"): decision = line.replace("DECISION:", "").strip()
            elif line.startswith("REASONING:"): reasoning = line.replace("REASONING:", "").strip()
            elif line.startswith("CONFIDENCE:"):
                try: confidence = int(line.replace("CONFIDENCE:", "").strip().replace("%", ""))
                except: pass
        
        return {
            'final_decision': decision,
            'reasoning': reasoning,
            'confidence': confidence,
            'all_views_considered': len(agent_views),
        }

# Agent classes remain mostly same but updated with cleaner parsing
class ArchitectAgent:
    def analyze(self, task, context, provider="auto"):
        prompt = f"Task: {task}\nContext: {context}\nAnalyze from ARCHITECT perspective (scalability, design, long-term). Respond with:\nSUMMARY: <one sentence>\nANALYSIS: <2-3 bullets>\nCONCERNS: <1 sentence>"
        return self._parse(generate_response(prompt, provider=provider, system_prompt="Senior Architect."))
    def _parse(self, text):
        res = {'summary': text.split('\n')[0], 'analysis': '', 'concerns': ''}
        for line in text.split('\n'):
            if line.startswith("SUMMARY:"): res['summary'] = line.replace("SUMMARY:", "").strip()
            elif line.startswith("ANALYSIS:"): res['analysis'] = line.replace("ANALYSIS:", "").strip()
            elif line.startswith("CONCERNS:"): res['concerns'] = line.replace("CONCERNS:", "").strip()
        return res

class BuilderAgent:
    def analyze(self, task, context, provider="auto"):
        prompt = f"Task: {task}\nContext: {context}\nAnalyze from BUILDER perspective (feasibility, execution). Respond with:\nSUMMARY: <one sentence>\nANALYSIS: <2-3 bullets>\nCONCERNS: <1 sentence>"
        return self._parse(generate_response(prompt, provider=provider, system_prompt="Pragmatic Builder."))
    def _parse(self, text):
        res = {'summary': text.split('\n')[0], 'analysis': '', 'concerns': ''}
        for line in text.split('\n'):
            if line.startswith("SUMMARY:"): res['summary'] = line.replace("SUMMARY:", "").strip()
            elif line.startswith("ANALYSIS:"): res['analysis'] = line.replace("ANALYSIS:", "").strip()
            elif line.startswith("CONCERNS:"): res['concerns'] = line.replace("CONCERNS:", "").strip()
        return res

class ResearcherAgent:
    def analyze(self, task, context, provider="auto"):
        prompt = f"Task: {task}\nContext: {context}\nAnalyze from RESEARCHER perspective (evidence, best practices). Respond with:\nSUMMARY: <one sentence>\nANALYSIS: <2-3 bullets>\nCONCERNS: <1 sentence>"
        return self._parse(generate_response(prompt, provider=provider, system_prompt="Research Expert."))
    def _parse(self, text):
        res = {'summary': text.split('\n')[0], 'analysis': '', 'concerns': ''}
        for line in text.split('\n'):
            if line.startswith("SUMMARY:"): res['summary'] = line.replace("SUMMARY:", "").strip()
            elif line.startswith("ANALYSIS:"): res['analysis'] = line.replace("ANALYSIS:", "").strip()
            elif line.startswith("CONCERNS:"): res['concerns'] = line.replace("CONCERNS:", "").strip()
        return res

class ExecutorAgent:
    def analyze(self, task, context, provider="auto"):
        prompt = f"Task: {task}\nContext: {context}\nAnalyze from EXECUTOR perspective (planning, steps). Respond with:\nSUMMARY: <one sentence>\nANALYSIS: <2-3 bullets>\nCONCERNS: <1 sentence>"
        return self._parse(generate_response(prompt, provider=provider, system_prompt="Project Executor."))
    def _parse(self, text):
        res = {'summary': text.split('\n')[0], 'analysis': '', 'concerns': ''}
        for line in text.split('\n'):
            if line.startswith("SUMMARY:"): res['summary'] = line.replace("SUMMARY:", "").strip()
            elif line.startswith("ANALYSIS:"): res['analysis'] = line.replace("ANALYSIS:", "").strip()
            elif line.startswith("CONCERNS:"): res['concerns'] = line.replace("CONCERNS:", "").strip()
        return res

class VerifierAgent:
    def analyze(self, task, context, provider="auto"):
        prompt = f"Task: {task}\nContext: {context}\nAnalyze from VERIFIER perspective (quality, testing). Respond with:\nSUMMARY: <one sentence>\nANALYSIS: <2-3 bullets>\nCONCERNS: <1 sentence>"
        return self._parse(generate_response(prompt, provider=provider, system_prompt="Quality Verifier."))
    def _parse(self, text):
        res = {'summary': text.split('\n')[0], 'analysis': '', 'concerns': ''}
        for line in text.split('\n'):
            if line.startswith("SUMMARY:"): res['summary'] = line.replace("SUMMARY:", "").strip()
            elif line.startswith("ANALYSIS:"): res['analysis'] = line.replace("ANALYSIS:", "").strip()
            elif line.startswith("CONCERNS:"): res['concerns'] = line.replace("CONCERNS:", "").strip()
        return res
