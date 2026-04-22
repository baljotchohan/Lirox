import sys
import os
sys.path.insert(0, os.path.abspath("."))
from lirox.mind.bridge import cognitive_tool_executor

print(cognitive_tool_executor("create_pdf", {"topic": "ai"}))
