"""WebSearch skill — search the internet for information."""

from typing import Dict, Any, List
from lirox.skills import BaseSkill, SkillResult, RiskLevel


class WebSearchSkill(BaseSkill):
    
    @property
    def name(self) -> str:
        return "web_search"
    
    @property
    def description(self) -> str:
        return "Search the web using DuckDuckGo + paid APIs if available"
    
    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW
    
    @property
    def keywords(self) -> List[str]:
        return [
            "search", "find", "lookup", "google", "what is",
            "who is", "latest", "current", "news", "trending",
            "how to", "where", "when did",
        ]
    
    def execute(self, query: str, context: Dict[str, Any] = None) -> SkillResult:
        from lirox.tools.free_data import get_free_data, duckduckgo_instant
        
        # Try free data APIs first (instant answers)
        free_result = get_free_data(query)
        if free_result.get("status") == "success":
            data = free_result["data"]
            api = free_result["api"]
            
            # Format based on API type
            if api == "wikipedia":
                output = f"{data.get('title', '')}\n\n{data.get('extract', '')}\n\nSource: {data.get('url', '')}"
            elif api == "coingecko":
                output = (
                    f"{data['coin'].title()}: ${data['price']:,.2f} {data['currency']}\n"
                    f"24h Change: {data['change_24h']:.2f}%\n"
                    f"Market Cap: ${data['market_cap']:,.0f}"
                )
            elif api == "wttr.in":
                output = (
                    f"Weather in {data['city']}: {data['condition']}\n"
                    f"Temperature: {data['temp_c']}°C / {data['temp_f']}°F\n"
                    f"Humidity: {data['humidity']}% | Wind: {data['wind_kmph']} km/h"
                )
            elif api == "github":
                lines = []
                for repo in data[:5]:
                    lines.append(f"  {repo['name']} ({repo['stars']} stars) — {repo['description'][:80]}")
                output = "GitHub Results:\n" + "\n".join(lines)
            elif api == "duckduckgo":
                if data.get("answer"):
                    output = data["answer"]
                elif data.get("abstract"):
                    output = f"{data['abstract']}\n\nSource: {data['source']} — {data['url']}"
                else:
                    output = "No instant answer found."
            else:
                output = str(data)
            
            return SkillResult(
                success=True, output=output, skill_name=self.name,
                sources=[{"api": api, "url": data.get("url", "")}],
                confidence=0.85
            )
        
        # Fallback: DuckDuckGo web search via browser tool
        try:
            from lirox.tools.browser import BrowserTool
            bt = BrowserTool()
            results = bt.search_web(query, num_results=5)
            if results:
                lines = []
                for r in results:
                    lines.append(f"  {r['title']} ({r['domain']})\n  {r['snippet']}\n  {r['url']}\n")
                output = f"Search results for '{query}':\n\n" + "\n".join(lines)
                return SkillResult(
                    success=True, output=output, skill_name=self.name,
                    sources=results, confidence=0.7
                )
        except Exception:
            pass
        
        return SkillResult(
            success=False, output="No results found.", skill_name=self.name,
            error="All search methods failed"
        )
