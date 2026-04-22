import pytest
from lirox.agents.personal_agent import PersonalAgent

def test_filegen_fallback():
    agent = PersonalAgent()
    fallback = agent._filegen_fallback("Make a slide deck about cars")
    assert fallback["file_type"] == "pptx"
    assert "sections" in fallback
    assert "slides" in fallback
    assert "sheets" in fallback
    
def test_filegen_fallback_pdf():
    agent = PersonalAgent()
    fallback = agent._filegen_fallback("Generate a report on AI")
    assert fallback["file_type"] == "pdf"
