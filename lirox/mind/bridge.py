import os
from typing import List, Dict, Any
from lirox.utils.llm import generate_response
from lirox.tools import file_tools, file_generator

def cognitive_llm_call(system_prompt: str, user_message: str, conversation_history: List[Dict[str, str]]) -> str:
    # Build context from history
    context = ""
    for msg in conversation_history:
        role = "User" if msg["role"] == "user" else "Assistant"
        content = msg["content"]
        # Skip if content is dict
        if isinstance(content, dict):
            content = str(content)
        context += f"{role}: {content}\n"
    
    if context:
        user_message = f"Recent Context:\n{context}\n\nQuery:\n{user_message}"
    
    return generate_response(prompt=user_message, system_prompt=system_prompt)

def cognitive_tool_executor(tool_name: str, parameters: Dict[str, Any]) -> Any:
    # We must handle placeholders gracefully because CognitiveEngine
    # plans tools *before* LLM generation in some intents.
    # If parameters lack critical data, we might need to do an inline LLM call!
    
    if tool_name == "list_files":
        path = parameters.get("path", "")
        if not path: path = "."
        return file_tools.file_list(path)
        
    elif tool_name == "read_file":
        path = parameters.get("path", "")
        return file_tools.file_read(path)
        
    elif tool_name == "write_file":
        path = parameters.get("path", "")
        content = parameters.get("content", "")
        
        # If content is empty, this means the engine planned it but hasn't generated it.
        # We must generate the content *now* inline using the LLM for the given path.
        if not content and "topic" in parameters:
            content = generate_response(f"Write the file {path} based on the topic: {parameters['topic']}")
        elif not content:
            # Maybe it's code generation? We'll ask LLM inline.
            content = generate_response(f"Generate the exact file content for: {path}")
            
        if not path:
            path = "generated_output.txt"
        return file_tools.file_write(path, content)
        
    elif tool_name == "create_presentation":
        import os
        from pathlib import Path as _Path
        from lirox.config import WORKSPACE_DIR
        workspace = os.getenv("LIROX_WORKSPACE", WORKSPACE_DIR)
        
        topic = parameters.get("topic", "Untitled")
        provided_name = parameters.get("filename")
        
        import re
        if not provided_name or str(provided_name).lower() in ("presentation.pptx", "presentation", "document.pptx", "document", "untitled.pptx", "untitled", "none", ""):
            safe_topic = re.sub(r'[^\w\s-]', '', topic).strip().replace(' ', '_')[:50]
            if safe_topic and safe_topic.lower() != "untitled":
                raw_name = f"{safe_topic}.pptx"
            else:
                raw_name = "presentation.pptx"
        else:
            raw_name = str(provided_name)
            
        if not raw_name.lower().endswith(".pptx"):
            raw_name = raw_name + ".pptx"
            
        if os.path.isabs(raw_name):
            path = str(raw_name)
        else:
            path = str(_Path(workspace) / raw_name)
            
        user_name = parameters.get("user_name", "")

        # Use ContentGenerator for rich, structured content
        from lirox.tools.content_generator import ContentGenerator
        gen = ContentGenerator()
        content_data = gen.generate("pptx", topic, query=topic)
        slides = content_data.get("slides", [])

        # Fallback if generation failed
        if not slides:
            slides = [
                {"title": f"Introduction to {topic}", "bullets": [f"Overview of {topic}"], "notes": ""},
                {"title": "Key Concepts", "bullets": ["Concept 1", "Concept 2", "Concept 3"], "notes": ""},
                {"title": "Conclusion", "bullets": [f"Summary of {topic}"], "notes": ""},
            ]

        return file_generator.create_pptx(path, topic, slides, query=topic, user_name=user_name)

    elif tool_name == "create_pdf":
        import os
        from pathlib import Path as _Path
        from lirox.config import WORKSPACE_DIR
        workspace = os.getenv("LIROX_WORKSPACE", WORKSPACE_DIR)
        
        topic = parameters.get("topic", "Untitled")
        provided_name = parameters.get("filename")
        
        import re
        if not provided_name or str(provided_name).lower() in ("document.pdf", "document", "untitled.pdf", "untitled", "none", ""):
            safe_topic = re.sub(r'[^\w\s-]', '', topic).strip().replace(' ', '_')[:50]
            if safe_topic and safe_topic.lower() != "untitled":
                raw_name = f"{safe_topic}.pdf"
            else:
                raw_name = "document.pdf"
        else:
            raw_name = str(provided_name)
            
        if not raw_name.lower().endswith(".pdf"):
            raw_name = raw_name + ".pdf"
            
        if os.path.isabs(raw_name):
            path = str(raw_name)
        else:
            path = str(_Path(workspace) / raw_name)
            
        user_name = parameters.get("user_name", "")

        from lirox.tools.content_generator import ContentGenerator
        gen = ContentGenerator()
        content_data = gen.generate("pdf", topic, query=topic)
        sections = content_data.get("sections", [])

        if not sections:
            sections = [{"heading": topic, "body": "Content", "bullets": []}]

        return file_generator.create_pdf(path, topic, sections, query=topic, user_name=user_name)

    elif tool_name in ("create_document", "create_docx"):
        import os
        from pathlib import Path as _Path
        from lirox.config import WORKSPACE_DIR
        workspace = os.getenv("LIROX_WORKSPACE", WORKSPACE_DIR)
        
        topic = parameters.get("topic", "Untitled")
        provided_name = parameters.get("filename")
        
        import re
        if not provided_name or str(provided_name).lower() in ("document.docx", "document", "untitled.docx", "untitled", "none", ""):
            safe_topic = re.sub(r'[^\w\s-]', '', topic).strip().replace(' ', '_')[:50]
            if safe_topic and safe_topic.lower() != "untitled":
                raw_name = f"{safe_topic}.docx"
            else:
                raw_name = "document.docx"
        else:
            raw_name = str(provided_name)
            
        if not raw_name.lower().endswith(".docx"):
            raw_name = raw_name + ".docx"
            
        if os.path.isabs(raw_name):
            path = str(raw_name)
        else:
            path = str(_Path(workspace) / raw_name)
            
        user_name = parameters.get("user_name", "")

        from lirox.tools.content_generator import ContentGenerator
        gen = ContentGenerator()
        content_data = gen.generate("docx", topic, query=topic)
        sections = content_data.get("sections", [])
        if not sections:
            sections = [{"heading": topic, "body": "Content", "bullets": []}]

        return file_generator.create_docx(path, topic, sections, query=topic, user_name=user_name)

    elif tool_name in ("create_spreadsheet", "create_xlsx"):
        import os
        from pathlib import Path as _Path
        from lirox.config import WORKSPACE_DIR
        workspace = os.getenv("LIROX_WORKSPACE", WORKSPACE_DIR)
        
        topic = parameters.get("topic", "Untitled")
        provided_name = parameters.get("filename")
        
        import re
        if not provided_name or str(provided_name).lower() in ("spreadsheet.xlsx", "spreadsheet", "untitled.xlsx", "untitled", "none", ""):
            safe_topic = re.sub(r'[^\w\s-]', '', topic).strip().replace(' ', '_')[:50]
            if safe_topic and safe_topic.lower() != "untitled":
                raw_name = f"{safe_topic}.xlsx"
            else:
                raw_name = "spreadsheet.xlsx"
        else:
            raw_name = str(provided_name)
            
        if not raw_name.lower().endswith(".xlsx"):
            raw_name = raw_name + ".xlsx"
            
        if os.path.isabs(raw_name):
            path = str(raw_name)
        else:
            path = str(_Path(workspace) / raw_name)
            
        user_name = parameters.get("user_name", "")

        from lirox.tools.content_generator import ContentGenerator
        gen = ContentGenerator()
        content_data = gen.generate("xlsx", topic, query=topic)
        sheets = content_data.get("sheets", [])
        if not sheets:
            sheets = [{"name": "Sheet1", "headers": ["A", "B"], "rows": [["1", "2"]]}]

        return file_generator.create_xlsx(path, topic, sheets, query=topic, user_name=user_name)

    elif tool_name == "execute_code":
        from lirox.tools.code_executor import CodeExecutor
        executor = CodeExecutor()
        code = parameters.get("code", "")
        language = parameters.get("language", "python")
        timeout = parameters.get("timeout", 15)
        if language == "python":
            return executor.execute_python(code, timeout=timeout)
        else:
            valid, msg = executor.validate_syntax(code, language)
            return {"success": valid, "output": msg}

    elif tool_name == "edit_file":
        path = parameters.get("path", "")
        changes = parameters.get("changes", [])
        if not path:
            raise ValueError("edit_file requires a path")
        content = file_tools.file_read(path)
        if isinstance(content, dict) and content.get("error"):
            raise FileNotFoundError(content["error"])
        # Apply changes (list of {"old": "...", "new": "..."} dicts)
        text = content if isinstance(content, str) else str(content)
        for change in changes:
            old = change.get("old", "")
            new = change.get("new", "")
            if old and old in text:
                text = text.replace(old, new, 1)
        return file_tools.file_write(path, text)

    elif tool_name == "run_command":
        # System command execution
        return "Command blocked in cognitive abstraction."

    else:
        raise ValueError(f"Unsupported tool: {tool_name}")
