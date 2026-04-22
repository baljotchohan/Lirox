import os
import re

# 1. Update personal_agent.py
agent_path = "lirox/agents/personal_agent.py"
with open(agent_path, "r") as f:
    agent_code = f.read()

start_idx = agent_code.find("    def _filegen(self, query, context, sp=\"\"):")
end_idx = agent_code.find("    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n    # FILE OPERATIONS")

new_methods = """    def _filegen(self, query, context, sp=""):
        from lirox.tools.document_creators import create_pdf, create_docx, create_xlsx, create_pptx
        from lirox.verify import FileVerificationEngine, ContentQualityVerifier
        from lirox.tools.content_generator import ContentGenerator
        from lirox.config import WORKSPACE_DIR, OUTPUTS_DIR
        from lirox.utils.input_sanitizer import sanitize_user_name
        from datetime import datetime

        yield {"type": "agent_progress", "message": "📄 Planning document generation…"}

        user_name = sanitize_user_name(self.profile_data.get("user_name", ""))

        # ── STEP 1: Determine file type, path, and content via LLM ──
        plan_prompt = f\"\"\"You are a document generation planner. The user wants a file created.

USER REQUEST: {query}
DEFAULT WORKSPACE: {WORKSPACE_DIR}
OUTPUTS DIRECTORY: {OUTPUTS_DIR}
USER NAME: {user_name or 'User'}

TASK: Determine the file type, output path, and generate COMPLETE, RICH content.

CONTENT QUALITY RULES:
- Generate AT LEAST 3-4 sentences per section — never just bullet points
- Include specific facts, statistics, dates, and examples
- Vary the content structure — mix paragraphs, key stats, comparisons
- For presentations: create 8+ slides with rich bullet points (4-6 per slide)
- For PDFs: write full prose paragraphs, not just bullet lists
- Always include an introduction and conclusion section
- Add real value — don't restate the topic title as a sentence

Output ONLY this JSON — no other text:
{{
  "file_type": "pdf|docx|xlsx|pptx",
  "path": "/absolute/path/to/filename.ext",
  "title": "Document Title",
  "sections": [
    {{"heading": "Section Title", "body": "Full paragraph text here. Multiple sentences with real content.", "bullets": ["Detailed point 1", "Detailed point 2"]}}
  ],
  "sheets": [
    {{"name": "Sheet1", "headers": ["Column A", "Column B"], "rows": [["data1", "data2"]]}}
  ],
  "slides": [
    {{"title": "Slide Title", "bullets": ["Rich bullet with detail and context", "Another substantial point with examples", "A third point with specific facts", "Fourth point with actionable insight"], "notes": "Speaker notes with additional context"}}
  ]
}}

IMPORTANT:
- Use "sections" for pdf and docx files
- Use "sheets" for xlsx files
- Use "slides" for pptx files — generate AT LEAST 6-8 content slides
- Generate ALL content NOW — complete paragraphs, real data, full bullet points
- Each bullet should be a full sentence or detailed phrase, NOT just 2-3 words
- For {query}: generate rich, detailed, informative, expert-level content\"\"\"

        raw = generate_response(plan_prompt, provider="auto",
                                system_prompt="Document planner. Output ONLY the JSON object. No explanation.")

        # ── STEP 2: Parse the plan with triple-layer fallback ──
        from lirox.utils.llm import is_error_response
        if is_error_response(raw):
            yield {"type": "error", "message": f"❌ LLM provider error: {raw[:200]}"}
            yield from self._chat(query, context, sp)
            return
        
        d = None
        try:
            d = _extract_json(raw)
            if not d or not isinstance(d, dict):
                raise ValueError("JSON extraction returned None or non-dict")
        except ValueError:
            _logger.warning("JSON extraction failed, attempting fallback")
            d = self._filegen_fallback(query)
            if not d:
                yield {"type": "error", "message": "❌ Could not parse document plan from LLM."}
                yield from self._chat(query, context, sp)
                return

        # ── STEP 3: Validate and normalize plan dict ──
        file_type = (d.get("file_type") or "").lower().strip()
        path = (d.get("path") or "").strip()
        title = (d.get("title") or "").strip()

        if not file_type:
            q = query.lower()
            if any(w in q for w in ["pdf"]):
                file_type = "pdf"
            elif any(w in q for w in ["word", "docx", "doc", "document"]):
                file_type = "docx"
            elif any(w in q for w in ["excel", "xlsx", "spreadsheet", "xls"]):
                file_type = "xlsx"
            elif any(w in q for w in ["ppt", "pptx", "powerpoint", "presentation", "slide", "deck"]):
                file_type = "pptx"
            else:
                file_type = "pdf"

        if not title:
            title = f"Generated {file_type.upper()}"

        # ── STEP 4: Resolve output path with safety checks ──
        ext_map = {"pdf": ".pdf", "docx": ".docx", "xlsx": ".xlsx", "pptx": ".pptx"}
        ext = ext_map.get(file_type, ".pdf")

        if not path:
            q = query.lower()
            if "desktop" in q:
                base_dir = os.path.expanduser("~/Desktop")
            elif "download" in q:
                base_dir = os.path.expanduser("~/Downloads")
            elif "document" in q:
                base_dir = os.path.expanduser("~/Documents")
            else:
                base_dir = WORKSPACE_DIR

            safe_name = re.sub(r'[^\\w\\s-]', '', title).strip().replace(' ', '_')[:50]
            if not safe_name:
                safe_name = f"document_{int(time.time())}"
            path = os.path.join(base_dir, safe_name + ext)
        
        if not path.endswith(ext):
            base = path.rsplit('.', 1)[0] if '.' in os.path.basename(path) else path
            path = base + ext

        try:
            path = _resolve_path(path, query)
        except (PermissionError, ValueError) as pe:
            yield {"type": "error", "message": f"❌ Path validation failed: {pe}"}
            return

        # Ensure parent directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)

        # ── STEP 4b: Ensure sections/slides/sheets are proper lists ──
        if file_type in ("pdf", "docx"):
            sections = d.get("sections", [])
            if not isinstance(sections, list):
                sections = []
            if not sections:
                sections = [{"heading": "Content", "body": query[:500], "bullets": []}]
            d["sections"] = sections

        elif file_type == "xlsx":
            sheets = d.get("sheets", [])
            if not isinstance(sheets, list):
                sheets = []
            if not sheets:
                sheets = [{"name": "Sheet1", "headers": ["Data"], "rows": [[query[:100]]]}]
            d["sheets"] = sheets

        elif file_type == "pptx":
            slides = d.get("slides", [])
            if not isinstance(slides, list):
                slides = []
            if not slides:
                slides = [{"title": title, "bullets": [query[:80]], "notes": ""}]
            d["slides"] = slides

        # ── STEP 4c: Content quality check — enrich thin content via ContentGenerator ──
        quality_check = ContentQualityVerifier.check(file_type, d)
        if quality_check.get("issues"):
            yield {"type": "agent_progress", "message": "📝 Enriching document content…"}
            try:
                gen = ContentGenerator()
                topic = title or query[:80]
                enriched = gen.generate(file_type, topic, query=query)
                for key in ("slides", "sections", "sheets"):
                    if enriched.get(key) and (not d.get(key) or quality_check.get("issues")):
                        d[key] = enriched[key]
            except Exception as _ce:
                _logger.warning("ContentGenerator failed: %s", _ce)

        # ── STEP 4d: Add user context to content ──
        context_header = ""
        if user_name and user_name.lower() not in ("lirox", "lirox ai", "", "unknown"):
            context_header = (
                f"Document prepared for {user_name}\\n"
                f"Topic: {query}\\n"
                f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}\\n\\n"
            )

        if file_type in ("pdf", "docx") and context_header:
            if d.get("sections") and len(d["sections"]) > 0:
                first_section = d["sections"][0]
                if first_section.get("body"):
                    first_section["body"] = context_header + first_section["body"]
                else:
                    first_section["body"] = context_header

        yield {"type": "tool_call", "message": f"📄 Creating {file_type.upper()}: {os.path.basename(path)}"}

        # ── STEP 5: EXECUTE — Actually create the file ──
        receipt = None
        try:
            if file_type == "pdf":
                sections = d.get("sections", [])
                if not isinstance(sections, list) or not sections:
                    sections = [{"heading": title, "body": query[:500], "bullets": []}]
                receipt = create_pdf(path, title, sections,
                                     query=query, user_name=user_name)

            elif file_type == "docx":
                sections = d.get("sections", [])
                if not isinstance(sections, list) or not sections:
                    sections = [{"heading": title, "body": query[:500], "bullets": []}]
                receipt = create_docx(path, title, sections,
                                      query=query, user_name=user_name)

            elif file_type == "xlsx":
                sheets = d.get("sheets", [])
                if not isinstance(sheets, list) or not sheets:
                    sheets = [{"name": "Sheet1", "headers": ["Data"], "rows": [[query[:100]]]}]
                receipt = create_xlsx(path, title, sheets,
                                      query=query, user_name=user_name)

            elif file_type == "pptx":
                slides = d.get("slides", [])
                if not isinstance(slides, list) or not slides:
                    slides = [{"title": title, "bullets": [query[:80]], "notes": ""}]
                receipt = create_pptx(path, title, slides,
                                      query=query, user_name=user_name)

            else:
                receipt = FileReceipt(tool="file_generator", operation="create",
                                      error=f"Unknown file type: {file_type}")

        except Exception as e:
            _logger.exception("File creation exception: %s", e)
            receipt = FileReceipt(tool="file_generator", operation="create",
                                  path=path, error=f"File creation error: {e}")

        if receipt is None:
            receipt = FileReceipt(tool="file_generator", operation="create", path=path,
                                  error="File creation returned None receipt")

        # ── STEP 6: VERIFY — Check the file actually exists and has real content ──
        if receipt.ok and receipt.verified:
            fv = FileVerificationEngine.verify(path)
            if fv["passed"]:
                yield {"type": "tool_result", "message": f"✅ Created {file_type.upper()}: {path} ({receipt.bytes_written:,} bytes)"}
                creator_credit = f"Created for {user_name}" if user_name else "Document created"
                answer = (f"✅ {creator_credit}: **{os.path.basename(path)}**\\n\\n"
                          f"📁 Path: `{path}`\\n"
                          f"📊 Size: {receipt.bytes_written:,} bytes\\n"
                          f"📄 Content: {self._count_content(d, file_type)}\\n\\n"
                          f"Your {file_type.upper()} is ready to download and share.")
            else:
                issues_str = "; ".join(fv["issues"])
                yield {"type": "tool_result", "message": f"⚠️ File created but verification flagged issues: {issues_str}"}
                answer = (f"Created **{os.path.basename(path)}** at `{path}` "
                          f"({receipt.bytes_written:,} bytes). "
                          f"Note: {issues_str}")
        else:
            error_msg = receipt.error or "Unknown file creation error"
            yield {"type": "tool_result", "message": f"❌ {error_msg}"}
            answer = f"Failed to create the file: {error_msg}"

        for chunk in _STREAMER.stream_words(answer, delay=0.025):
            yield {"type": "streaming", "message": chunk}
        yield {"type": "done", "answer": answer}

    def _count_content(self, d: dict, file_type: str) -> str:
        \"\"\"Human-readable content summary.\"\"\"
        if not d or not isinstance(d, dict):
            return "unknown amount"
        
        if file_type == "pptx":
            slides = d.get("slides", [])
            if not isinstance(slides, list):
                return "unknown amount"
            n = len(slides)
            return f"{n} slide{'s' if n != 1 else ''}"
        elif file_type == "xlsx":
            sheets = d.get("sheets", [])
            if not isinstance(sheets, list):
                return "unknown amount"
            total_rows = sum(len(s.get("rows", []) if isinstance(s, dict) else []) for s in sheets)
            return f"{len(sheets)} sheet{'s' if len(sheets) != 1 else ''}, {total_rows} rows"
        else:
            sections = d.get("sections", [])
            if not isinstance(sections, list):
                return "unknown amount"
            n = len(sections)
            return f"{n} section{'s' if n != 1 else ''}"

    def _filegen_fallback(self, query: str) -> dict:
        \"\"\"Last-resort: build a complete, valid plan from the query itself.\"\"\"
        q = query.lower()
        file_type = "pdf"
        if any(w in q for w in ["ppt", "powerpoint", "presentation", "slide", "deck"]):
            file_type = "pptx"
        elif any(w in q for w in ["excel", "xlsx", "spreadsheet", "xls"]):
            file_type = "xlsx"
        elif any(w in q for w in ["word", "docx", "doc"]):
            file_type = "docx"

        title = query[:80] if query else "Untitled Document"
        
        fallback = {
            "file_type": file_type,
            "title": title,
            "path": "",  
            "sections": [{"heading": "Content", "body": query[:500], "bullets": []}],
            "slides": [{"title": title, "bullets": ["Content based on: " + query[:60]], "notes": ""}],
            "sheets": [{"name": "Sheet1", "headers": ["Info"], "rows": [[query[:100]]]}],
        }
        
        return fallback
"""
if start_idx != -1 and end_idx != -1:
    agent_code = agent_code[:start_idx] + new_methods + "\n" + agent_code[end_idx:]
    with open(agent_path, "w") as f:
        f.write(agent_code)
    print("Updated personal_agent.py")
