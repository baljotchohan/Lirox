"""FileRead skill — read files safely."""

from typing import Dict, Any, List
from lirox.skills import BaseSkill, SkillResult, RiskLevel


class FileReadSkill(BaseSkill):
    
    @property
    def name(self) -> str:
        return "file_read"
    
    @property
    def description(self) -> str:
        return "Read file contents safely (sandboxed)"
    
    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW
    
    @property
    def keywords(self) -> List[str]:
        return [
            "read", "open", "show", "display", "cat", "view file",
            "contents of", "what's in", "load file", "read file",
        ]
    
    def execute(self, query: str, context: Dict[str, Any] = None) -> SkillResult:
        from lirox.tools.file_io import FileIOTool
        from lirox.utils.llm import generate_response
        
        # Extract file path
        prompt = f"Extract the file path from this request. Return ONLY the path.\n\nRequest: {query}"
        path = generate_response(prompt, "auto").strip().strip("\"'` \n")
        
        try:
            fio = FileIOTool()
            content = fio.read_file(path)
            return SkillResult(
                success=True, output=content, skill_name=self.name,
                metadata={"path": path, "chars": len(content)}
            )
        except Exception as e:
            return SkillResult(
                success=False, output="", skill_name=self.name,
                error=str(e)
            )
