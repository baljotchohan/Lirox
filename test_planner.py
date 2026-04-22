import sys
import os
sys.path.insert(0, os.path.abspath("."))
from lirox.utils.llm import generate_response

plan_prompt = """You are a document generation planner. The user wants a file created.

USER REQUEST: create a pdf about ai
DEFAULT WORKSPACE: /tmp
OUTPUTS DIRECTORY: /tmp
USER NAME: User

TASK: Determine the file type, output path, and generate COMPLETE, RICH content.

Output ONLY this JSON — no other text:
{
  "file_type": "pdf",
  "path": "/tmp/test.pdf",
  "title": "Document Title",
  "sections": [
    {"heading": "Section Title", "body": "Full paragraph text here. Multiple sentences with real content.", "bullets": ["Detailed point 1", "Detailed point 2"]}
  ]
}
"""

print(generate_response(plan_prompt, provider="auto", system_prompt="Document planner. Output ONLY the JSON object. No explanation."))
