"""
Format Enforcer (Pipeline Module)
Determines and enforces correct output file format.
"""
import logging
import re

_logger = logging.getLogger("lirox.pipeline.format")


class FormatEnforcer:
    """Determines the correct output format from user query."""

    _EXPLICIT: list = [
        (r"\.(md|markdown)\b",                       "md"),
        (r"\b(markdown|\.md)\b",                     "md"),
        (r"\.(txt|text file)\b",                     "txt"),
        (r"\.html?\b",                               "html"),
        (r"\.pdf\b",                                 "pdf"),
        (r"\.(docx?|word)\b",                        "docx"),
        (r"\b(word document|word file)\b",           "docx"),
        (r"\.(xlsx?|excel|spreadsheet)\b",           "xlsx"),
        (r"\b(excel|spreadsheet)\b",                 "xlsx"),
        (r"\.(pptx?|powerpoint|presentation|slides)","pptx"),
        (r"\b(powerpoint|presentation|slides|deck)\b","pptx"),
    ]

    _INTENT: list = [
        (["copy paste", "prompt file", "cursor", "windsurf"],            "md"),
        (["resume", "cv"],                                               "docx"),
        (["report", "research", "thesis", "essay"],                      "pdf"),
        (["website", "site", "landing page", "web page"],               "html"),
        (["budget", "tracker", "data", "table", "sheet"],               "xlsx"),
        (["pitch", "presentation", "deck", "slides"],                   "pptx"),
        (["document", "brief", "memo", "proposal", "letter"],           "pdf"),
    ]

    def determine_format(self, query: str) -> str:
        """Return the correct file extension for this query."""
        q = query.lower()
        for pattern, fmt in self._EXPLICIT:
            if re.search(pattern, q):
                return fmt
        for keywords, fmt in self._INTENT:
            if any(kw in q for kw in keywords):
                return fmt
        return "pdf"
