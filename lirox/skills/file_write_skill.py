"""FileWrite skill — create and write files."""

from typing import Dict, Any, List
from lirox.skills import BaseSkill, SkillResult, RiskLevel


class FileWriteSkill(BaseSkill):
    
    @property
    def name(self) -> str:
        return "file_write"
    
    @property
    def description(self) -> str:
        return "Create and write files (defaults to outputs/)"
    
    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM
    
    @property
    def keywords(self) -> List[str]:
        return [
            "write", "save", "create file", "output", "store",
            "write file", "save to", "generate file", "export",
        ]
    
    def execute(self, query: str, context: Dict[str, Any] = None) -> SkillResult:
        from lirox.tools.file_io import FileIOTool
        from lirox.utils.llm import generate_response
        import re
        
        # Generate content
        content_prompt = (
            f"Generate the content for this file request. "
            f"Return ONLY the file content, no explanation.\n\n"
            f"Request: {query}\n"
            f"Context: {str(context or {})[:500]}"
        )
        content = generate_response(content_prompt, "auto")
        
        # Strip code fences
        content = re.sub(r'```\w*\n?', '', content).strip('`').strip()
        
        # Extract filename
        path_prompt = (
            f"Suggest a filename for this content. Return ONLY the filename "
            f"(use outputs/ directory if unspecified). No explanation.\n\n"
            f"Request: {query}"
        )
        path = generate_response(path_prompt, "auto").strip().strip("\"'` \n")
        
        if "/" not in path and "\\" not in path:
            path = f"outputs/{path}"
        
        try:
            fio = FileIOTool()
            result = fio.write_file(path, content)
            return SkillResult(
                success=True, output=result, skill_name=self.name,
                metadata={"path": path, "chars": len(content)}
            )
        except Exception as e:
            return SkillResult(
                success=False, output="", skill_name=self.name,
                error=str(e)
            )
