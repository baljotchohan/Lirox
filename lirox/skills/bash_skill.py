"""BashTool skill — execute shell commands safely."""

from typing import Dict, Any, List, Tuple
from lirox.skills import BaseSkill, SkillResult, RiskLevel


class BashSkill(BaseSkill):
    
    @property
    def name(self) -> str:
        return "bash"
    
    @property
    def description(self) -> str:
        return "Execute shell commands safely (allowlist enforced)"
    
    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.HIGH
    
    @property
    def keywords(self) -> List[str]:
        return [
            "run", "execute", "command", "terminal", "shell", "bash",
            "mkdir", "ls", "pip", "npm", "git", "install", "cd",
            "create directory", "list files", "run script",
        ]
    
    def execute(self, query: str, context: Dict[str, Any] = None) -> SkillResult:
        from lirox.tools.terminal import run_command
        from lirox.utils.llm import generate_response
        
        # Extract the command from natural language
        prompt = (
            f"Extract the EXACT terminal command from this request. "
            f"Return ONLY the raw shell command on one line. No explanation.\n\n"
            f"Request: {query}"
        )
        command = generate_response(prompt, "auto")
        command = command.strip().strip("`\"' \n")
        
        if command.startswith("```"):
            lines = command.split("\n")
            command = "\n".join(l for l in lines if not l.startswith("```")).strip()
        
        if not command or len(command) > 500:
            return SkillResult(
                success=False, output="Could not extract a valid command.",
                skill_name=self.name, error="Command extraction failed"
            )
        
        # Execute safely
        output = run_command(command)
        
        is_blocked = output.startswith("[Blocked]")
        return SkillResult(
            success=not is_blocked,
            output=output,
            skill_name=self.name,
            metadata={"command": command},
            error=output if is_blocked else ""
        )
