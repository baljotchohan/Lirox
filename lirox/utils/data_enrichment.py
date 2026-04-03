"""
Lirox v0.8 — Data Enrichment Layer

Enriches research results with browser-fetched full content:
- Completes incomplete snippets
- Validates information across sources
- Handles time-sensitive data verification
- Merges duplicates intelligently
"""

import json
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from dataclasses import dataclass
from lirox.utils.llm import generate_response


@dataclass
class EnrichedSource:
    """Research source enhanced with browser-fetched content."""
    original_url: str
    title: str
    domain: str
    snippet: str  # Original research snippet
    full_content: Optional[str] = None  # Browser-fetched content
    is_enriched: bool = False
    fetch_method: str = "research"  # "research" or "browser"
    enrichment_confidence: float = 1.0
    timestamp: str = None
    verification_status: str = "unverified"  # unverified, verified, conflicting
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "url": self.original_url,
            "title": self.title,
            "domain": self.domain,
            "snippet": self.snippet,
            "full_content": self.full_content[:500] + "..." if self.full_content and len(self.full_content) > 500 else self.full_content,
            "is_enriched": self.is_enriched,
            "fetch_method": self.fetch_method,
            "confidence": self.enrichment_confidence,
            "verification": self.verification_status,
        }


class DataEnrichmentEngine:
    """
    Enriches research results with browser content.
    Smart logic to decide when browser fetching is needed.
    """
    
    # Snippet length thresholds
    MIN_SNIPPET_LENGTH = 100
    MIN_CONTENT_LENGTH = 300
    
    # Topics that need live verification
    REAL_TIME_TOPICS = [
        "price", "stock", "crypto", "bitcoin", "weather", "news",
        "score", "game", "ranking", "live", "current", "today"
    ]
    
    # Domains that require full content verification
    VERIFICATION_DOMAINS = [
        "github.com", "stackoverflow.com", "wikipedia.org",
        "coinmarketcap.com", "yahoo.com", "google.com",
        "bbc.com", "cnn.com", "reuters.com"
    ]
    
    def __init__(self, browser_tool=None, verbose: bool = False):
        self.browser_tool = browser_tool
        self.verbose = verbose
        self.enrichment_cache = {}
    
    def enrich_sources(self, sources: List[Dict], 
                      query: str, 
                      verify_real_time: bool = True) -> List[EnrichedSource]:
        """
        Enrich research sources with browser content where needed.
        
        Args:
            sources: List of research sources (dicts with url, title, snippet, etc.)
            query: Original query (to detect real-time topics)
            verify_real_time: Whether to verify real-time data
        
        Returns:
            List of EnrichedSource objects
        """
        enriched = []
        
        for source in sources:
            enriched_source = self._enrich_single_source(
                source,
                query,
                verify_real_time=verify_real_time
            )
            enriched.append(enriched_source)
        
        # Deduplicate and validate
        enriched = self._deduplicate_enriched(enriched)
        enriched = self._validate_consistency(enriched)
        
        return enriched
    
    def _enrich_single_source(self, source: Dict, query: str,
                             verify_real_time: bool = True) -> EnrichedSource:
        """Enrich a single source."""
        
        url = source.get("url", "")
        snippet = source.get("snippet", "") or source.get("content", "")
        
        # Initialize enriched source
        enriched = EnrichedSource(
            original_url=url,
            title=source.get("title", ""),
            domain=source.get("domain", ""),
            snippet=snippet,
            fetch_method="research",
        )
        
        # Decision: Should we fetch full content?
        should_enrich = self._should_enrich(
            enriched, query, verify_real_time
        )
        
        if should_enrich and self.browser_tool:
            # Fetch full content via browser
            full_content = self._fetch_full_content(url)
            if full_content:
                enriched.full_content = full_content
                enriched.is_enriched = True
                enriched.fetch_method = "browser"
                enriched.verification_status = "verified"
        
        return enriched
    
    def _should_enrich(self, source: EnrichedSource, 
                      query: str, verify_real_time: bool) -> bool:
        """Decide if source needs browser enrichment."""
        
        # Rule 1: Snippet is too short
        if len(source.snippet) < self.MIN_SNIPPET_LENGTH:
            if self.verbose:
                print(f"[ENRICH] {source.domain}: Snippet too short ({len(source.snippet)} chars)")
            return True
        
        # Rule 2: Real-time topic detected
        if verify_real_time:
            is_real_time = any(
                topic in query.lower() for topic in self.REAL_TIME_TOPICS
            )
            if is_real_time:
                if self.verbose:
                    print(f"[ENRICH] {source.domain}: Real-time topic detected, fetching live content")
                return True
        
        # Rule 3: Domain requires verification
        if any(domain in source.domain for domain in self.VERIFICATION_DOMAINS):
            if self.verbose:
                print(f"[ENRICH] {source.domain}: Verification domain, fetching full content")
            return True
        
        # Rule 4: Dynamic content indicators (SPA, AJAX)
        if any(indicator in source.snippet for indicator in ["JavaScript", "loading...", "..."]):
            if self.verbose:
                print(f"[ENRICH] {source.domain}: Dynamic content detected, using headless browser")
            return True
        
        return False
    
    def _fetch_full_content(self, url: str) -> Optional[str]:
        """Fetch full content from URL using browser."""
        if not self.browser_tool:
            return None
        
        try:
            result = self.browser_tool.fetch_page(
                url, extract="markdown", timeout=15
            )
            
            if result.get("status") == "success":
                content = result.get("data", {}).get("markdown", "")
                return content[:5000] if content else None
            
            return None
        except Exception as e:
            if self.verbose:
                print(f"[ENRICH ERROR] Failed to fetch {url}: {e}")
            return None
    
    def _deduplicate_enriched(self, sources: List[EnrichedSource]) -> List[EnrichedSource]:
        """Remove duplicate sources (same URL or very similar content)."""
        unique = {}
        
        for source in sources:
            # Use URL as unique key
            if source.original_url not in unique:
                unique[source.original_url] = source
            else:
                # Keep the more enriched version
                existing = unique[source.original_url]
                if source.is_enriched and not existing.is_enriched:
                    unique[source.original_url] = source
        
        return list(unique.values())
    
    def _validate_consistency(self, sources: List[EnrichedSource]) -> List[EnrichedSource]:
        """Validate consistency across sources."""
        
        for source in sources:
            if not source.is_enriched or not source.full_content:
                continue
            
            # Check for content consistency between snippet and full content
            snippet_words = set(source.snippet.lower().split())
            content_words = set(source.full_content.lower().split()[:50])
            
            overlap = len(snippet_words & content_words) / max(len(snippet_words), 1)
            
            if overlap > 0.5:
                source.enrichment_confidence = 0.95
                source.verification_status = "verified"
            else:
                source.enrichment_confidence = 0.7
                source.verification_status = "conflicting"
                if self.verbose:
                    print(f"[WARNING] {source.domain}: Content mismatch detected (overlap: {overlap:.0%})")
        
        return sources
    
    def merge_enriched_results(self, 
                              enriched_sources: List[EnrichedSource],
                              synthesis_prompt: str = None) -> Dict:
        """
        Merge enriched sources into final response.
        
        Returns:
            {
                "merged_content": str,
                "sources": [...],
                "verification_status": "verified|partial|unverified",
                "enrichment_summary": {...}
            }
        """
        
        # Build merged content
        parts = []
        for i, source in enumerate(enriched_sources, 1):
            content = source.full_content or source.snippet
            parts.append(f"\n--- SOURCE [{i}] {source.domain} ---\n{content}\n")
        
        merged_text = "\n".join(parts)
        
        # Verification status
        verification_statuses = [s.verification_status for s in enriched_sources]
        if all(v == "verified" for v in verification_statuses):
            verification_status = "verified"
        elif all(v in ["verified", "conflicting"] for v in verification_statuses):
            verification_status = "partial"
        else:
            verification_status = "unverified"
        
        return {
            "merged_content": merged_text,
            "sources": [s.to_dict() for s in enriched_sources],
            "verification_status": verification_status,
            "enrichment_summary": {
                "total_sources": len(enriched_sources),
                "enriched_sources": sum(1 for s in enriched_sources if s.is_enriched),
                "verification_rate": sum(1 for s in enriched_sources if s.verification_status == "verified") / len(enriched_sources) if enriched_sources else 0,
                "average_confidence": sum(s.enrichment_confidence for s in enriched_sources) / len(enriched_sources) if enriched_sources else 0,
            }
        }
