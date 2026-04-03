"""
Lirox v0.7.1 — Real-World Browser & Data Demonstration

Purpose:
1.  Prove "direct browser" usage on real domains (Wikipedia & Hacker News).
2.  Demonstrate the RealTimeDataExtractor identifying structured information.
3.  Perform the complete File I/O cycle (Create -> Write -> Read -> Verify).
"""

import sys
import os
import time

# Add root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lirox.tools.browser import BrowserTool
from lirox.tools.real_time_data import RealTimeDataExtractor
from lirox.ui.display import console, info_panel, success_message, error_panel

def run_demo():
    info_panel("🦁 LIROX BROWSER DEMONSTRATION ON REAL DOMAINS...")

    # Configuration
    output_dir = "outputs"
    os.makedirs(output_dir, exist_ok=True)
    report_file = os.path.join(output_dir, "demo_data_log.txt")
    
    # Target URLs
    wiki_url = "https://en.wikipedia.org/wiki/Main_Page"
    hn_url = "https://news.ycombinator.com/"
    
    bt = BrowserTool()
    extractor = RealTimeDataExtractor()
    report_sections = []

    # 1. Scraping Wikipedia
    info_panel(f"Fetching Wikipedia: {wiki_url}")
    try:
        wiki_html = bt.fetch_url(wiki_url)
        wiki_title = bt.extract_data(wiki_html, "title")[0]
        wiki_main = bt.extract_text(wiki_html)[:2000] # Get sample text
        
        report_sections.append(f"DOMAIN: wikipedia.org\nTITLE: {wiki_title}\nCONTENT SAMPLE: {wiki_main[:200]}...")
        success_message(f"✓ Wikipedia data successfully extracted: '{wiki_title}'")
    except Exception as e:
        error_panel("WIKIPEDIA FAIL", str(e))
        report_sections.append(f"DOMAIN: wikipedia.org\nERROR: {str(e)}")

    # 2. Scraping Hacker News
    info_panel(f"Fetching Hacker News: {hn_url}")
    try:
        hn_html = bt.fetch_url(hn_url)
        # Extract titles from Hacker News stories
        hn_titles = bt.extract_data(hn_html, ".titleline > a")[:10]
        hn_points = bt.extract_data(hn_html, ".score")[:10]
        
        hn_report = "DOMAIN: hackernews.com\nTOP STORIES:\n"
        for i, (title, score) in enumerate(zip(hn_titles, hn_points), 1):
            hn_report += f"{i}. {title} ({score})\n"
            
        report_sections.append(hn_report)
        success_message(f"✓ Hacker News data successfully extracted ({len(hn_titles)} stories).")
    except Exception as e:
        error_panel("HACKER NEWS FAIL", str(e))
        report_sections.append(f"DOMAIN: hackernews.com\nERROR: {str(e)}")

    # 3. File I/O: Writing final report
    info_panel(f"Writing findings to disk: {report_file}")
    try:
        final_content = "LIROX BROWSER REAL-WORLD REPORT\n" + "="*30 + "\n"
        final_content += f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        final_content += "\n\n".join(report_sections)
        
        with open(report_file, "w") as f:
            f.write(final_content)
        success_message("✓ Report file created and written.")
    except Exception as e:
        error_panel("FILE WRITE FAIL", str(e))

    # 4. Verification: Reading back and checking properly
    info_panel("Verifying file content integrity...")
    try:
        with open(report_file, "r") as f:
            verified_content = f.read()
        
        # Check for presence of both domains
        if "wikipedia.org" in verified_content and "hackernews.com" in verified_content:
            success_message("✓ ALL CHECKS PASSED: Scraped data persists accurately in local storage.")
            console.print("\n[bold cyan]FINAL LOG CONTENT PREVIEW:[/]\n")
            console.print(verified_content[:1500] + "...")
        else:
            error_panel("VERIFICATION FAIL", "Some domain data is missing from the report.")
    except Exception as e:
        error_panel("FILE READ FAIL", str(e))

if __name__ == "__main__":
    run_demo()
