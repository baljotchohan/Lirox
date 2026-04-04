"""
Lirox v2.0 — Browser System Verification Script

Purpose:
1.  Demonstrate direct browser usage (fetching/scraping) without search APIs.
2.  Test both HTTP-based (BrowserTool) and CDP-based (HeadlessBrowserTool) pathways.
3.  Perform file operations (create, write, read) based on scraped data.
4.  Verify data extraction (title, text, selectors).
"""

import sys
import os
import time
import requests

# Add root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lirox.tools.browser import BrowserTool
from lirox.tools.browser_tool import HeadlessBrowserTool
from lirox.ui.display import console, info_panel, success_message, error_panel

def run_verification():
    # ─── SETUP ───────────────────────────────────────────────────────────────
    info_panel("INITIATING BROWSER V0.7.1 VERIFICATION...")
    
    output_dir = "outputs"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "verification_browser.txt")
    
    target_url = "https://example.com"
    verification_results = []

    # ─── 1. HTTP BROWSER TEST (BrowserTool) ──────────────────────────────────
    info_panel(f"Testing BrowserTool (HTTP fallback) on {target_url}...")
    try:
        bt = BrowserTool()
        html = bt.fetch_url(target_url)
        text = bt.extract_text(html)
        title = bt.extract_data(html, "h1")
        
        title_text = title[0] if title else "No H1 found"
        verification_results.append(f"BrowserTool Title: {title_text}")
        verification_results.append(f"BrowserTool Text Sample: {text[:100]}...")
        success_message(f"BrowserTool: ✓ Fetched and extracted '{title_text}'")
    except Exception as e:
        error_panel("BROWSER TOOL ERROR", str(e))
        verification_results.append(f"BrowserTool Error: {str(e)}")

    # ─── 2. HEADLESS BROWSER TEST (HeadlessBrowserTool) ──────────────────────
    info_panel(f"Testing HeadlessBrowserTool (CDP) on {target_url}...")
    try:
        hb = HeadlessBrowserTool()
        # Fetch markdown extract
        result = hb.fetch_page(target_url, extract="markdown")
        
        if result.get("status") == "success":
            md_content = result.get("data", {}).get("markdown", "")
            meta = result.get("metadata", {})
            title_meta = meta.get("title", "N/A")
            
            verification_results.append(f"Headless Title: {title_meta}")
            verification_results.append(f"Headless Content Sample: {md_content[:100]}...")
            success_message(f"HeadlessBrowserTool: ✓ Fetched '{title_meta}' via {meta.get('method', 'unknown')}")
        else:
            reason = result.get("error", "Unknown error")
            verification_results.append(f"Headless Error: {reason}")
            error_panel("HEADLESS BROWSER FAIL", reason)
    except Exception as e:
        error_panel("HEADLESS BROWSER CRASH", str(e))
        verification_results.append(f"Headless Crash: {str(e)}")

    # ─── 3. FILE OPERATIONS (Create/Write) ───────────────────────────────────
    info_panel(f"Synchronizing results to file: {output_file}...")
    try:
        content_to_write = "LIROX BROWSER VERIFICATION LOG\n" + "="*30 + "\n"
        content_to_write += f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        content_to_write += f"Target URL: {target_url}\n\n"
        content_to_write += "\n".join(verification_results)
        
        with open(output_file, "w") as f:
            f.write(content_to_write)
        
        success_message("✓ Results written to file.")
    except Exception as e:
        error_panel("FILE WRITE ERROR", str(e))

    # ─── 4. FILE OPERATIONS (Read/Verify) ────────────────────────────────────
    info_panel("Verifying file integrity...")
    try:
        with open(output_file, "r") as f:
            read_back = f.read()
            
        if "BrowserTool Title" in read_back and target_url in read_back:
            success_message("✓ Verification Complete: File content matches expectations.")
            console.print("\n[bold cyan]FINAL LOG CONTENT:[/]\n")
            console.print(read_back)
        else:
            error_panel("VERIFICATION FAIL", "File content was incomplete or corrupted.")
    except Exception as e:
        error_panel("FILE READ ERROR", str(e))

if __name__ == "__main__":
    run_verification()
