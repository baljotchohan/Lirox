"""CodeGen skill — generate, explain, and debug code."""

from typing import Dict, Any, List
from lirox.skills import BaseSkill, SkillResult, RiskLevel


class CodeGenSkill(BaseSkill):
    
    @property
    def name(self) -> str:
        return "code_gen"
    
    @property
    def description(self) -> str:
        return "Generate, explain, review, and debug code"
    
    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE
    
    @property
    def keywords(self) -> List[str]:
        return [
            "code", "script", "function", "class", "program",
            "debug", "fix code", "explain code", "review code",
            "python", "javascript", "html", "css", "sql",
            "algorithm", "implement", "refactor", "optimize code",
        ]
    
    def execute(self, query: str, context: Dict[str, Any] = None) -> SkillResult:
        from lirox.utils.llm import generate_response
        
        system_prompt = (
            "You are an expert programmer. Write clean, production-ready code.\n"
            "Rules:\n"
            "- Include comments explaining complex logic\n"
            "- Use proper error handling\n"
            "- Follow language best practices\n"
            "- If debugging, explain the bug and the fix\n"
            "- Output code in clean text (no markdown fences unless the user will copy it)\n"
        )
        
        response = generate_response(query, "auto", system_prompt=system_prompt)
        
        return SkillResult(
            success=True,
            output=response,
            skill_name=self.name,
            confidence=0.9,
        )
