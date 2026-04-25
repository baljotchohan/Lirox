"""
Text Similarity Calculation (Jaccard-based, no external deps)
"""
import re


def calculate_similarity(text1: str, text2: str) -> float:
    """
    Jaccard similarity between two texts.

    Returns 0.0 (completely different) → 1.0 (identical).
    Operates purely on word-level tokens; no external libraries required.
    """
    words1 = set(_normalize(text1).split())
    words2 = set(_normalize(text2).split())

    union = words1 | words2
    if not union:
        return 0.0

    return len(words1 & words2) / len(union)


def _normalize(text: str) -> str:
    """Lowercase and strip punctuation."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())
