"""
Lirox v0.8.5 — Free Public Data APIs (Phase 5)

Keyless, rate-limit-friendly access to real-time data sources:
- DuckDuckGo Instant Answer API
- Wikipedia REST API
- CoinGecko (crypto prices)
- wttr.in (weather)
- GitHub Search
- Yahoo Finance (stocks, indices: Nifty 50, Sensex, S&P 500, etc.)

All functions return clean structured dicts and NEVER crash on failure.
"""

import re
import json
from typing import Optional, Dict, Any

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


# ─── Shared HTTP helper ──────────────────────────────────────────────────────

_SESSION = None

def _get_session():
    global _SESSION
    if _SESSION is None and _HAS_REQUESTS:
        import requests as rq
        _SESSION = rq.Session()
        _SESSION.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; Lirox-Agent/0.8.5)",
            "Accept": "application/json",
        })
    return _SESSION


def _get(url: str, params: dict = None, timeout: int = 8, extra_headers: dict = None) -> Optional[dict]:
    if not _HAS_REQUESTS:
        return None
    try:
        sess = _get_session()
        hdrs = extra_headers or {}
        r = sess.get(url, params=params, timeout=timeout, headers=hdrs)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _get_text(url: str, params: dict = None, timeout: int = 8) -> Optional[str]:
    if not _HAS_REQUESTS:
        return None
    try:
        sess = _get_session()
        r = sess.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception:
        return None


# ─── Yahoo Finance (Stocks & Indices — no key needed) ────────────────────────

_TICKER_MAP = {
    "nifty":      "^NSEI",
    "nifty 50":   "^NSEI",
    "nifty50":    "^NSEI",
    "sensex":     "^BSESN",
    "bse sensex": "^BSESN",
    "bank nifty": "^NSEBANK",
    "nifty bank": "^NSEBANK",
    "s&p 500":    "^GSPC",
    "sp500":      "^GSPC",
    "dow jones":  "^DJI",
    "nasdaq":     "^IXIC",
    "apple":      "AAPL",
    "microsoft":  "MSFT",
    "google":     "GOOGL",
    "tesla":      "TSLA",
    "amazon":     "AMZN",
    "meta":       "META",
    "nvidia":     "NVDA",
    "reliance":   "RELIANCE.NS",
    "tcs":        "TCS.NS",
    "infosys":    "INFY.NS",
}

def yahoo_finance_price(symbol_or_name: str) -> Dict[str, Any]:
    """Fetch real-time stock/index price from Yahoo Finance (no API key)."""
    query_lower = symbol_or_name.lower().strip()
    ticker = _TICKER_MAP.get(query_lower) or symbol_or_name.upper().strip()
    is_indian = "NS" in ticker or "NSEI" in ticker or "BSESN" in ticker or "NSEBANK" in ticker

    # Try v8 chart API first
    data = _get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
        params={"interval": "1m", "range": "1d"},
    )

    if not data or "chart" not in data or not data["chart"].get("result"):
        # Fallback: v7 quote API
        data_v7 = _get(
            "https://query1.finance.yahoo.com/v7/finance/quote",
            params={"symbols": ticker},
        )
        if data_v7:
            try:
                quote = data_v7["quoteResponse"]["result"][0]
                price = quote.get("regularMarketPrice", 0)
                change = quote.get("regularMarketChange", 0)
                chg_pct = quote.get("regularMarketChangePercent", 0)
                high = quote.get("regularMarketDayHigh", 0)
                low = quote.get("regularMarketDayLow", 0)
                prev_close = quote.get("regularMarketPreviousClose", 0)
                name = quote.get("longName") or quote.get("shortName") or ticker
                currency = quote.get("currency", "INR" if is_indian else "USD")
                direction = "\u25b2" if change >= 0 else "\u25bc"
                answer = (
                    f"{name} ({ticker}): {price:,.2f} {currency}\n"
                    f"Change: {direction} {abs(change):.2f} ({abs(chg_pct):.2f}%)\n"
                    f"Day range: {low:,.2f} \u2013 {high:,.2f}\n"
                    f"Prev close: {prev_close:,.2f}"
                )
                return {
                    "status": "success", "source": "yahoo_finance",
                    "answer": answer, "price": price,
                    "change": change, "change_pct": chg_pct,
                    "ticker": ticker, "name": name, "currency": currency, "live": True,
                }
            except (KeyError, IndexError, TypeError):
                pass
        return {
            "status": "error", "source": "yahoo_finance",
            "answer": f"Could not fetch live price for {symbol_or_name}. Please try again in a moment.",
        }

    try:
        result = data["chart"]["result"][0]
        meta = result["meta"]
        price = meta.get("regularMarketPrice") or meta.get("currentPrice", 0)
        prev_close = meta.get("previousClose") or meta.get("chartPreviousClose", 0)
        change = price - prev_close if prev_close else 0
        chg_pct = (change / prev_close * 100) if prev_close else 0
        currency = meta.get("currency", "INR" if is_indian else "USD")
        name = meta.get("longName") or meta.get("symbol") or ticker
        direction = "\u25b2" if change >= 0 else "\u25bc"

        indicators = result.get("indicators", {}).get("quote", [{}])[0]
        highs = [h for h in indicators.get("high", []) if h]
        lows = [l for l in indicators.get("low", []) if l]
        day_high = max(highs) if highs else 0
        day_low = min(lows) if lows else 0

        answer = (
            f"{name} ({ticker}): {price:,.2f} {currency}\n"
            f"Change: {direction} {abs(change):.2f} ({abs(chg_pct):.2f}%)"
        )
        if day_high and day_low:
            answer += f"\nDay range: {day_low:,.2f} \u2013 {day_high:,.2f}"
        answer += f"\nPrev close: {prev_close:,.2f}"

        return {
            "status": "success", "source": "yahoo_finance",
            "answer": answer, "price": price,
            "change": change, "change_pct": chg_pct,
            "ticker": ticker, "name": name, "currency": currency, "live": True,
        }
    except (KeyError, IndexError, TypeError):
        return {
            "status": "error", "source": "yahoo_finance",
            "answer": f"Received data but could not parse price for {symbol_or_name}.",
        }


# ─── DuckDuckGo Instant Answer ───────────────────────────────────────────────

def duckduckgo_instant(query: str) -> Dict[str, Any]:
    data = _get(
        "https://api.duckduckgo.com/",
        params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
    )
    if not data:
        return {"status": "error", "source": "duckduckgo", "answer": ""}
    answer = data.get("AbstractText") or data.get("Answer") or data.get("Definition") or ""
    topics = [t["Text"] for t in data.get("RelatedTopics", [])[:5] if isinstance(t, dict) and t.get("Text")]
    return {
        "status": "success" if answer or topics else "empty",
        "source": "duckduckgo", "answer": answer, "related": topics,
        "url": data.get("AbstractURL", ""), "type": data.get("Type", ""),
    }


# ─── Wikipedia REST API ───────────────────────────────────────────────────────

def wikipedia_summary(query: str, lang: str = "en") -> Dict[str, Any]:
    slug = query.replace(" ", "_")
    data = _get(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{slug}")
    if not data or data.get("type") == "https://mediawiki.org/wiki/HyperSwitch/errors/not_found":
        search = _get(
            f"https://{lang}.wikipedia.org/w/api.php",
            params={"action": "query", "list": "search", "srsearch": query,
                    "format": "json", "srlimit": 1},
        )
        if search:
            results = search.get("query", {}).get("search", [])
            if results:
                title = results[0]["title"].replace(" ", "_")
                data = _get(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}")
    if not data:
        return {"status": "error", "source": "wikipedia", "answer": ""}
    extract = data.get("extract", "")
    if not extract:
        return {"status": "empty", "source": "wikipedia", "answer": ""}
    return {
        "status": "success", "source": "wikipedia",
        "answer": extract[:1500],
        "title": data.get("title", query),
        "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
    }


# ─── CoinGecko Crypto Prices ──────────────────────────────────────────────────

_COINGECKO_SLUGS = {
    "bitcoin": "bitcoin", "btc": "bitcoin",
    "ethereum": "ethereum", "eth": "ethereum",
    "solana": "solana", "sol": "solana",
    "dogecoin": "dogecoin", "doge": "dogecoin",
    "cardano": "cardano", "ada": "cardano",
    "xrp": "ripple", "ripple": "ripple",
    "bnb": "binancecoin", "binance": "binancecoin",
    "usdc": "usd-coin", "usdt": "tether",
}


def coingecko_price(coin: str, vs_currency: str = "usd") -> Dict[str, Any]:
    coin_id = _COINGECKO_SLUGS.get(coin.lower().strip(), coin.lower().strip())
    data = _get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={"ids": coin_id, "vs_currencies": vs_currency,
                "include_24hr_change": "true", "include_market_cap": "true"},
    )
    if not data or coin_id not in data:
        return {"status": "error", "source": "coingecko", "answer": f"Could not fetch {coin} price."}
    cd = data[coin_id]
    price = cd.get(vs_currency, 0)
    chg = cd.get(f"{vs_currency}_24h_change", 0)
    mcap = cd.get(f"{vs_currency}_market_cap", 0)
    direction = "\u25b2" if chg >= 0 else "\u25bc"
    answer = (
        f"{coin.upper()} price: ${price:,.2f} {vs_currency.upper()}\n"
        f"24h change: {direction} {abs(chg):.2f}%\n"
        f"Market cap: ${mcap:,.0f}"
    )
    return {
        "status": "success", "source": "coingecko",
        "answer": answer, "price": price, "change_24h": chg,
        "market_cap": mcap, "coin": coin_id, "currency": vs_currency,
    }


# ─── wttr.in Weather ──────────────────────────────────────────────────────────

def wttr_weather(location: str) -> Dict[str, Any]:
    text = _get_text(f"https://wttr.in/{location}", params={"format": "j1"})
    if not text:
        simple = _get_text(f"https://wttr.in/{location}?format=3")
        if simple:
            return {"status": "success", "source": "wttr.in", "answer": simple.strip(), "location": location}
        return {"status": "error", "source": "wttr.in", "answer": ""}
    try:
        data = json.loads(text)
        cur = data["current_condition"][0]
        tc, tf = cur["temp_C"], cur["temp_F"]
        desc = cur["weatherDesc"][0]["value"]
        fc, hum, wind = cur["FeelsLikeC"], cur["humidity"], cur["windspeedKmph"]
        area = data.get("nearest_area", [{}])[0]
        aname = area.get("areaName", [{}])[0].get("value", location)
        country = area.get("country", [{}])[0].get("value", "")
        answer = (
            f"Weather in {aname}, {country}:\n"
            f"{desc} \u2014 {tc}\u00b0C / {tf}\u00b0F\n"
            f"Feels like: {fc}\u00b0C | Humidity: {hum}% | Wind: {wind} km/h"
        )
        return {
            "status": "success", "source": "wttr.in",
            "answer": answer, "temp_c": int(tc), "temp_f": int(tf),
            "description": desc, "location": f"{aname}, {country}",
        }
    except (KeyError, ValueError, json.JSONDecodeError):
        return {"status": "error", "source": "wttr.in", "answer": "Could not parse weather data."}


# ─── GitHub Search ────────────────────────────────────────────────────────────

def github_search(query: str, search_type: str = "repositories") -> Dict[str, Any]:
    data = _get(
        f"https://api.github.com/search/{search_type}",
        params={"q": query, "sort": "stars", "order": "desc", "per_page": 5},
    )
    if not data:
        return {"status": "error", "source": "github", "answer": ""}
    items = data.get("items", [])
    total = data.get("total_count", 0)
    if not items:
        return {"status": "empty", "source": "github", "answer": f"No {search_type} found for: {query}"}
    lines = [f"GitHub '{query}' ({total:,} results):"]
    for r in items[:5]:
        nm = r.get("full_name") or r.get("login") or r.get("path", "")
        stars = r.get("stargazers_count", "")
        desc = r.get("description") or r.get("bio") or ""
        lines.append(f"  \u2022 {nm}" + (f" \u2b50 {stars:,}" if stars else "") + (f" \u2014 {desc[:60]}" if desc else ""))
    return {"status": "success", "source": "github", "answer": "\n".join(lines), "results": items[:5], "total": total}


# ─── Local System Query Detector ─────────────────────────────────────────────

_LOCAL_PATTERN = re.compile(
    r"\b(how many files|count files|list files|files in|files on|"
    r"disk space|storage used|my desktop|my downloads|my documents|"
    r"running processes|cpu usage|memory usage|ram usage|"
    r"how many.*folder|what.*folder)\b",
    re.IGNORECASE,
)

def is_local_system_query(query: str) -> bool:
    """True if query is about local FS/system — should use terminal, NOT web search."""
    return bool(_LOCAL_PATTERN.search(query))


# ─── Smart Dispatcher ────────────────────────────────────────────────────────

_STOCK_PATTERN = re.compile(
    r"\b(nifty|sensex|nifty\s*50|bank\s*nifty|s&p\s*500|dow\s*jones|nasdaq|"
    r"stock\s+price|share\s+price|index\s+level|market\s+index|"
    r"reliance|tcs|infosys|apple|microsoft|tesla|nvidia|google|amazon|meta)\b",
    re.IGNORECASE,
)
_CRYPTO_PATTERN = re.compile(
    r"\b(bitcoin|btc|ethereum|eth|solana|sol|dogecoin|doge|cardano|ada|xrp|ripple|bnb|usdc|usdt)\b",
    re.IGNORECASE,
)
_WEATHER_PATTERN = re.compile(
    r"\b(weather|temperature|forecast|rain|sunny|cloudy|humidity|wind)\b",
    re.IGNORECASE,
)
_GITHUB_PATTERN = re.compile(
    r"\b(github|repo|repository|repositories|open.?source|starred)\b",
    re.IGNORECASE,
)
_PRICE_TRIGGERS = {
    "price", "cost", "worth", "value", "how much", "usd", "$", "inr",
    "rate", "trading at", "level", "index", "nifty", "sensex", "market",
}


def get_free_data(query: str) -> Dict[str, Any]:
    """
    Smart dispatcher.
    Priority:
    0. Local system query  → {status: local}  (caller handles via terminal)
    1. Stock/index price   → Yahoo Finance     (REAL live data)
    2. Crypto price        → CoinGecko
    3. Weather             → wttr.in
    4. GitHub              → GitHub Search
    5. General             → DuckDuckGo → Wikipedia
    """
    q_lower = query.lower()

    # 0. Local system (file counts, disk, processes)
    if is_local_system_query(query):
        return {"status": "local", "source": "system", "answer": None}

    # 1. Stock / Index
    m = _STOCK_PATTERN.search(q_lower)
    if m and any(kw in q_lower for kw in _PRICE_TRIGGERS):
        result = yahoo_finance_price(m.group(0))
        if result["status"] == "success":
            return result

    # 2. Crypto
    m = _CRYPTO_PATTERN.search(q_lower)
    if m and any(kw in q_lower for kw in _PRICE_TRIGGERS):
        result = coingecko_price(m.group(0))
        if result["status"] == "success":
            return result

    # 3. Weather
    if _WEATHER_PATTERN.search(q_lower):
        stop = {"weather","temperature","forecast","in","at","for","the","what",
                "is","how","today","now","current","currently"}
        words = [w for w in query.split() if w.lower() not in stop]
        location = " ".join(words[:3]) if words else "London"
        result = wttr_weather(location)
        if result["status"] == "success":
            return result

    # 4. GitHub
    if _GITHUB_PATTERN.search(q_lower):
        result = github_search(query)
        if result["status"] == "success":
            return result

    # 5. DuckDuckGo instant
    ddg = duckduckgo_instant(query)
    if ddg.get("answer") or ddg.get("related"):
        return ddg

    # 6. Wikipedia
    wiki = wikipedia_summary(query)
    if wiki.get("status") == "success":
        return wiki

    return {"status": "empty", "source": "free_apis", "answer": ""}
