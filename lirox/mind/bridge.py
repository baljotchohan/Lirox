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
        raw_name = parameters.get("filename", "presentation.pptx")
        # Use only the final filename component to avoid path traversal
        stem = _Path(raw_name).stem or "presentation"
        filename = stem + ".pptx"
        path = str(_Path(workspace) / filename)
        topic = parameters.get("topic", "Untitled")

        # We need to generate slides inline because the planner doesn't provide them
        sys_prompt = "You are a slide generator. Output ONLY raw JSON matching: [{'title': '...', 'content': ['...', '...']}] for 8+ slides."
        slides_json = generate_response(f"Topic: {topic}. Generate 8 slides.", system_prompt=sys_prompt)
        import json
        try:
            # very naive extraction
            import re
            m = re.search(r'\[\s*\{.*\}\s*\]', slides_json, re.DOTALL)
            if m: slides = json.loads(m.group(0))
            else: slides = json.loads(slides_json)
        except:
            # fallback
            slides = [{"title": topic, "content": ["Slide 1 content", "More content"]}]

        return file_generator.create_pptx(path, topic, slides)
        
    elif tool_name == "create_pdf":
        import os
        from pathlib import Path as _Path
        from lirox.config import WORKSPACE_DIR
        workspace = os.getenv("LIROX_WORKSPACE", WORKSPACE_DIR)
        raw_name = parameters.get("filename", "document.pdf")
        # Use only the final filename component to avoid path traversal
        stem = _Path(raw_name).stem or "document"
        filename = stem + ".pdf"
        path = str(_Path(workspace) / filename)
        topic = parameters.get("topic", "Untitled")
        # Likewise, inline generation of paragraph blocks
        sys_prompt = "You are a PDF content generator. Output ONLY raw JSON matching: [{'title': '...', 'blocks': [{'type': 'paragraph', 'text': '...'}]}]"
        pdf_json = generate_response(f"Topic: {topic}. Generate 5 sections.", system_prompt=sys_prompt)
        import json
        try:
            import re
            m = re.search(r'\[\s*\{.*\}\s*\]', pdf_json, re.DOTALL)
            if m: sections = json.loads(m.group(0))
            else: sections = json.loads(pdf_json)
        except:
            sections = [{"title": topic, "blocks": [{"type": "paragraph", "text": "Content"}]}]

        return file_generator.create_pdf(path, topic, sections)
    
    elif tool_name == "run_command":
        # System command execution
        return "Command blocked in cognitive abstraction."
        
    else:
        raise ValueError(f"Unsupported tool: {tool_name}")
