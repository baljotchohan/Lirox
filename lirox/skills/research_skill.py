"""Research skill — multi-source deep research with citations."""

from typing import Dict, Any, List
from lirox.skills import BaseSkill, SkillResult, RiskLevel


class ResearchSkill(BaseSkill):
    
    @property
    def name(self) -> str:
        return "research"
    
    @property
    def description(self) -> str:
        return "Deep multi-source research with citations and confidence scoring"
    
    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW
    
    @property
    def keywords(self) -> List[str]:
        return [
            "research", "investigate", "deep dive", "comprehensive",
            "everything about", "detailed analysis", "compare",
            "report on", "study", "analyze", "findings",
        ]
    
    def execute(self, query: str, context: Dict[str, Any] = None) -> SkillResult:
        """Run the full research pipeline: search → extract → synthesize."""
        from lirox.tools.browser import BrowserTool
        from lirox.agent.tier import get_available_search_apis
        from lirox.utils.llm import generate_response
        import os, requests
        from urllib.parse import urlparse
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        browser = BrowserTool()
        apis = get_available_search_apis()
        
        # 1. Search across available APIs
        all_results = []
        
        # DuckDuckGo (always available)
        ddg_results = browser.search_web(query, num_results=5)
        all_results.extend(ddg_results)
        
        # Tavily if available
        tavily_key = os.getenv("TAVILY_API_KEY")
        if tavily_key:
            try:
                resp = requests.post(
                    "https://api.tavily.com/search",
                    json={"api_key": tavily_key, "query": query, "max_results": 5},
                    timeout=10
                )
                for item in resp.json().get("results", []):
                    all_results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("content", "")[:300],
                        "domain": urlparse(item.get("url", "")).netloc,
                    })
            except Exception:
                pass
        
        # Serper if available
        serper_key = os.getenv("SERPER_API_KEY")
        if serper_key:
            try:
                resp = requests.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": serper_key},
                    json={"q": query, "num": 5},
                    timeout=10
                )
                for item in resp.json().get("organic", []):
                    all_results.append({
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "snippet": item.get("snippet", ""),
                        "domain": urlparse(item.get("link", "")).netloc,
                    })
            except Exception:
                pass
        
        if not all_results:
            return SkillResult(
                success=False, output="No search results found.",
                skill_name=self.name, error="Search returned no results"
            )
        
        # 2. Deduplicate by URL
        seen = set()
        unique = []
        for r in all_results:
            url = r.get("url", "").split("#")[0]
            if url and url not in seen:
                seen.add(url)
                unique.append(r)
        
        # 3. Extract content from top sources (parallel)
        top_sources = unique[:6]
        
        def fetch_content(source):
            try:
                content = browser.summarize_page(source["url"])
                source["content"] = content[:3000]
            except Exception:
                source["content"] = source.get("snippet", "")
            return source
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            top_sources = list(executor.map(fetch_content, top_sources))
        
        # 4. Synthesize with LLM
        source_text = ""
        for i, s in enumerate(top_sources, 1):
            source_text += f"\n--- SOURCE [{i}] ({s.get('domain', '')}) ---\n"
            source_text += f"Title: {s.get('title', '')}\n"
            source_text += f"{s.get('content', s.get('snippet', ''))[:2000]}\n"
        
        synthesis_prompt = (
            f"Synthesize these sources into a clear, cited answer.\n"
            f"Use [1], [2] etc for citations. Rate confidence of each claim.\n"
            f"Be direct and factual. If sources conflict, say so.\n\n"
            f"Query: {query}\n\n"
            f"Sources:\n{source_text}\n\n"
            f"Write clean text, no JSON, no markdown bold."
        )
        
        summary = generate_response(synthesis_prompt, "auto")
        
        return SkillResult(
            success=True,
            output=summary,
            skill_name=self.name,
            sources=[{"title": s.get("title"), "url": s.get("url"), "domain": s.get("domain")} for s in top_sources],
            confidence=0.75 if len(top_sources) >= 3 else 0.5,
            metadata={
                "source_count": len(top_sources),
                "apis_used": ["duckduckgo"] + apis,
            }
        )
