"""
Lirox v0.8.0 — Deep Research Engine

Perplexity-grade autonomous research:
- Multi-source parallel search (Tavily, Serper, Exa, DuckDuckGo fallback)
- Headless browser for dynamic content extraction (v0.8.0)
- Source quality scoring and ranking
- Content extraction and deduplication
- Cross-source LLM synthesis
- Citation tracking with confidence scoring
- Structured report generation (Markdown)
- API tier enforcement (free vs paid keys)
"""

import os
import json
import requests
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from lirox.tools.browser import BrowserTool
from lirox.utils.llm import generate_response
from lirox.config import OUTPUTS_DIR
from lirox.agent.tier import get_available_search_apis


@dataclass
class ResearchSource:
    url: str
    title: str
    domain: str
    content: str
    score: float = 0.0
    snippet: str = ""
    search_query: str = ""
    retrieved_at: str = field(default_factory=lambda: datetime.now().isoformat())
    citation_id: int = 0


@dataclass  
class ResearchReport:
    query: str
    summary: str
    findings: List[Dict]        # [{claim, confidence, citation_ids}]
    sources: List[ResearchSource]
    sub_queries: List[str]
    confidence_overall: float
    generated_at: str
    provider_used: str
    search_apis_used: List[str]
    word_count: int = 0
    report_path: str = ""


class Researcher:
    def __init__(self, browser: BrowserTool, provider: str = "auto", tier_limit: int = 1):
        self.browser = browser
        self.provider = provider
        self.tier_limit = tier_limit # [FIX #7] Injection
        self.search_apis = get_available_search_apis()

        # v0.7: Headless browser for enhanced extraction
        self.headless_browser = None
        try:
            from lirox.tools.browser_tool import HeadlessBrowserTool
            self.headless_browser = HeadlessBrowserTool()
        except ImportError:
            pass

    def research(self, query: str, depth: str = "standard") -> ResearchReport:
        # Determine source counts based on depth
        if depth == "quick":
            target_sources = 3
        elif depth == "deep":
            target_sources = 12
        else: # standard
            target_sources = 6

        # 1. Decompose Query (Expansion 2.0)
        sub_queries = self._decompose_query(query)
        
        # 2. Search All (Categorized)
        raw_sources = self._search_all(sub_queries)
        
        # 3. Deduplicate and Rank (Advanced Ranking)
        best_sources = self._deduplicate_sources(raw_sources)
        best_sources = self._rank_results(best_sources, query)[:target_sources]
        
        # Assign citation IDs
        for i, source in enumerate(best_sources):
            source.citation_id = i + 1

        # 4. Extract Content
        filled_sources = self._extract_all_content(best_sources)
        
        # Filter out sources that failed to extract content
        valid_sources = [s for s in filled_sources if s.content and not s.content.startswith("Error accessing")]
        
        if not valid_sources:
            raise Exception("Failed to extract content from any source.")

        # 5. Synthesize
        synthesis_text, findings = self._synthesize(query, valid_sources, self.provider)
        
        # 6. Calculate Confidence
        confidence = self._calculate_confidence(valid_sources)

        apis_used = self.search_apis if self.search_apis else ["duckduckgo"]

        report = ResearchReport(
            query=query,
            summary=synthesis_text,
            findings=findings,
            sources=valid_sources,
            sub_queries=sub_queries,
            confidence_overall=confidence,
            generated_at=datetime.now().isoformat(),
            provider_used=self.provider,
            search_apis_used=apis_used,
            word_count=len(synthesis_text.split())
        )
        return report

    def _decompose_query(self, query: str) -> Dict[str, List[str]]:
        """
        v0.8 Phase 2: Multi-Query Expansion 2.0.
        Decomposes query into categorized sub-queries (Background, Real-time, Technical, etc.)
        """
        prompt = f"""Deconstruct this research query into 3-5 specialized sub-queries categorized by intent.
        Categories: "background", "real_time", "technical", "opinion"
        Query: {query}
        
        Return ONLY valid JSON with this schema:
        {{
          "sub_queries": [
            {{"category": "background", "query": "..."}},
            {{"category": "real_time", "query": "..."}}
          ]
        }}
        """
        response = generate_response(prompt, self.provider)
        try:
            if "```json" in response:
                json_str = response.split("```json")[-1].split("```")[0].strip()
            else:
                json_str = response.strip()
            
            data = json.loads(json_str)
            return data.get("sub_queries", [{"category": "background", "query": query}])
        except Exception:
            return [{"category": "background", "query": query}]

    def _is_realtime_data_query(self, query: str) -> bool:
        """Detect if the query requires live/real-time verification."""
        realtime_keywords = [
            "current", "price", "live", "score", "today", "now", "latest",
            "stock", "market", "breaking", "update", "value"
        ]
        return any(kw in query.lower() for kw in realtime_keywords)

    def _search_all(self, sub_queries: List[Dict]) -> List[ResearchSource]:
        """v0.8 Phase 2: Categorized parallel search."""
        if self.tier_limit < 1:
            self.search_apis = []

        all_sources = []
        with ThreadPoolExecutor(max_workers=len(sub_queries) * 2) as executor:
            futures = []
            for item in sub_queries:
                q_text = item.get("query", "")
                q_category = item.get("category", "background")
                
                # Intelligent routing: use advanced search for real-time/technical
                depth = "advanced" if q_category in ["real_time", "technical"] else "basic"
                
                if "tavily" in self.search_apis:
                    futures.append(executor.submit(self._search_tavily, q_text, depth=depth))
                if "serper" in self.search_apis:
                    futures.append(executor.submit(self._search_serper, q_text))
                if "exa" in self.search_apis:
                    futures.append(executor.submit(self._search_exa, q_text))
                
                if not self.search_apis:
                    futures.append(executor.submit(self._search_duckduckgo, q_text))

            for future in as_completed(futures):
                try:
                    all_sources.extend(future.result())
                except Exception as e:
                    print(f"Search API error: {e}")

        return all_sources

    def _search_duckduckgo(self, query: str) -> List[ResearchSource]:
        results = self.browser.search_web(query, num_results=5)
        sources = []
        for r in results:
            sources.append(ResearchSource(
                url=r.get("url", ""),
                title=r.get("title", ""),
                domain=r.get("domain", ""),
                content="",
                score=r.get("score", 0.0),
                snippet=r.get("snippet", ""),
                search_query=query
            ))
        return sources

    def _search_tavily(self, query: str, depth: str = "advanced") -> List[ResearchSource]:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key: return []
        try:
            response = requests.post(
                "https://api.tavily.com/search",
                json={"api_key": api_key, "query": query, "search_depth": depth, "max_results": 5},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            sources = []
            for item in data.get("results", []):
                domain = urlparse(item.get("url", "")).netloc.replace("www.", "")
                sources.append(ResearchSource(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    domain=domain,
                    content=item.get("content", ""), # Tavily brings content
                    score=self.browser.score_source(item.get("url", "")),
                    snippet=item.get("content", "")[:200],
                    search_query=query
                ))
            return sources
        except Exception:
            return []

    def _search_serper(self, query: str) -> List[ResearchSource]:
        api_key = os.getenv("SERPER_API_KEY")
        if not api_key: return []
        try:
            response = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": query, "num": 10},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            sources = []
            for item in data.get("organic", []):
                domain = urlparse(item.get("link", "")).netloc.replace("www.", "")
                sources.append(ResearchSource(
                    url=item.get("link", ""),
                    title=item.get("title", ""),
                    domain=domain,
                    content="",
                    score=self.browser.score_source(item.get("link", "")),
                    snippet=item.get("snippet", ""),
                    search_query=query
                ))
            return sources
        except Exception:
            return []

    def _search_exa(self, query: str) -> List[ResearchSource]:
        api_key = os.getenv("EXA_API_KEY")
        if not api_key: return []
        try:
            response = requests.post(
                "https://api.exa.ai/search",
                headers={"x-api-key": api_key, "Content-Type": "application/json"},
                json={"query": query, "numResults": 5, "useAutoprompt": True},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            sources = []
            for item in data.get("results", []):
                domain = urlparse(item.get("url", "")).netloc.replace("www.", "")
                sources.append(ResearchSource(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    domain=domain,
                    content="",
                    score=self.browser.score_source(item.get("url", "")),
                    snippet="",
                    search_query=query
                ))
            return sources
        except Exception:
            return []

    def _deduplicate_sources(self, sources: List[ResearchSource]) -> List[ResearchSource]:
        deduped = {}
        for source in sources:
            if not source.url: continue
            
            # Simple URL dedup
            clean_url = source.url.split("#")[0]
            if clean_url in deduped:
                # Keep the one with better score
                if source.score > deduped[clean_url].score:
                    deduped[clean_url] = source
            else:
                deduped[clean_url] = source

        # Optional: Further limit to best page per domain if generating too many from same site
        domain_best = {}
        for url, source in deduped.items():
            domain = source.domain
            if domain not in domain_best or source.score > domain_best[domain].score:
                domain_best[domain] = source

        return list(domain_best.values())

    def _rank_results(self, sources: List[ResearchSource], query: str) -> List[ResearchSource]:
        """
        v0.8 Phase 2: Advanced Result Ranking.
        Scores based on Domain Authority, Recency (if applicable), and Relevance.
        """
        HIGH_TRUST = {
            "wikipedia.org", "github.com", "arxiv.org", "reuters.com", "bloomberg.com",
            "nytimes.com", "theguardian.com", "wsj.com", "gov", "edu", "stackoverflow.com"
        }
        LOW_TRUST = {"quora.com", "medium.com", "reddit.com", "pinterest.com", "youtube.com"}

        is_realtime = self._is_realtime_data_query(query)
        
        for s in sources:
            base_score = s.score or 0.5
            
            # 1. Domain Trust
            if any(t in s.domain for t in HIGH_TRUST):
                base_score += 0.25
            elif any(t in s.domain for t in LOW_TRUST):
                base_score -= 0.15
            
            # 2. Relevancy Boost (Snippet keywords)
            keywords = [k for k in query.lower().split() if len(k) > 3]
            overlap = sum(1 for k in keywords if k in s.title.lower() or k in s.snippet.lower())
            base_score += (overlap / max(1, len(keywords))) * 0.2
            
            # 3. Recency Boost
            if is_realtime and ("2026" in s.snippet or "today" in s.snippet.lower()):
                base_score += 0.2
                
            s.score = min(1.0, max(0.0, base_score))
            
        return sorted(sources, key=lambda x: x.score, reverse=True)

    def _extract_all_content(self, sources: List[ResearchSource], max_workers: int = 4) -> List[ResearchSource]:
        def extract(src: ResearchSource) -> ResearchSource:
            needs_live_data = self._is_realtime_data_query(src.search_query)
            if src.content and len(src.content) > 500 and not needs_live_data:
                return src # Already extracted (e.g. by Tavily)

            # v0.7: Try headless browser first for richer or live content
            if self.headless_browser and self.headless_browser._browser_available:
                try:
                    result = self.headless_browser.fetch_page(src.url, extract="markdown", timeout=15)
                    if result.get("status") == "success":
                        content = result.get("data", {}).get("markdown", "")
                        if content and len(content) > 100:
                            src.content = content[:5000]
                            return src
                except Exception:
                    pass  # Fall through to requests-based extraction

            # Fallback: requests-based extraction
            try:
                src.content = self.browser.summarize_page(src.url)
            except Exception as e:
                src.content = f"Error accessing {src.url}: {str(e)}"
            return src

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            return list(executor.map(extract, sources))

    def research_with_browser(self, url: str) -> ResearchSource:
        """
        v0.7: Research a specific URL using headless browser for live data.
        Used for verifying real-time claims (stock prices, live scores, etc).
        """
        from urllib.parse import urlparse as _urlparse
        domain = _urlparse(url).netloc.replace("www.", "")

        if self.headless_browser and self.headless_browser._browser_available:
            result = self.headless_browser.fetch_page(url, extract="all", timeout=20)
            if result.get("status") == "success":
                data = result.get("data", {})
                content = data.get("markdown", "")
                return ResearchSource(
                    url=url,
                    title=result.get("metadata", {}).get("title", ""),
                    domain=domain,
                    content=content[:5000],
                    score=0.9,  # High score for direct browser fetch
                    snippet=content[:200],
                    search_query="[direct browser extraction]"
                )

        # Fallback
        content = self.browser.summarize_page(url)
        return ResearchSource(
            url=url,
            title="",
            domain=domain,
            content=content,
            score=0.7,
            snippet=content[:200],
            search_query="[direct fetch]"
        )

    def _synthesize(self, query: str, sources: List[ResearchSource], provider: str) -> Tuple[str, List[Dict]]:
        system_prompt = """You are a research synthesis engine. Your job is to synthesize 
factual information from multiple sources into a coherent, cited report.
RULES:
- Every factual claim MUST include a citation [1], [2] etc referencing the source number
- Rate confidence of each claim: high/medium/low based on source agreement
- If sources conflict, note the disagreement explicitly
- Never fabricate information. If uncertain, say so.
- Format as structured Markdown with sections
- At the very end, provide a JSON block of key findings.

Example JSON:
```json
{
  "findings": [
    {"claim": "The sky is blue", "confidence": "high", "citation_ids": [1, 2]}
  ]
}
```
"""
        
        user_prompt = f"Query: {query}\n\nSources:\n\n"
        for s in sources:
            user_prompt += f"--- SOURCE [{s.citation_id}] ({s.domain}) ---\n"
            content_snippet = s.content[:3000] if len(s.content) > 3000 else s.content
            user_prompt += f"Title: {s.title}\n{content_snippet}\n\n"

        response = generate_response(user_prompt, provider, system_prompt=system_prompt)
        
        # Extract findings JSON
        findings = []
        synthesis_text = response
        
        import re
        try:
            if "```json" in response:
                json_part = response.split("```json")[-1].split("```")[0]
                data = json.loads(json_part.strip())
                findings = data.get("findings", [])
                # Use regex to robustly strip the JSON block from the generated report
                synthesis_text = re.sub(r"```json.*?```", "", response, flags=re.DOTALL).strip()
                # Also strip any trailing text introducing the JSON block
                synthesis_text = re.sub(r"(?i)\s*JSON Block of Key Findings:?\s*$", "", synthesis_text).strip()
        except Exception:
            pass

        return synthesis_text, findings

    def _calculate_confidence(self, sources: List[ResearchSource]) -> float:
        if not sources: return 0.0
        avg_score = sum(s.score for s in sources) / len(sources)
        # Bonus for having more sources
        volume_bonus = min(0.2, len(sources) * 0.02)
        confidence = avg_score + volume_bonus
        return max(0.0, min(1.0, confidence))

    def generate_report(self, report: ResearchReport) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = "".join(c if c.isalnum() else "_" for c in report.query[:20]).strip("_")
        filename = f"research_{slug}_{timestamp}.md"
        filepath = os.path.join(OUTPUTS_DIR, filename)

        md = f"# Research Report: {report.query}\n\n"
        md += f"**Date:** {report.generated_at}\n"
        md += f"**Confidence:** {int(report.confidence_overall * 100)}%\n"
        md += f"**Sources Analyzed:** {len(report.sources)}\n"
        md += f"**APIs Used:** {', '.join(report.search_apis_used)}\n\n"
        
        md += "---\n\n## Abstract & Synthesis\n\n"
        md += report.summary + "\n\n"

        if report.findings:
            md += "## Key Findings\n\n"
            for f in report.findings:
                md += f"- **[{f.get('confidence', 'medium').upper()}]** {f.get('claim', '')} "
                if f.get('citation_ids'):
                    md += f"(Sources: {', '.join(str(i) for i in f.get('citation_ids', []))})\n"
            md += "\n"

        md += "## Sources Table\n\n"
        md += "| ID | Title | Domain | Quality | URL |\n"
        md += "|---|---|---|---|---|\n"
        for s in report.sources:
            quality = f"{int(s.score * 100)}%"
            md += f"| [{s.citation_id}] | {s.title} | {s.domain} | {quality} | {s.url} |\n"

        with open(filepath, "w") as f:
            f.write(md)

        return filepath
