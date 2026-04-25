"""
DuckDuckGo web search implementation.
Free, no API key required.
"""
import logging
from typing import List, Dict, Optional

_logger = logging.getLogger("lirox.tools.search")


def search(query: str, max_results: int = 10, region: str = "wt-wt") -> List[Dict]:
    """
    Search the web using DuckDuckGo.
    
    Args:
        query: Search query string
        max_results: Number of results to return (default 10, max 30)
        region: Region code (wt-wt = worldwide, in-en = India, us-en = USA)
    
    Returns:
        List of dicts with: title, snippet, url, source
    """
    try:
        from ddgs import DDGS  # UPDATED IMPORT
        
        results = []
        
        with DDGS() as ddgs:
            search_results = ddgs.text(
                query,
                region=region,
                max_results=min(max_results, 30)
            )
            
            if not search_results:
                _logger.warning(f"No results for query: {query}")
                return []
            
            for r in search_results:
                results.append({
                    'title': r.get('title', ''),
                    'snippet': r.get('body', ''),
                    'url': r.get('href', ''),
                    'source': r.get('href', '').split('/')[2] if r.get('href') else ''
                })
        
        _logger.info(f"Search '{query}' returned {len(results)} results")
        return results
    
    except ImportError:
        _logger.error("ddgs not installed. Run: pip install ddgs")
        raise RuntimeError(
            "Web search unavailable. Install with: pip install ddgs"
        )
    
    except Exception as e:
        _logger.error(f"Search error: {e}")
        return []


def search_news(query: str, max_results: int = 10) -> List[Dict]:
    """Search news articles using DuckDuckGo."""
    try:
        from ddgs import DDGS  # UPDATED IMPORT
        
        results = []
        
        with DDGS() as ddgs:
            news_results = ddgs.news(
                query,
                max_results=min(max_results, 30)
            )
            
            for r in news_results:
                results.append({
                    'title': r.get('title', ''),
                    'snippet': r.get('body', ''),
                    'url': r.get('url', ''),
                    'source': r.get('source', ''),
                    'date': r.get('date', '')
                })
        
        return results
    
    except Exception as e:
        _logger.error(f"News search error: {e}")
        return []


def search_images(query: str, max_results: int = 10) -> List[Dict]:
    """Search images using DuckDuckGo."""
    try:
        from ddgs import DDGS  # UPDATED IMPORT
        
        results = []
        
        with DDGS() as ddgs:
            image_results = ddgs.images(
                query,
                max_results=min(max_results, 30)
            )
            
            for r in image_results:
                results.append({
                    'title': r.get('title', ''),
                    'url': r.get('image', ''),
                    'thumbnail': r.get('thumbnail', ''),
                    'source': r.get('url', '')
                })
        
        return results
    
    except Exception as e:
        _logger.error(f"Image search error: {e}")
        return []
