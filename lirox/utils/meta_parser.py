import json
import re

def extract_meta(text: str) -> tuple[str, dict]:
    """Extracts LIROX_META JSON from LLM response and returns clean text + meta."""
    pattern = r'```json\s+(?:LIROX_META\n)?(\{.*?\})\s+```|LIROX_META:\s*({.*?})'
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    
    if not match:
        # Fallback for non-fenced or simple blocks
        try:
            # Look for the last { and last }
            start = text.rfind('{')
            end = text.rfind('}')
            if start != -1 and end != -1 and end > start:
                json_str = text[start:end+1]
                meta = json.loads(json_str)
                clean_text = text[:start].strip()
                return clean_text, meta
        except:
            pass
        return text, {}

    json_str = match.group(1) or match.group(2)
    try:
        meta = json.loads(json_str)
        # Remove the match from the text
        clean_text = text[:match.start()].strip() + "\n" + text[match.end():].strip()
        return clean_text.strip(), meta
    except:
        return text, {}
