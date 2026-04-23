"""Content templates for rich, structured generation."""

RICH_SECTION_TEMPLATE = """
SECTION: {title}

OVERVIEW:
{overview_paragraph - 2-3 sentences}

KEY POINTS:
• {point_1 - with detail}
• {point_2 - with detail}
• {point_3 - with detail}

DETAILED ANALYSIS:
{paragraph 1 - 200+ words with examples, dates, specific facts}

{paragraph 2 - 200+ words with analysis, quotes, context}

PRACTICAL EXAMPLES:
{example 1 with specific details}
{example 2 with specific details}

FURTHER READING:
• {Reference 1}
• {Reference 2}

SUMMARY:
{Key takeaways - what reader learned}
"""
