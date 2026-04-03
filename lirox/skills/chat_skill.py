"""Chat skill — default conversational responses via LLM."""

from typing import Dict, Any, List
from lirox.skills import BaseSkill, SkillResult, RiskLevel


class ChatSkill(BaseSkill):
    """Default fallback skill — direct LLM conversation."""
    
    @property
    def name(self) -> str:
        return "chat"
    
    @property
    def description(self) -> str:
        return "General conversation, questions, explanations"
    
    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE
    
    @property
    def keywords(self) -> List[str]:
        return []  # Empty — this is the fallback
    
    def can_handle(self, query: str) -> tuple:
        """Chat always handles with minimum score (fallback)."""
        return True, 0.05
    
    def execute(self, query: str, context: Dict[str, Any] = None) -> SkillResult:
        from lirox.utils.llm import generate_response
        
        system_prompt = context.get("system_prompt", "") if context else ""
        response = generate_response(query, "auto", system_prompt=system_prompt)
        
        return SkillResult(
            success=True, output=response, skill_name=self.name,
            confidence=1.0
        )
