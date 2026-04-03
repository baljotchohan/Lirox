"""
Lirox v0.8 — Unified Execution Bridge

Routes queries to optimal execution mode and orchestrates:
- CHAT: Direct LLM response
- RESEARCH: Multi-source synthesis
- BROWSER: Direct scraping
- HYBRID: Research + Browser verification
"""

import json
from typing import Dict, Optional, Tuple
from datetime import datetime

from lirox.agent.researcher import Researcher
from lirox.tools.browser_tool import HeadlessBrowserTool
from lirox.tools.browser import BrowserTool
from lirox.utils.llm import generate_response
from lirox.utils.smart_router import SmartRouter
from lirox.utils.data_enrichment import DataEnrichmentEngine, EnrichedSource


class UnifiedExecutor:
    """
    Executes queries using optimal mode selected by SmartRouter.
    Coordinates research, browser, and LLM tools.
    """
    
    def __init__(self, provider: str = "auto", verbose: bool = False):
        self.provider = provider
        self.verbose = verbose
        
        # Initialize components
        self.router = SmartRouter(provider=provider, verbose=verbose)
        self.researcher = Researcher(BrowserTool(), provider=provider)
        self.browser_tool = HeadlessBrowserTool()
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
            # Step 1: Route query
            routing = self.router.route(user_input)
            
            if self.verbose:
                print(f"\n[UNIFIED EXECUTOR]")
                print(f"Mode: {routing['mode']} (confidence: {routing['confidence']:.0%})")
            
            # Step 2: Execute based on mode
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
            enriched_sources = self.enrichment_engine.enrich_sources(
                sources=[{
                    "url": s.url,
                    "title": s.title,
                    "snippet": s.snippet,
                    "domain": s.domain,
                } for s in report.sources],
                query=user_input,
                verify_real_time=parameters.get("verify_sources", True)
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
        """Execute BROWSER mode: Direct page scraping."""
        
        try:
            urls = parameters.get("urls", [])
            
            if not urls:
                return {
                    "status": "error",
                    "error": "No URLs found to scrape.",
                    "answer": "Please provide a URL to scrape.",
                }
            
            results = []
            
            for url in urls:
                fetch_result = self.browser_tool.fetch_page(
                    url,
                    extract=parameters.get("extract_type", "all"),
                    timeout=parameters.get("timeout", 30)
                )
                
                if fetch_result.get("status") == "success":
                    results.append({
                        "url": url,
                        "title": fetch_result.get("metadata", {}).get("title", ""),
                        "content": fetch_result.get("data", {}).get("markdown", "")[:2000],
                        "method": fetch_result.get("metadata", {}).get("method", "unknown"),
                    })
            
            if not results:
                return {
                    "status": "error",
                    "error": "Failed to fetch pages.",
                    "answer": "Could not extract content from the provided URLs.",
                }
            
            # Format answer
            answer_parts = []
            for result in results:
                answer_parts.append(f"## {result['title']}\n\n{result['content']}")
            
            answer = "\n\n---\n\n".join(answer_parts)
            
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
