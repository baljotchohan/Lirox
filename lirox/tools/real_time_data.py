"""
Lirox v2.0 — Real-Time Data Extractor

Extracts structured financial and other real-time data from text.
"""

from __future__ import annotations

import re
from typing import Dict, Any, List


class RealTimeDataExtractor:
    """Extracts structured data (prices, etc.) from unstructured text."""

    @staticmethod
    def extract_stock_data(text: str, symbol: str) -> Dict[str, Any]:
        """
        Extract stock price data for a given ticker symbol from text.

        Args:
            text:   Raw text containing stock information.
            symbol: Ticker symbol to look for (e.g. "AAPL").

        Returns:
            Dict with:
              - symbol: str
              - prices: List[float]  — extracted price values
              - changes: List[str]   — extracted change strings (e.g. "+2.5%")
              - raw: str             — original text
        """
        prices:  List[float] = []
        changes: List[str]   = []

        # Match price patterns: $185.43 or 185.43
        price_pattern = re.compile(r"\$?([\d,]+\.?\d*)")
        for match in price_pattern.finditer(text):
            try:
                value = float(match.group(1).replace(",", ""))
                if value > 0:
                    prices.append(value)
            except ValueError:
                continue

        # Match change patterns: +2.5% or -1.3%
        change_pattern = re.compile(r"[+\-]\d+\.?\d*%")
        changes = change_pattern.findall(text)

        return {
            "symbol":  symbol,
            "prices":  prices,
            "changes": changes,
            "raw":     text,
        }

    @staticmethod
    def extract_crypto_data(text: str, symbol: str) -> Dict[str, Any]:
        """
        Extract cryptocurrency price data from text.

        Args:
            text:   Raw text containing crypto price info.
            symbol: Crypto symbol (e.g. "BTC").

        Returns:
            Same structure as extract_stock_data.
        """
        return RealTimeDataExtractor.extract_stock_data(text, symbol)
