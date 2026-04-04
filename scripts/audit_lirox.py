import os
import time
from lirox.tools.terminal import run_command
from lirox.tools.browser import BrowserTool
from lirox.tools.file_io import FileIOTool
from lirox.utils.llm import generate_response, available_providers

def audit_lirox_tools():
    print("🧹 AUDITING LIROX CORE v2.0...")
    
    # 1. LLM Provider Audit
    print("\n[LLM Provider Audit]")
    avail = available_providers()
    print(f"Available Providers: {avail}")
    if not avail:
        print("❌ CRITICAL: No API keys detected.")
    else:
        test_prompt = "Say 'test success'"
        for p in avail:
            res = generate_response(test_prompt, p)
            if "error" in res.lower() or "missing" in res.lower():
                print(f"❌ Provider {p} failed: {res}")
            else:
                print(f"✅ Provider {p} works: {res.strip()}")

    # 2. Terminal Command Audit
    print("\n[Terminal Command Audit]")
    safe_cmd = "echo 'Lirox Terminal Test' && pwd"
    res_raw = run_command(safe_cmd)
    if "Lirox Terminal Test" in res_raw:
        print(f"✅ Terminal command success: {res_raw.strip()}")
    else:
        print(f"❌ Terminal command failed: {res_raw}")

    # 3. Browser Tool Audit
    print("\n[Browser Tool Audit]")
    browser = BrowserTool()
    search_query = "Lirox AI agent"
    try:
        results = browser.search_web(search_query, num_results=2)
        if results and len(results) > 0:
            print(f"✅ Browser search success ({len(results)} results).")
            # Test fetch
            content = browser.summarize_page(results[0]["url"])
            if content and len(content) > 10:
                print(f"✅ Browser fetch success ({len(content)} chars).")
            else:
                print(f"❌ Browser fetch empty content.")
        else:
            print(f"❌ Browser search returned 0 results for '{search_query}'.")
    except Exception as e:
        print(f"❌ Browser tool error: {str(e)}")

    # 4. File I/O Audit
    print("\n[File I/O Audit]")
    file_io = FileIOTool()
    test_file = "outputs/audit_test.txt"
    try:
        file_io.write_file(test_file, "Audit line 1\nAudit line 2")
        if file_io.file_exists(test_file):
            content = file_io.read_file(test_file)
            if "Audit line 2" in content:
                print(f"✅ File I/O success.")
            else:
                print(f"❌ File I/O read data mismatch.")
        else:
            print(f"❌ File I/O write failed, file not found.")
    except Exception as e:
        print(f"❌ File I/O tool error: {str(e)}")

    print("\n🎉 AUDIT COMPLETE. See details above.")

if __name__ == "__main__":
    audit_lirox_tools()
