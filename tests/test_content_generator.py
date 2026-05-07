import pytest
from lirox.tools.content_generator import ContentGenerator

def test_generate_sections_consumes_generator():
    """
    Tests that generate() correctly consumes the generator from
    generate_sections() and populates the results correctly.
    """
    generator = ContentGenerator()
    
    # Mock section generator to test consumption logic
    def mock_generate_sections(*args, **kwargs):
        yield {"type": "progress", "message": "generating section 1"}
        yield {"title": "Section 1", "content": "Content 1"}
        yield {"type": "progress", "message": "generating section 2"}
        yield {"title": "Section 2", "content": "Content 2"}

    # Replace the method with our mock
    generator.generate_sections = mock_generate_sections
    
    # Run the generate function which should consume the generator
    plan = {"topic": "Test", "audience": "beginner", "theme": "educational"}
    structure = type("Structure", (), {"sections": []})()
    
    result = None
    for event in generator.generate(plan, structure):
        if event.get("type") == "done":
            result = event.get("data")
            
    assert result is not None
    assert "sections" in result
    assert isinstance(result["sections"], list)
    assert len(result["sections"]) == 2
    assert result["sections"][0]["title"] == "Section 1"
    assert result["sections"][1]["title"] == "Section 2"
