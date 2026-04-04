"""
Lirox v2.0 — Real-Time Data Extraction

Specialized extractors for structured financial and live data from web pages.
Used by BrowserTool and HeadlessBrowser to parse prices, percentages,
market caps, and timestamps from page content.
"""

import re
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger("lirox.tools.realtime_data")


class RealTimeDataExtractor:
    """
    Extracts structured financial and real-time data from text content.

    Usage:
        extractor = RealTimeDataExtractor()
        stock = extractor.extract_stock_data(page_text, "AAPL")
        crypto = extractor.extract_crypto_data(page_text, "Bitcoin")
    """

    # Currency patterns
    CURRENCY_PATTERNS = [
        r'(?:[\$\u20b9\u20ac\u00a3]|USD|INR|EUR|GBP)\s?\d{1,3}(?:,\d{3})*(?:\.\d+)?',
        r'\d{1,3}(?:,\d{3})*(?:\.\d+)?\s?(?:[\$\u20b9\u20ac\u00a3]|USD|INR|EUR|GBP)',
    ]

    # Percentage/point change patterns
    CHANGE_PATTERNS = [
        r'[+-]?\s?\d{1,3}(?:,\d{3})*(?:\.\d+)?\s?%',
        r'[+-]?\s?\d{1,3}(?:,\d{3})*(?:\.\d+)?\s?(?:points|pts)',
    ]

    # Market cap patterns
    MARKET_CAP_PATTERNS = [
        r'(?:market\s*cap|mkt\s*cap|mcap)\s*:?\s*[\$\u20b9]?\s*\d+(?:\.\d+)?\s*(?:T|B|M|trillion|billion|million)',
    ]

    # Volume patterns
    VOLUME_PATTERNS = [
        r'(?:volume|vol)\s*:?\s*\d+(?:\.\d+)?\s*(?:T|B|M|K|trillion|billion|million|thousand)',
    ]

    @classmethod
    def extract_stock_data(cls, text: str, symbol: str = None) -> Dict[str, Any]:
        """
        Extract stock/financial data from text.

        Args:
            text: Page content to parse
            symbol: Stock ticker or company name for contextual matching

        Returns:
            Dict with 'prices', 'changes', 'market_cap', 'volume', 'raw_matches'
        """
        if not text:
            return {"prices": [], "changes": [], "market_cap": None, "volume": None, "raw_matches": []}

        result = {
            "prices": [],
            "changes": [],
            "market_cap": None,
            "volume": None,
            "raw_matches": [],
        }

        # Extract prices
        for pattern in cls.CURRENCY_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                price_str = match.group(0).strip()
                price_val = cls._parse_numeric(price_str)
                if price_val and cls._is_valid_price(price_val):
                    result["prices"].append({
                        "raw": price_str,
                        "value": price_val,
                    })

        # Extract changes
        for pattern in cls.CHANGE_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                result["changes"].append(match.group(0).strip())

        # Extract market cap
        for pattern in cls.MARKET_CAP_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["market_cap"] = match.group(0).strip()
                break

        # Extract volume
        for pattern in cls.VOLUME_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["volume"] = match.group(0).strip()
                break

        # Contextual search near symbol/keyword
        if symbol:
            context_matches = cls._contextual_search(text, symbol)
            result["raw_matches"] = context_matches

        return result

    @classmethod
    def extract_crypto_data(cls, text: str, name: str = None) -> Dict[str, Any]:
        """
        Extract cryptocurrency data from text.

        Same structure as extract_stock_data with additional crypto-specific patterns.
        """
        result = cls.extract_stock_data(text, symbol=name)

        # Additional crypto patterns (24h change, ATH, etc.)
        ath_match = re.search(
            r'(?:all[- ]?time\s*high|ATH)\s*:?\s*[\$\u20b9]?\s*\d+(?:,\d{3})*(?:\.\d+)?',
            text, re.IGNORECASE
        )
        if ath_match:
            result["ath"] = ath_match.group(0).strip()

        supply_match = re.search(
            r'(?:circulating\s*supply|supply)\s*:?\s*\d+(?:\.\d+)?\s*(?:T|B|M|K)?',
            text, re.IGNORECASE
        )
        if supply_match:
            result["supply"] = supply_match.group(0).strip()

        return result

    @classmethod
    def _contextual_search(cls, text: str, keyword: str, window: int = 100) -> List[str]:
        """Find numbers near a keyword within a character window."""
        matches = []
        keyword_lower = keyword.lower()
        text_lower = text.lower()

        pos = 0
        while True:
            idx = text_lower.find(keyword_lower, pos)
            if idx == -1:
                break

            # Extract window around the keyword
            start = max(0, idx - window // 4)
            end = min(len(text), idx + len(keyword) + window)
            context = text[start:end]

            # Look for numbers in the context
            for match in re.finditer(r'\d{1,3}(?:,\d{3})*(?:\.\d+)?', context):
                value = cls._parse_numeric(match.group(0))
                if value and value > 0:
                    matches.append(f"{keyword}: {match.group(0)}")

            pos = idx + len(keyword)
            if len(matches) >= 5:
                break

        return list(dict.fromkeys(matches))  # Deduplicate preserving order

    @staticmethod
    def _parse_numeric(text: str) -> Optional[float]:
        """Parse a numeric string, removing currency symbols and commas."""
        try:
            clean = re.sub(r'[^\d.,\-]', '', text)
            clean = clean.replace(',', '')
            return float(clean)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _is_valid_price(value: float) -> bool:
        """Validate a price value is within reasonable bounds."""
        return 0 < value < 10_000_000
