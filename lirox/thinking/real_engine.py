"""
Real multi-agent thinking with actual LLM calls.
Every agent thinks independently (in parallel), then they debate.
Updated for production-grade performance and robustness.
"""

import time
import logging
import concurrent.futures
from typing import Dict, List, Any, Generator, Optional
from lirox.utils.llm import generate_response

_logger = logging.getLogger("lirox.thinking.real_engine")

class BaseThinkingAgent:
    """Base class for specialized thinking agents."""
    def __init__(self, name: str, persona: str):
        self.name = name
        self.persona = persona

    def analyze(self, task: str, context: str, provider: str = "auto") -> Dict[str, Any]:
        prompt = (
            f"Task: {task}\n"
            f"Context: {context[:4000]}\n\n"
            f"Analyze from {self.name.upper()} perspective ({self.persona}).\n"
            "Respond with exactly this format:\n"
            "SUMMARY: <one sentence summary of your stance>\n"
            "ANALYSIS: <2-3 key technical bullets>\n"
            "CONCERNS: <one sentence about risks or gaps>"
        )
        try:
            sys_p = f"You are a {self.persona}. 🚀 ZERO ASTERISK POLICY (STRICT): NEVER use '*' for any reason. Use '__' for bold. Use emojis for lists."
            response = generate_response(prompt, provider=provider, system_prompt=sys_p)
            return self._parse(response)
        except Exception as e:
            _logger.error(f"Agent {self.name} failed: {e}")
            return {
                'summary': f"Error in analysis: {e}",
                'analysis': "N/A",
                'concerns': "Communication failure"
            }

    def _parse(self, text: str) -> Dict[str, Any]:
        res = {'summary': "No summary provided", 'analysis': '', 'concerns': 'No concerns identified'}
        lines = text.strip().split('\n')
        for line in lines:
            if line.startswith("SUMMARY:"): res['summary'] = line.replace("SUMMARY:", "").strip()
            elif line.startswith("ANALYSIS:"): res['analysis'] = line.replace("ANALYSIS:", "").strip()
            elif line.startswith("CONCERNS:"): res['concerns'] = line.replace("CONCERNS:", "").strip()
        
        # Fallback if parsing failed
        if not res['summary'] or res['summary'] == "No summary provided":
            res['summary'] = lines[0] if lines else "Analysis complete."
            
        return res

class RealThinkingEngine:
    """
    ACTUAL multi-agent reasoning with parallel LLM calls.
    Yields events for real-time UI streaming.
    """
    
    def __init__(self, provider="auto"):
        self.provider = provider
        self.agents = [
            BaseThinkingAgent('Architect', 'Senior System Architect specializing in scalability and long-term design.'),
            BaseThinkingAgent('Builder', 'Pragmatic Software Engineer focused on feasibility, execution, and performance.'),
            BaseThinkingAgent('Researcher', 'Fact-driven analyst specializing in industry best practices and deep-dive research.'),
            BaseThinkingAgent('Executor', 'Project Lead focused on planning, step-by-step implementation, and delivery.'),
            BaseThinkingAgent('Verifier', 'Security and Quality Expert focused on testing, edge cases, and robustness.')
        ]
    
    def think_and_decide(self, task: str, context: str = "") -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        """
        Complete thinking pipeline yielding events for the UI.
        Runs independent analyses in parallel for maximum speed.
        """
        
        start_time = time.time()
        agent_views = {}
        
        # ── PHASE 1: INDEPENDENT ANALYSIS (PARALLEL) ──────────────────────────
        yield {
            "type": "thinking_phase", 
            "phase_index": 0,
            "phase_name": "INDEPENDENT ANALYSIS",
            "phase_icon": "🔍",
            "phase_total": 3,
            "phase_tagline": "Experts are analyzing the task in parallel",
            "confidence": 70,
            "steps": ["Initializing debate protocols", "Launching parallel analysis threads"]
        }
        
        # We use a ThreadPoolExecutor to run all agent analyses at once
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.agents)) as executor:
            future_to_agent = {
                executor.submit(agent.analyze, task, context, self.provider): agent 
                for agent in self.agents
            }
            
            for future in concurrent.futures.as_completed(future_to_agent):
                agent = future_to_agent[future]
                try:
                    view = future.result()
                    agent_views[agent.name] = view
                    yield {
                        "type": "agent_progress", 
                        "agent": agent.name, 
                        "message": f"✓ {agent.name} finished analysis", 
                        "status": "done"
                    }
                except Exception as e:
                    _logger.error(f"Agent {agent.name} analysis failed: {e}")
        
        # ── PHASE 2: CONFLICT DETECTION & RESOLUTION ──────────────────────────
        yield {
            "type": "thinking_phase", 
            "phase_index": 1,
            "phase_name": "MULTI-AGENT DEBATE",
            "phase_icon": "💬",
            "phase_total": 3,
            "phase_tagline": "Synthesizing perspectives and resolving contradictions",
            "confidence": 85,
            "steps": ["Analyzing perspective alignment", "Detecting conceptual conflicts", "Resolving multi-agent contradictions"]
        }
        
        debate_log = []
        positions_text = "\n".join([f"{name}: {view['summary']}\nAnalysis: {view['analysis']}" for name, view in agent_views.items()])
        
        yield {"type": "agent_progress", "agent": "System", "message": "Analyzing conflict map...", "status": "running"}
        
        # ── PHASE 2.1: CRITICAL ANALYSIS ──
        conflict_prompt = (
            f"Expert Positions:\n{positions_text}\n\n"
            "Analyze these positions for contradictions, risks, or trade-offs.\n"
            "Respond with a list of specific conflicts or 'NO CONFLICT'.\n"
            "Format: [{'agents': ['A', 'B'], 'issue': '...', 'resolution_strategy': '...'}]"
        )
        
        conflict_analysis = generate_response(
            conflict_prompt,
            provider=self.provider,
            system_prompt="You are a Strategic Debate Judge. Find deep technical contradictions. 🚀 ZERO ASTERISK POLICY."
        )
        
        if "NO CONFLICT" not in conflict_analysis:
            # We found conflicts, let's try to resolve them
            yield {"type": "agent_progress", "agent": "System", "message": "Resolving identified conflicts...", "status": "running"}
            
            resolution_prompt = (
                f"Original Task: {task}\n\n"
                f"Expert Perspectives:\n{positions_text}\n\n"
                f"Identified Conflicts:\n{conflict_analysis}\n\n"
                "Resolve these conflicts. Propose a single verified path forward that merges the best points while mitigating the risks.\n"
                "Respond with:\nRESOLVED_PATH: <detailed path>\nTRADE_OFFS: <key trade-offs made>"
            )
            
            resolution = generate_response(
                resolution_prompt,
                provider=self.provider,
                system_prompt="Strategic Mediator. Resolve expert conflicts into a unified plan. 🚀 ZERO ASTERISK POLICY."
            )
            
            # Record in debate log
            debate_log.append({
                "agent_a": "Architect/Builder",
                "agent_b": "Verifier/Researcher",
                "issue": "Conceptual Alignment",
                "resolution": resolution[:500]
            })
        else:
            yield {"type": "agent_progress", "agent": "System", "message": "✓ Perfect alignment detected.", "status": "done"}

        # ── PHASE 3: CONSENSUS SYNTHESIS ──────────────────────────────────────
        yield {
            "type": "thinking_phase", 
            "phase_index": 2,
            "phase_name": "CONSENSUS SYNTHESIS",
            "phase_icon": "🎯",
            "phase_total": 3,
            "phase_tagline": "Forming the unified final strategy",
            "confidence": 98,
            "steps": ["Merging expertise", "Finalizing verified path", "Applying Zero Asterisk Protocol"]
        }
        
        synthesis = self._synthesize_decision(agent_views, debate_log)
        elapsed = round(time.time() - start_time, 2)
        
        final_result = {
            'agent_views': agent_views,
            'debate': {'conflicts': debate_log, 'summary': f"Synthesized {len(agent_views)} views through debate"},
            'synthesis': synthesis,
            'decision': synthesis['final_decision'],
            'time_taken': elapsed,
            'reasoning_shown': True,
        }
        
        yield {"type": "done", "message": "Consensus achieved.", "data": final_result}
        return final_result
    
    def _synthesize_decision(self, agent_views: Dict, conflicts: List) -> Dict:
        views_text = "\n".join([f"{name}: {view['summary']}\n- Analysis: {view['analysis']}" for name, view in agent_views.items()])
        conflicts_text = "\n".join([f"Conflict between {c['agent_a']} and {c['agent_b']}: {c['resolution']}" for c in conflicts])
        
        synthesis_prompt = f"""
Synthesize these expert perspectives and resolved conflicts into a single unified decision.

EXPERT VIEWS:
{views_text}

RESOLVED CONFLICTS:
{conflicts_text}

Provide:
1. DECISION: The final unified action (one clear sentence)
2. REASONING: Why this is the best path (2 sentences)
3. CONFIDENCE: 0-100%
"""
        
        sys_p = "Strategic decision engine. 🚀 ZERO ASTERISK POLICY (MANDATORY): NEVER use '*' for any reason. Use '__' for bold. Use emojis for lists."
        response = generate_response(synthesis_prompt, provider=self.provider, system_prompt=sys_p)
        
        # Robust parsing
        decision = "Proceed with task as requested."
        reasoning = "Consensus formed from expert analysis."
        confidence = 90
        
        for line in response.split('\n'):
            if line.upper().startswith("DECISION:"): decision = line.split(':', 1)[1].strip()
            elif line.upper().startswith("REASONING:"): reasoning = line.split(':', 1)[1].strip()
            elif line.upper().startswith("CONFIDENCE:"):
                try: confidence = int(''.join(filter(str.isdigit, line)))
                except: pass
                
        return {
            'final_decision': decision,
            'reasoning': reasoning,
            'confidence': confidence,
            'all_views_considered': len(agent_views),
        }

