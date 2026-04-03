"""WebFetch skill — fetch and extract content from a URL."""

from typing import Dict, Any, List
from lirox.skills import BaseSkill, SkillResult, RiskLevel


class WebFetchSkill(BaseSkill):
    
    @property
    def name(self) -> str:
        return "web_fetch"
    
    @property
    def description(self) -> str:
        return "Fetch and extract content from any URL"
    
    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW
    
    @property
    def keywords(self) -> List[str]:
        return [
            "fetch", "scrape", "extract", "url", "http", "https",
            "website", "page", "open url", "get page", "browse",
        ]
    
    def can_handle(self, query: str) -> tuple:
        """Override: also match if query contains a URL."""
        import re
        has_url = bool(re.search(r'https?://\S+', query))
        base_can, base_score = super().can_handle(query)
        if has_url:
            return True, max(base_score, 0.9)
        return base_can, base_score
    
    def execute(self, query: str, context: Dict[str, Any] = None) -> SkillResult:
        import re
        
        # Extract URL from query
        url_match = re.search(r'https?://\S+', query)
        if not url_match:
            return SkillResult(
                success=False, output="No URL found in query.",
                skill_name=self.name, error="No URL"
            )
        
        url = url_match.group(0).rstrip(".,;)")
        
        # Try headless browser first, then fallback to requests
        try:
            from lirox.tools.browser_tool import HeadlessBrowserTool
            hb = HeadlessBrowserTool()
            if hb._browser_available:
                result = hb.fetch_page(url, extract="markdown", timeout=20)
                if result.get("status") == "success":
                    content = result.get("data", {}).get("markdown", "")
                    title = result.get("metadata", {}).get("title", "")
                    return SkillResult(
                        success=True,
                        output=f"{title}\n\n{content[:5000]}",
                        skill_name=self.name,
                        metadata={"url": url, "method": "headless", "chars": len(content)}
                    )
        except Exception:
            pass
        
        # Fallback: requests + BeautifulSoup
        try:
            from lirox.tools.browser import BrowserTool
            bt = BrowserTool()
            content = bt.summarize_page(url)
            return SkillResult(
                success=True,
                output=f"Content from {url}:\n\n{content[:5000]}",
                skill_name=self.name,
                metadata={"url": url, "method": "requests", "chars": len(content)}
            )
        except Exception as e:
            return SkillResult(
                success=False, output="", skill_name=self.name,
                error=f"Fetch failed: {str(e)}"
            )
