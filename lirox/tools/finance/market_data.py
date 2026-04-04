"""Market Data — yfinance (free) prices, news, metrics."""
import json
import re


def get_market_data(query: str) -> str:
    ticker = _extract_ticker(query)
    if not ticker:
        try:
            from lirox.tools.search.duckduckgo import search_ddg
            return search_ddg(f"stock market {query}")
        except Exception as e:
            return f"Error: {e}"
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).info
        return json.dumps(
            {
                "ticker": ticker,
                "name": info.get("longName", ticker),
                "price": info.get("currentPrice") or info.get("regularMarketPrice"),
                "change_pct": info.get("regularMarketChangePercent"),
                "market_cap": _fmt(info.get("marketCap")),
                "pe": info.get("trailingPE"),
                "fwd_pe": info.get("forwardPE"),
                "div_yield": info.get("dividendYield"),
                "52w_high": info.get("fiftyTwoWeekHigh"),
                "52w_low": info.get("fiftyTwoWeekLow"),
                "volume": _fmt(info.get("volume")),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
            },
            indent=2,
            default=str,
        )
    except ImportError:
        return "yfinance not installed. Run: pip install yfinance"
    except Exception as e:
        return f"Error for {ticker}: {e}"


def _extract_ticker(q: str) -> str:
    # Check name map first (higher priority)
    q_lower = q.lower()
    names = {
        "apple": "AAPL", "microsoft": "MSFT", "google": "GOOGL",
        "amazon": "AMZN", "meta": "META", "tesla": "TSLA",
        "nvidia": "NVDA", "bitcoin": "BTC-USD", "ethereum": "ETH-USD",
    }
    for n, t in names.items():
        if n in q_lower:
            return t

    # Only match explicit tickers (preceded by $ or standalone uppercase)
    m = re.search(r'\$([A-Z]{1,5})\b', q)
    if m:
        return m.group(1)

    # Match standalone tickers only if they look like tickers (not common words)
    common_words = {"I", "A", "AM", "IS", "IT", "IN", "ON", "AT", "TO", "OF",
                    "DO", "IF", "OR", "SO", "UP", "BY", "AN", "AS", "NO", "BE",
                    "US", "WE", "MY", "HE", "ME", "GDP", "USA", "UK", "CEO", "CTO"}
    m = re.search(r'\b([A-Z]{1,5})\b', q)
    if m and m.group(1) not in common_words:
        return m.group(1)
    return None


def _fmt(n) -> str:
    if n is None:
        return "N/A"
    try:
        n = float(n)
        if n >= 1e12:
            return f"{n/1e12:.1f}T"
        if n >= 1e9:
            return f"{n/1e9:.1f}B"
        if n >= 1e6:
            return f"{n/1e6:.1f}M"
        return str(n)
    except Exception:
        return str(n)
