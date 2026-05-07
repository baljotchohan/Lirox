import pytest
from lirox.agents.classifier import _classify

def test_classify_shell_commands():
    assert _classify("run pip install pandas") == ("shell", "low")
    assert _classify("create a new dir") == ("shell", "low")

def test_classify_file_generation():
    assert _classify("create a PDF report on marketing") == ("filegen", "high")
    assert _classify("generate a docx for the Q3 plan") == ("filegen", "high")
    assert _classify("make me a spreadsheet with sales data") == ("filegen", "medium")

def test_classify_file_operations():
    assert _classify("write hello to a file") == ("file", "low")
    assert _classify("save this string in test.txt") == ("file", "low")

def test_classify_web_search():
    assert _classify("search the web for python tutorials") == ("web", "low")
    assert _classify("google who won the superbowl") == ("web", "low")

def test_classify_chat():
    assert _classify("hello there") == ("chat", "low")
    assert _classify("how are you doing") == ("chat", "low")

def test_classify_complexity():
    complex_query = "explain how the transformer architecture works in deep learning and what the pros and cons are"
    assert _classify(complex_query) == ("chat", "high")
