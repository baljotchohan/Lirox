"""Lirox v1.0.0 — MindAgent — personal advisor with deep user knowledge"""
from __future__ import annotations
import re
import time
from collections import Counter
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

_soul: LivingSoul = None; _learnings: LearningsStore = None
_skills: SkillsRegistry = None; _sub_agents: SubAgentsRegistry = None
_trainer: TrainingEngine = None; _improver: SelfImprover = None


def get_soul() -> LivingSoul:
    global _soul
    if _soul is None: _soul = LivingSoul()
    return _soul

def get_learnings() -> LearningsStore:
    global _learnings
    if _learnings is None: _learnings = LearningsStore()
    return _learnings

def get_skills() -> SkillsRegistry:
    global _skills
    if _skills is None: _skills = SkillsRegistry()
    return _skills

def get_sub_agents() -> SubAgentsRegistry:
    global _sub_agents
    if _sub_agents is None: _sub_agents = SubAgentsRegistry()
    return _sub_agents

def get_trainer(memory: MemoryManager = None) -> TrainingEngine:
    global _trainer
    if _trainer is None or memory is not None:
        _trainer = TrainingEngine(get_learnings())
    return _trainer

def get_improver() -> SelfImprover:
    global _improver
    if _improver is None: _improver = SelfImprover()
    return _improver


class MindAgent(BaseAgent):
    @property
    def name(self) -> str: return get_soul().get_name().lower()
    @property
    def description(self) -> str: return "Personal advisor — recommendations, plans, deep user knowledge"

    def run(self, query: str, system_prompt: str = "",
            context: str = "", mode: str = "advisor") -> Generator[AgentEvent, None, None]:
        soul       = get_soul()
        learnings  = get_learnings()
        sub_agents = get_sub_agents()
        skills     = get_skills()
        improver   = get_improver()
        soul.increment_interactions()

        # 1. Sub-agent routing
        agent_call = sub_agents.detect_agent_call(query)
        if agent_call:
            name, q = agent_call
            yield {"type": "agent_progress", "message": f"🤖 Routing to: {name}"}
            try:
                result = sub_agents.run_agent(name, q, {"user_profile": learnings.to_context_string()})
                self.memory.save_exchange(query, result)
                yield {"type": "done", "answer": result}
            except Exception as e:
                improver.log_error(f"sub_agent:{name}", str(e))
                yield {"type": "done", "answer": f"Sub-agent error: {e}"}
            return  # always return

        # 2. Skill activation
        skill_name = skills.find_relevant_skill(query)
        if skill_name:
            yield {"type": "agent_progress", "message": f"🔧 Using skill: {skill_name}"}
            try:
                skill_result = skills.run_skill(skill_name, query,
                                                {"user_profile": learnings.to_context_string()})
                answer = generate_response(
                    f"Query: {query}\n\nSkill output:\n{skill_result}\n\nSynthesize into helpful response.",
                    provider="auto", system_prompt=self._sys(soul, learnings))
                self.memory.save_exchange(query, answer)
                yield {"type": "done", "answer": answer}
                return  # FIX: return — prevents fall-through to step 4
            except Exception as e:
                improver.log_error(f"skill:{skill_name}", str(e))
                # fall through to advisor

        # 3. Extract learnings
        self._learn(query, learnings)

        # 4. Advisor response
        mem_ctx    = self.memory.get_relevant_context(query)
        sys_prompt = system_prompt or self._sys(soul, learnings)
        prompt     = (f"Context:\n{mem_ctx}\n\nUser: {query}" if mem_ctx else query)
        if context: prompt = f"Reasoning:\n{context[:2000]}\n\n{prompt}"

        try:
            answer = generate_response(prompt, provider="auto", system_prompt=sys_prompt)
            self.memory.save_exchange(query, answer)
            self._auto_topics(query, learnings)
            learnings.flush()   # persist deferred topic bumps (BUG-4 FIX)
            yield {"type": "done", "answer": answer}
        except Exception as e:
            improver.log_error("mind_agent:run", str(e))
            yield {"type": "error", "message": str(e)}

    def _sys(self, soul, learnings) -> str:
        base = soul.to_system_prompt(learnings.to_context_string())
        if self.profile_data:
            lines = [f"• {lbl}: {self.profile_data.get(k,'')}"
                     for k, lbl in [("user_name","User name"),("niche","Their work"),
                                     ("current_project","Current project")]
                     if self.profile_data.get(k)]
            if lines and "USER PROFILE" not in base:
                base += "\n\nUSER PROFILE BASELINE:\n" + "\n".join(lines)
        return base

    def _learn(self, query: str, learnings: LearningsStore) -> None:
        q = query.lower()
        patterns = [
            (r"remember (?:that )?i (?:prefer|like|love|want|use|work with) (.+)", "fact"),
            (r"my (?:name is|name's) (\w+)", "fact"),
            (r"i(?:'m| am) (?:a |an )?([\w][\w ]+(?:developer|engineer|designer|founder|ceo|student|researcher|writer|manager))", "fact"),
            (r"i work (?:at|for|with) ([\w ]+)", "fact"),
            (r"i(?:'m| am) working on ([\w ]+)", "fact"),
            (r"my (?:main )?project(?:'s| is) ([\w ]+)", "project"),
            (r"i (?:don't|do not|hate|dislike) (?:like )?(.+)", "dislike"),
        ]
        for pat, kind in patterns:
            m = re.search(pat, q)
            if m:
                val = m.group(1).strip()[:150]
                if len(val) > 3:
                    if kind == "fact": learnings.add_fact(val, confidence=0.9, source="inline")
                    elif kind == "project": learnings.add_project(val)
                    elif kind == "dislike": learnings.add_dislike(val)
        for pat in [r"(?:working on|building|my project) (?:called |named )?([A-Z][a-zA-Z0-9\- ]+)",
                    r"project[: ]+([A-Z][a-zA-Z0-9\- ]+)"]:
            m = re.search(pat, query)
            if m: learnings.add_project(m.group(1).strip()[:60])

    def _auto_topics(self, query: str, learnings: LearningsStore) -> None:
        stop  = {'what','when','where','which','that','this','with','from','about',
                 'have','will','your','just','like','make','want','need','help',
                 'also','some','more','does','should'}
        words = [w for w in re.findall(r'\b[a-zA-Z]{4,}\b', query.lower()) if w not in stop]
        for topic, _ in Counter(words).most_common(3):
            learnings.bump_topic(topic)
