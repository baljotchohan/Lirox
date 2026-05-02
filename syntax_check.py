import sys
import traceback

try:
    import lirox.utils.llm
    print("Success: No syntax errors.")
except Exception as e:
    print("Error during import:")
    traceback.print_exc()
