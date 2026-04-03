"""
Lirox v0.8.5 — Unified Execution Bridge

Routes queries to optimal execution mode and orchestrates:
- CHAT: Direct LLM response
- RESEARCH: Multi-source synthesis
- BROWSER: Direct scraping (with requests fallback)
- HYBRID: Research + Browser verification
"""

import re
import json
from typing import Dict, Optional, Tuple
from datetime import datetime

from lirox.agent.researcher import Researcher
from lirox.tools.browser import BrowserTool
from lirox.utils.llm import generate_response
from lirox.utils.smart_router import SmartRouter
from lirox.utils.data_enrichment import DataEnrichmentEngine, EnrichedSource

# Lazy import — don't crash if Lightpanda not installed
try:
    from lirox.tools.browser_tool import HeadlessBrowserTool
    _HAS_HEADLESS = True
except ImportError:
    _HAS_HEADLESS = False
    HeadlessBrowserTool = None


class UnifiedExecutor:
    """
    Executes queries using optimal mode selected by SmartRouter.
    Coordinates research, browser, and LLM tools.
    Falls back to requests-based browser when Lightpanda is unavailable.
    """

    def __init__(self, provider: str = "auto", verbose: bool = False):
        self.provider = provider
        self.verbose = verbose

        # Initialize components
        self.router = SmartRouter(provider=provider, verbose=verbose)
        self.researcher = Researcher(BrowserTool(), provider=provider)

        # Safe headless browser init — never crash if binary missing
        self.browser_tool = None
        if _HAS_HEADLESS:
            try:
                self.browser_tool = HeadlessBrowserTool()
            except Exception:
                pass

        self.enrichment_engine = DataEnrichmentEngine(
            browser_tool=self.browser_tool,
            verbose=verbose
        )

        self.last_execution = None
    
    # ─── MAIN EXECUTION ENTRY POINT ──────────────────────────────────────────
    
    def execute(self, user_input: str, 
               system_prompt: Optional[str] = None) -> Dict:
        """
        Execute query using optimal mode.
        
        Args:
            user_input: User's query
            system_prompt: Optional system prompt for LLM
        
        Returns:
            {
                "status": "success|error",
                "mode": "chat|research|browser|hybrid",
                "answer": str,
                "sources": [...],
                "confidence": 0.0-1.0,
                "verification_status": "verified|partial|unverified",
                "metadata": {...}
            }
        """
        
        execution_start = datetime.now()

        try:
            # Step 1: Route query (also pre-fetches free data shortcut)
            routing = self.router.route(user_input)

            if self.verbose:
                print(f"\n[UNIFIED EXECUTOR]")
                print(f"Mode: {routing['mode']} (confidence: {routing['confidence']:.0%})")

            # ── Phase 5 shortcut: if free real-time data was fetched, return it NOW
            #    without running the LLM pipeline (prevents hallucination of prices).
            free_data = routing.get("free_data")
            if free_data:
                # Local system query (e.g. "how many files on desktop")
                if free_data.get("status") == "local":
                    # Run as CHAT — LLM will use terminal tool or system knowledge
                    result = self._execute_chat(
                        f"[LOCAL TASK] Use the system terminal to answer: {user_input}",
                        system_prompt,
                    )
                    result["mode"] = "chat"
                    result["routing_confidence"] = routing["confidence"]
                    result["fallback_mode"] = routing["fallback_mode"]
                    result["execution_time"] = (datetime.now() - execution_start).total_seconds()
                    self.last_execution = result
                    return result

                # Real live data (stocks, crypto, weather, etc.)
                if free_data.get("status") == "success" and free_data.get("answer"):
                    source = free_data.get("source", "free_api")
                    answer = free_data["answer"]
                    is_live = free_data.get("live", False)
                    note = " (live data)" if is_live else ""
                    result = {
                        "status": "success",
                        "mode": "free_data",
                        "answer": answer,
                        "sources": [{"source": source, "note": f"Real-time via {source}{note}"}],
                        "confidence": 0.97,
                        "verification_status": "verified",
                        "routing_confidence": routing["confidence"],
                        "fallback_mode": routing["fallback_mode"],
                        "execution_time": (datetime.now() - execution_start).total_seconds(),
                        "source": source,
                    }
                    self.last_execution = result
                    return result

            # Step 2: Execute based on mode (no free data shortcut available)
            if routing["mode"] == "chat":
                result = self._execute_chat(user_input, system_prompt)

            elif routing["mode"] == "research":
                result = self._execute_research(
                    user_input,
                    routing["parameters"],
                    system_prompt
                )

            elif routing["mode"] == "browser":
                result = self._execute_browser(user_input, routing["parameters"])

            elif routing["mode"] == "hybrid":
                result = self._execute_hybrid(
                    user_input,
                    routing["parameters"],
                    system_prompt
                )

            else:
                result = self._execute_chat(user_input, system_prompt)

            # Add metadata
            result["mode"] = routing["mode"]
            result["routing_confidence"] = routing["confidence"]
            result["fallback_mode"] = routing["fallback_mode"]
            result["execution_time"] = (datetime.now() - execution_start).total_seconds()

            self.last_execution = result
            return result

        except Exception as e:
            if self.verbose:
                print(f"[EXECUTION ERROR] {str(e)}")

            return {
                "status": "error",
                "error": str(e),
                "mode": "error",
                "answer": "Sorry, I encountered an error processing your query.",
                "execution_time": (datetime.now() - execution_start).total_seconds(),
            }
    
    # ─── EXECUTION MODES ────────────────────────────────────────────────────
    
    def _execute_chat(self, user_input: str, 
                     system_prompt: Optional[str]) -> Dict:
        """Execute CHAT mode: Direct LLM response."""
        
        try:
            answer = generate_response(
                user_input,
                self.provider,
                system_prompt=system_prompt
            )
            
            return {
                "status": "success",
                "answer": answer,
                "sources": [],
                "confidence": 1.0,
                "verification_status": "n/a",
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "answer": "Failed to generate response.",
            }
    
    def _execute_research(self, user_input: str, 
                         parameters: Dict,
                         system_prompt: Optional[str]) -> Dict:
        """Execute RESEARCH mode: Multi-source synthesis."""
        
        try:
            # Run research
            report = self.researcher.research(
                user_input,
                depth=parameters.get("depth", "standard")
            )
            
            # Enrich with browser content if needed
            verify_real_time = parameters.get("verify_sources", True)
            if not verify_real_time and self.researcher._is_realtime_data_query(user_input):
                verify_real_time = True
                if self.verbose:
                    print("  [RESEARCH] Real-time data detected — forcing browser verification")

            enriched_sources = self.enrichment_engine.enrich_sources(
                sources=[{
                    "url": s.url,
                    "title": s.title,
                    "snippet": s.snippet,
                    "domain": s.domain,
                } for s in report.sources],
                query=user_input,
                verify_real_time=verify_real_time
            )
            
            # Merge results
            merged = self.enrichment_engine.merge_enriched_results(enriched_sources)
            
            return {
                "status": "success",
                "answer": report.summary,
                "sources": [s.to_dict() for s in enriched_sources],
                "key_findings": report.findings,
                "confidence": report.confidence_overall,
                "verification_status": merged["verification_status"],
                "source_count": len(report.sources),
            }

        except Exception as e:
            if self.verbose:
                print(f"[RESEARCH ERROR] {str(e)}")

            return {
                "status": "error",
                "error": str(e),
                "answer": "Failed to complete research.",
            }

    def _execute_browser(self, user_input: str,
                         parameters: Dict) -> Dict:
        """Execute BROWSER mode: Direct page scraping with requests fallback."""

        try:
            urls = parameters.get("urls", [])

            if not urls:
                # Try to extract URL from query text
                url_match = re.search(r'https?://\S+', user_input)
                if url_match:
                    urls = [url_match.group(0).rstrip(".,;)")]
                else:
                    return {
                        "status": "error",
                        "error": "No URL found in query.",
                        "answer": "No URL found. Provide a URL to fetch.",
                    }

            results = []

            for url in urls[:3]:  # Cap at 3 URLs
                content = self._fetch_url_smart(url, user_input)
                if content:
                    results.append(content)

            if not results:
                return {
                    "status": "error",
                    "error": "Failed to fetch pages.",
                    "answer": "Could not extract content from the provided URLs.",
                }

            answer = "\n\n---\n\n".join(
                f"## {r['title']}\n\n{r['content']}" for r in results
            )

            return {
                "status": "success",
                "answer": answer,
                "sources": [{"url": r["url"], "title": r["title"], "method": r["method"]} for r in results],
                "confidence": 0.9,
                "verification_status": "verified",
                "fetched_urls": len(results),
            }

        except Exception as e:
            if self.verbose:
                print(f"[BROWSER ERROR] {str(e)}")

            return {
                "status": "error",
                "error": str(e),
                "answer": "Failed to scrape pages.",
            }

    def _fetch_url_smart(self, url: str, query: str = "") -> dict:
        """Fetch a URL using the best available method (headless → requests fallback)."""
        # Try headless browser first
        if self.browser_tool:
            try:
                if query and len(query) > 10:
                    result = self.browser_tool.fetch_focused_fragment(url, query=query)
                else:
                    result = self.browser_tool.fetch_page(url, extract="markdown", timeout=20)
                if result.get("status") == "success":
                    return {
                        "url": url,
                        "title": result.get("metadata", {}).get("title", url),
                        "content": result.get("data", {}).get("markdown", "")[:3000],
                        "method": "headless",
                    }
            except Exception:
                pass

        # Fallback: requests-based BrowserTool
        try:
            bt = BrowserTool()
            content = bt.summarize_page(url)
            return {
                "url": url,
                "title": url,
                "content": str(content)[:3000],
                "method": "requests",
            }
        except Exception:
            return None
    
    def _execute_hybrid(self, user_input: str,
                       parameters: Dict,
                       system_prompt: Optional[str]) -> Dict:
        """
        Execute HYBRID mode: Research + Browser Verification
        
        Flow:
        1. Use research to find sources
        2. Use browser to verify/fetch full content
        3. Merge and validate across sources
        4. Return comprehensive answer
        """
        
        try:
            # Step 1: Research
            if self.verbose:
                print("  [HYBRID] Step 1: Researching sources...")
            
            report = self.researcher.research(
                user_input,
                depth=parameters.get("depth", "standard")
            )
            
            if not report.sources:
                return {
                    "status": "error",
                    "error": "No sources found for verification.",
                    "answer": "Could not find sources to verify.",
                }
            
            # Step 2: Enrich with browser verification
            if self.verbose:
                print(f"  [HYBRID] Step 2: Verifying {len(report.sources)} sources with browser...")
            
            enriched_sources = self.enrichment_engine.enrich_sources(
                sources=[{
                    "url": s.url,
                    "title": s.title,
                    "snippet": s.snippet,
                    "domain": s.domain,
                } for s in report.sources],
                query=user_input,
                verify_real_time=True
            )
            
            # Step 3: Merge results
            merged = self.enrichment_engine.merge_enriched_results(enriched_sources)
            
            # Step 4: Generate final synthesis
            if self.verbose:
                print("  [HYBRID] Step 3: Synthesizing final answer...")
            
            synthesis_prompt = f"""
            Based on the following verified sources, provide a comprehensive answer to the user's query.
            User Query: {user_input}
            
            {merged['merged_content']}
            
            Rules:
            - Cite sources when making factual claims
            - Note if sources conflict
            - Clearly state your confidence level
            - Be concise and direct
            """
            
            final_answer = generate_response(
                synthesis_prompt,
                self.provider,
                system_prompt=system_prompt
            )
            
            return {
                "status": "success",
                "answer": final_answer,
                "sources": merged["sources"],
                "key_findings": report.findings,
                "confidence": min(
                    report.confidence_overall,
                    merged["enrichment_summary"]["average_confidence"]
                ),
                "verification_status": merged["verification_status"],
                "enrichment_summary": merged["enrichment_summary"],
                "source_count": len(enriched_sources),
            }
        
        except Exception as e:
            if self.verbose:
                print(f"[HYBRID ERROR] {str(e)}")
            
            # Fallback to research only
            try:
                report = self.researcher.research(user_input, depth="standard")
                return {
                    "status": "partial",
                    "answer": report.summary,
                    "sources": [{"url": s.url, "title": s.title} for s in report.sources],
                    "confidence": report.confidence_overall,
                    "verification_status": "unverified",
                    "note": "Browser verification failed, showing research-only results.",
                }
            except:
                return {
                    "status": "error",
                    "error": str(e),
                    "answer": "Failed to complete hybrid execution.",
                }
    
    # ─── UTILITY METHODS ────────────────────────────────────────────────────
    
    def get_last_execution(self) -> Dict:
        """Get details of last execution."""
        return self.last_execution or {}
    
    def get_routing_stats(self) -> Dict:
        """Get routing statistics."""
        return self.router.get_statistics()
