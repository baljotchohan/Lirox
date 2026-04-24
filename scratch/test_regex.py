import re

_FILEGEN_PATTERN = re.compile(
    r'\b(?:create|make|generate|build|prepare|draft|write|design)\b'
    r'.*\b(?:pdf|word|docx|doc|excel|xlsx|xls|spreadsheet|'
    r'pptx?|powerpoint|presentation|slides?|report|repoty?|resume|invoice|'
    r'certificate|letter|memo|proposal|deck|document|file|paper|chart)\b',
    re.IGNORECASE,
)

query = "create a chart repoty of ai effecting areas in 2026"
match = _FILEGEN_PATTERN.search(query.lower().strip())
print(f"Match found: {bool(match)}")
if match:
    print(f"Matched text: {match.group(0)}")
