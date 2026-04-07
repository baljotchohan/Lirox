"""
Lirox v0.5 — MindAgent

The core personal advisor. This is NOT a generic LLM wrapper.
It knows you, learns from you, grows with you.

Capabilities:
  - Deep user knowledge via LearningsStore
  - Living soul that shapes personality
  - Named sub-agents callable by name
  - Dynamic skills that expand capabilities
  - Self-improvement via /improve
  - /train to crystallize session learnings permanently
  - File/desktop access with permission requests
"""
from __future__ import annotations

import time
from typing import Generator, Dict, Any

from lirox.agents.base_agent import BaseAgent, AgentEvent
from lirox.memory.manager import MemoryManager
from lirox.thinking.scratchpad import Scratchpad
from lirox.mind.soul import LivingSoul
from lirox.mind.learnings import LearningsStore
from lirox.mind.skills.registry import SkillsRegistry
from lirox.mind.sub_agents.registry import SubAgentsRegistry
from lirox.mind.trainer import TrainingEngine
from lirox.mind.self_improver import SelfImprover
from lirox.utils.llm import generate_response


# ── Singleton instances (shared across orchestrator) ──────────────────────────
_soul:         LivingSoul        = None
_learnings:    LearningsStore    = None
_skills:       SkillsRegistry    = None
_sub_agents:   SubAgentsRegistry = None
_trainer:      TrainingEngine    = None
_improver:     SelfImprover      = None


def get_soul() -> LivingSoul:
    global _soul
    if _soul is None:
        _soul = LivingSoul()
    return _soul


def get_learnings() -> LearningsStore:
    global _learnings
    if _learnings is None:
        _learnings = LearningsStore()
    return _learnings


def get_skills() -> SkillsRegistry:
    global _skills
    if _skills is None:
        _skills = SkillsRegistry()
    return _skills


def get_sub_agents() -> SubAgentsRegistry:
    global _sub_agents
    if _sub_agents is None:
        _sub_agents = SubAgentsRegistry()
    return _sub_agents


def get_trainer(memory: MemoryManager = None) -> TrainingEngine:
    global _trainer
    learn = get_learnings()
    if _trainer is None or memory is not None:
        _trainer = TrainingEngine(learn)
    return _trainer


def get_improver() -> SelfImprover:
    global _improver
    if _improver is None:
        _improver = SelfImprover()
    return _improver


class MindAgent(BaseAgent):
    """
    The Mind Agent — personal advisor for Lirox v0.5.

    Unlike PersonalAgent (which executes tasks), MindAgent:
    - Knows the user deeply via LearningsStore
    - Gives personalized recommendations and plans
    - Routes to sub-agents by name
    - Activates skills when relevant
    - Falls through to PersonalAgent for execution tasks
    """

    @property
    def name(self) -> str:
        return get_soul().get_name().lower()

    @property
    def description(self) -> str:
        return "Personal advisor — recommendations, plans, and deep user knowledge"

    def get_onboarding_message(self) -> str:
        soul = get_soul()
        name = soul.get_name()
        return (
            f"👋 I'm {name} — your personal AI advisor.\n\n"
            f"I'm different from a regular AI:\n"
            f"  • I learn from every interaction (/train to save)\n"
            f"  • I give you recommendations, not just information\n"
            f"  • You can teach me new skills (/add-skill)\n"
            f"  • You can add specialized agents (/add-agent)\n"
            f"  • I improve my own code over time (/improve)\n\n"
            f"The more you use me, the better I know you.\n"
            f"Type /mind to see my current state."
        )

    def run(
        self,
        query: str,
        system_prompt: str = "",
        context: str = "",
        mode: str = "advisor",
    ) -> Generator[AgentEvent, None, None]:

        soul = get_soul()
        learnings = get_learnings()
        sub_agents = get_sub_agents()
        skills = get_skills()
        improver = get_improver()

        soul.increment_interactions()
        start = time.time()

        yield {"type": "agent_start", "message": "Analyzing…"}

        # ── 1. Check for sub-agent call ───────────────────────────────────────
        agent_call = sub_agents.detect_agent_call(query)
        if agent_call:
            agent_name, clean_query = agent_call
            yield {"type": "agent_progress",
                   "message": f"🤖 Routing to sub-agent: {agent_name}"}
            try:
                ctx = {"user_profile": learnings.to_context_string(), "soul": soul.get_name()}
                result = sub_agents.run_agent(agent_name, clean_query, ctx)
                self.memory.save_exchange(query, result)
                yield {"type": "done", "answer": result}
            except Exception as e:
                improver.log_error(f"sub_agent:{agent_name}", str(e))
                yield {"type": "done", "answer": f"Sub-agent error: {e}"}
            return

        # ── 2. Check for relevant skill ───────────────────────────────────────
        skill_name = skills.find_relevant_skill(query)
        if skill_name:
            yield {"type": "agent_progress",
                   "message": f"🔧 Using skill: {skill_name}"}
            try:
                ctx = {"user_profile": learnings.to_context_string()}
                skill_result = skills.run_skill(skill_name, query, ctx)

                # Use skill result as context for LLM to synthesize
                final_prompt = (
                    f"User query: {query}\n\n"
                    f"Skill '{skill_name}' output:\n{skill_result}\n\n"
                    f"Based on what you know about this user and the skill output, "
                    f"give your recommendation or summary."
                )
                answer = generate_response(
                    final_prompt,
                    provider="auto",
                    system_prompt=soul.to_system_prompt(learnings.to_context_string()),
                )
                self.memory.save_exchange(query, answer)
                yield {"type": "done", "answer": answer}
            except Exception as e:
                improver.log_error(f"skill:{skill_name}", str(e))
                # Fall through to normal advisor mode
                yield {"type": "agent_progress",
                       "message": f"Skill failed, falling back to advisor mode…"}

        # ── 3. Detect learning signals in the query ───────────────────────────
        self._extract_inline_learnings(query, learnings)

        # ── 4. Build advisor response ─────────────────────────────────────────
        yield {"type": "agent_progress", "message": "Thinking…"}

        mem_ctx = self.memory.get_relevant_context(query)
        learn_ctx = learnings.to_context_string()
        sys_prompt = soul.to_system_prompt(learn_ctx)

        prompt = query
        if mem_ctx:
            prompt = f"Conversation context:\n{mem_ctx}\n\nUser: {query}"
        if context:
            prompt = f"Reasoning:\n{context}\n\n{prompt}"

        try:
            answer = generate_response(prompt, provider="auto", system_prompt=sys_prompt)
            self.memory.save_exchange(query, answer)
            yield {"type": "done", "answer": answer}
        except Exception as e:
            improver.log_error("mind_agent:run", str(e))
            yield {"type": "error", "message": str(e)}

    def _extract_inline_learnings(self, query: str, learnings: LearningsStore) -> None:
        """
        Detect inline learning signals in the query.
        e.g. "remember that I prefer short responses"
             "I'm working on a new project called Lirox"
             "I don't like bullet points"
        """
        q_lower = query.lower()

        # Preference patterns
        remember_patterns = [
            r"remember (?:that )?i (?:prefer|like|love|enjoy|want) (.+)",
            r"always (.+) when you respond",
            r"i prefer (.+)",
        ]
        import re
        for pat in remember_patterns:
            m = re.search(pat, q_lower)
            if m:
                learnings.add_preference("explicit", m.group(1).strip()[:100])

        # Dislike patterns
        dislike_patterns = [
            r"i (?:don't|do not|hate|dislike) (?:like )?(.+)",
            r"stop (.+)",
            r"never (.+) again",
        ]
        for pat in dislike_patterns:
            m = re.search(pat, q_lower)
            if m:
                text = m.group(1).strip()[:100]
                if len(text) > 3:
                    learnings.add_dislike(text)

        # Project patterns
        project_patterns = [
            r"(?:working on|building|creating|developing) (?:a |an )?(?:project called |app called |tool called )?([A-Z][a-zA-Z0-9\-_ ]+)",
            r"my project[: ]+([A-Z][a-zA-Z0-9\-_ ]+)",
        ]
        for pat in project_patterns:
            m = re.search(pat, query)  # case-sensitive for proper nouns
            if m:
                learnings.add_project(m.group(1).strip()[:60])
