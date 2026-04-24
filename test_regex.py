import re

def _enforce_zero_asterisk(text: str) -> str:
    if not text:
        return text
    
    # Split by code blocks
    parts = re.split(r'(```.*?```|`.*?`)', text, flags=re.DOTALL)
    
    for i in range(len(parts)):
        # Only modify text outside code blocks (even indices in the split)
        if i % 2 == 0:
            part = parts[i]
            # Replace **bold**
            part = re.sub(r'\*\*(.*?)\*\*', r'__\1__', part)
            # Replace *italic*
            part = re.sub(r'(?<!\w)\*(?!\s)(.*?)(?<!\s)\*(?!\w)', r'_\1_', part)
            # Replace bullet points (* or -)
            part = re.sub(r'^([ \t]*)\*[ \t]+', r'\1🔹 ', part, flags=re.MULTILINE)
            part = re.sub(r'^([ \t]*)\-[ \t]+', r'\1🔸 ', part, flags=re.MULTILINE)
            parts[i] = part
            
    return "".join(parts)

test_str = """
Here is some text with **bold** and *italic*.
* Bullet 1
* Bullet 2
  - Sub bullet
  - Sub bullet 2
  
```python
# code block
a = 5 * 3
b = a - 2
# do not touch **bold** here
```
Another *test* here.
"""

print(_enforce_zero_asterisk(test_str))
