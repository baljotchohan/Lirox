import json
import re

def extract_meta(text: str) -> tuple[str, dict]:
    """
    Safely extracts and completely removes LIROX_META artifacts.
    Legacy fallback: We don't ask for this anymore, but if it hallucinates it, we strip it out.
    """
    # Specifically target LIROX_META: and any following json block.
    # Often it hallucinated like: LIROX_META:\n```json\n{...}\n```
    pattern = r'(?:LIROX_META:?)?\s*```json\s*(\{.*?\})\s*```'
    
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    meta = {}
    
    if match:
        try:
            meta = json.loads(match.group(1))
            text = text[:match.start()] + text[match.end():]
        except Exception:
            pass
            
    # As a secondary cleanup, if "LIROX_META:" is just hanging around without JSON, strip it.
    text = re.sub(r'LIROX_META:?\s*', '', text, flags=re.IGNORECASE)
    
    # Strip any stray `[jarves] ✦` tags that slip through
    text = re.sub(r'\[.*?\]\s*✦\s*', '', text)
    
    return text.strip(), meta
