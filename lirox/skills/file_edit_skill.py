"""FileEdit skill — edit existing files with find/replace."""

from typing import Dict, Any, List
from lirox.skills import BaseSkill, SkillResult, RiskLevel


class FileEditSkill(BaseSkill):
    
    @property
    def name(self) -> str:
        return "file_edit"
    
    @property
    def description(self) -> str:
        return "Edit existing files using find/replace or line-based edits"
    
    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM
    
    @property
    def keywords(self) -> List[str]:
        return [
            "edit", "modify", "change", "replace", "update file",
            "fix file", "add to file", "insert", "append", "remove line",
        ]
    
    def execute(self, query: str, context: Dict[str, Any] = None) -> SkillResult:
        from lirox.tools.file_io import FileIOTool
        from lirox.utils.llm import generate_response
        
        # LLM determines the edit operation
        edit_prompt = (
            f"You are a file editor. Determine the edit operation from this request.\n"
            f"Return JSON: {{\"path\": \"...\", \"find\": \"text to find\", \"replace\": \"replacement text\"}}\n"
            f"If appending, use find=\"\" and replace=\"text to append\".\n\n"
            f"Request: {query}\n"
            f"Context: {str(context or {})[:500]}"
        )
        
        import json
        try:
            response = generate_response(edit_prompt, "auto")
            # Parse JSON from response
            if "```json" in response:
                json_str = response.split("```json")[-1].split("```")[0].strip()
            else:
                import re
                match = re.search(r'\{.*\}', response, re.DOTALL)
                json_str = match.group(0) if match else response
            
            edit = json.loads(json_str)
            path = edit.get("path", "")
            find_text = edit.get("find", "")
            replace_text = edit.get("replace", "")
            
            fio = FileIOTool()
            content = fio.read_file(path)
            
            if find_text:
                if find_text not in content:
                    return SkillResult(
                        success=False, output="", skill_name=self.name,
                        error=f"Text '{find_text[:50]}...' not found in {path}"
                    )
                new_content = content.replace(find_text, replace_text, 1)
            else:
                # Append mode
                new_content = content + "\n" + replace_text
            
            result = fio.write_file(path, new_content)
            return SkillResult(
                success=True, output=f"File edited: {path}", skill_name=self.name,
                metadata={"path": path, "operation": "replace" if find_text else "append"}
            )
        except Exception as e:
            return SkillResult(
                success=False, output="", skill_name=self.name,
                error=str(e)
            )
