"""Code Agent v2 — Real-time file operations, terminal execution, desktop control"""
import os
import tempfile
import subprocess
from pathlib import Path
from typing import Generator, Dict, Any, Optional

from lirox.config import PROJECT_ROOT, SAFE_DIRS_RESOLVED
from lirox.tools.desktop_v2 import get_desktop_controller
from lirox.utils.llm import generate_response
from lirox.utils.structured_logger import get_logger

logger = get_logger("lirox.agents.code_agent_v2")


class CodeAgentV2:
    """Production code agent with real execution capabilities."""
    
    def __init__(self, memory=None, scratchpad=None, profile_data=None):
        self.memory = memory
        self.scratchpad = scratchpad
        self.profile_data = profile_data or {}
        self.desktop = get_desktop_controller()
        self.current_workspace = None
        self.execution_history = []
    
    def create_workspace(self, project_name: str) -> Path:
        """Create isolated project workspace."""
        workspace = Path(PROJECT_ROOT) / "workspaces" / project_name
        workspace.mkdir(parents=True, exist_ok=True)
        self.current_workspace = workspace
        logger.info(f"Created workspace: {workspace}")
        return workspace
    
    def write_file(self, filepath: str, content: str) -> bool:
        """Write file with safety checks."""
        try:
            path = Path(filepath).resolve()
            
            # Safety: Check if within safe directories
            if not any(path.is_relative_to(safe_dir) for safe_dir in SAFE_DIRS_RESOLVED):
                logger.error(f"Path not in safe dirs: {filepath}")
                return False
            
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
            logger.info(f"File written: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Write file failed: {e}")
            return False
    
    def read_file(self, filepath: str) -> Optional[str]:
        """Read file content."""
        try:
            path = Path(filepath).resolve()
            return path.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"Read file failed: {e}")
            return None
    
    def list_directory(self, dirpath: str) -> Dict[str, Any]:
        """List directory contents."""
        try:
            path = Path(dirpath).resolve()
            items = {
                "files": [],
                "directories": [],
            }
            
            for item in path.iterdir():
                if item.is_file():
                    items["files"].append({
                        "name": item.name,
                        "size": item.stat().st_size,
                    })
                elif item.is_dir():
                    items["directories"].append(item.name)
            
            return items
            
        except Exception as e:
            logger.error(f"List directory failed: {e}")
            return {"files": [], "directories": []}
    
    def execute_terminal_command(self, command: str, cwd: str = None) -> Dict[str, Any]:
        """
        Execute terminal command with full output capture.
        
        Args:
            command: Shell command to execute
            cwd: Working directory
            
        Returns:
            {stdout, stderr, returncode, execution_time}
        """
        import shlex
        import time
        
        # Safety: Block dangerous commands
        dangerous_patterns = [
            "rm -rf /",
            "rm -rf ~",
            "shutdown",
            "reboot",
            "sudo rm",
        ]
        
        for pattern in dangerous_patterns:
            if pattern in command.lower():
                logger.error(f"Blocked dangerous command: {command}")
                return {
                    "stdout": "",
                    "stderr": f"Blocked: {command}",
                    "returncode": 1,
                    "execution_time": 0,
                }
        
        try:
            start = time.time()
            result = subprocess.run(
                shlex.split(command),
                cwd=cwd or self.current_workspace,
                capture_output=True,
                text=True,
                timeout=30,
            )
            elapsed = time.time() - start
            
            self.execution_history.append({
                "command": command,
                "returncode": result.returncode,
                "timestamp": time.time(),
            })
            
            return {
                "stdout": result.stdout[:2000],  # Truncate large outputs
                "stderr": result.stderr[:2000],
                "returncode": result.returncode,
                "execution_time": elapsed,
            }
            
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": "Command timeout (30s)",
                "returncode": -1,
                "execution_time": 30,
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": str(e),
                "returncode": -1,
                "execution_time": 0,
            }
    
    def run(self, query: str, system_prompt: str = "", context: str = "", mode: str = "complex") -> Generator:
        """
        Main agent execution loop.
        
        Pipeline:
        1. Parse intent (what should be built/fixed?)
        2. Create workspace
        3. Plan file structure
        4. Write files
        5. Execute tests
        6. Report results
        """
        import time
        
        # Parse intent with LLM
        intent_prompt = f"""
Analyze this request and extract:
1. Main goal
2. Language/technology
3. Specific tasks (ordered list)

Request: {query}
"""
        
        yield {
            "type": "thinking",
            "message": "Analyzing request...",
        }
        
        try:
            intent_analysis = generate_response(
                intent_prompt,
                provider="auto",
                system_prompt="You are a code planning expert. Be concise.",
            )
            
            yield {
                "type": "progress",
                "message": f"Plan: {intent_analysis[:500]}",
            }
            
            # Create workspace
            workspace = self.create_workspace(f"task_{int(time.time())}")
            
            yield {
                "type": "progress",
                "message": f"Workspace created: {workspace}",
            }
            
            # Generate code
            code_prompt = f"""
Based on this analysis:
{intent_analysis}

Write complete, production-quality code that solves the problem.
Include:
- Type hints
- Error handling
- Docstrings
- No TODOs

CRITICAL INSTRUCTION FOR DESKTOP TASKS:
If the user wants to control the desktop, open an application, type text, or navigate URLs, you MUST write a Python script that uses the built-in Lirox Desktop Controller:
```python
import time
from lirox.tools.desktop_v2 import get_desktop_controller

desktop = get_desktop_controller()
desktop.start_task("Running desktop automation limit 1")

# Example usages:
# desktop.open_app("Safari")
# desktop.navigate_to_url("https://google.com")
# time.sleep(2)
# desktop.type_text("Lirox AI")
# desktop.press_key("enter")
# desktop.click(x=500, y=500)

desktop.end_task(success=True)
```

Request: {query}
"""
            
            code = generate_response(
                code_prompt,
                provider="auto",
                system_prompt="You are an expert Python/JS developer. Write ONLY code in markdown blocks.",
            )
            
            # Extract and save code
            files_created = self._extract_and_save_code(code, workspace)
            
            yield {
                "type": "progress",
                "message": f"Files created: {len(files_created)}",
                "data": {"files": files_created},
            }
            
            # Run tests/validation
            test_result = self._run_validation(workspace, files_created)
            
            yield {
                "type": "done",
                "answer": f"✅ Task complete!\n\n{test_result}",
                "data": {
                    "workspace": str(workspace),
                    "files": files_created,
                    "validation": test_result,
                },
            }
            
        except Exception as e:
            yield {
                "type": "error",
                "message": str(e),
            }
    
    def _extract_and_save_code(self, response: str, workspace: Path) -> list:
        """Extract code blocks from response and save."""
        import re
        
        files = []
        # Match markdown code blocks
        pattern = r"```(?:(\w+)\n)?(.*?)```"
        matches = re.findall(pattern, response, re.DOTALL)
        
        for lang, code in matches:
            ext = self._get_extension(lang)
            filename = f"code_{len(files)}{ext}"
            filepath = workspace / filename
            
            if self.write_file(str(filepath), code):
                files.append(str(filepath))
        
        return files
    
    def _get_extension(self, lang: str) -> str:
        """Get file extension from language."""
        if not lang:
            return ".txt"
        ext_map = {
            "python": ".py",
            "javascript": ".js",
            "typescript": ".ts",
            "java": ".java",
            "cpp": ".cpp",
            "go": ".go",
            "rust": ".rs",
            "bash": ".sh",
            "yaml": ".yaml",
            "json": ".json",
        }
        return ext_map.get(lang.lower(), ".txt")
    
    def _run_validation(self, workspace: Path, files: list) -> str:
        """Run the generated code/scripts."""
        output = ""
        for file in files:
            if file.endswith('.py'):
                res = self.execute_terminal_command(f"python3 {Path(file).name}", cwd=str(workspace))
                output += f"--- Execution of {Path(file).name} ---\nSTDOUT:\n{res['stdout']}\nSTDERR:\n{res['stderr']}\n\n"
            elif file.endswith('.js'):
                res = self.execute_terminal_command(f"node {Path(file).name}", cwd=str(workspace))
                output += f"--- Execution of {Path(file).name} ---\nSTDOUT:\n{res['stdout']}\nSTDERR:\n{res['stderr']}\n\n"
            elif file.endswith('.sh'):
                res = self.execute_terminal_command(f"bash {Path(file).name}", cwd=str(workspace))
                output += f"--- Execution of {Path(file).name} ---\nSTDOUT:\n{res['stdout']}\nSTDERR:\n{res['stderr']}\n\n"
                
        if not output.strip():
            result = self.execute_terminal_command("ls -la", cwd=str(workspace))
            output = f"Validation complete (No executable scripts found):\n{result['stdout']}"
            
        return output.strip()
