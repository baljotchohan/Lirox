import pytest
from lirox.utils.input_sanitizer import sanitize_user_name
from lirox.tools.document_creators.pdf_creator import create_pdf

def test_sanitize_user_name():
    assert sanitize_user_name("Lirox AI") == ""
    assert sanitize_user_name("Lirox") == ""
    assert sanitize_user_name("lirox-ai") == ""
    assert sanitize_user_name("lirox compact") == ""
    assert sanitize_user_name("John Doe") == "John Doe"
    assert sanitize_user_name("") == ""
    assert sanitize_user_name(None) == ""

def test_pdf_creator_metadata(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    sections = [{"heading": "Test", "body": "Body text", "bullets": []}]
    receipt = create_pdf(str(pdf_path), "Test Doc", sections, user_name="Alice Smith")
    assert receipt.ok is True
    assert pdf_path.exists()
