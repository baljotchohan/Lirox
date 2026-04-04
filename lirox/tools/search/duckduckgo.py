"""DuckDuckGo Search — free, no API key required."""


def search_ddg(query: str, max_results: int = 8) -> str:
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return f"No results for: {query}"
        return "\n\n".join(
            f"{i}. {r.get('title', '')}\n   {r.get('body', '')[:200]}\n   {r.get('href', '')}"
            for i, r in enumerate(results, 1)
        )
    except ImportError:
        return "duckduckgo-search not installed. Run: pip install duckduckgo-search"
    except Exception as e:
        return f"Search error: {e}"
