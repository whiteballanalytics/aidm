# tests/unit/test_narrative.py
"""Unit tests for extract_narrative_from_runresult function."""

from game_engine import extract_narrative_from_runresult


def test_extract_narrative_with_final_output():
    """Tests extract_narrative_from_runresult: extracts content from RunResult with final_output field."""
    result_text = """RunResult:
- Final output (str): The dragon roars and spreads its wings menacingly!
- 1 new item(s)
- 2 raw response(s)"""
    
    narrative = extract_narrative_from_runresult(result_text)
    
    assert "The dragon roars" in narrative
    assert "1 new item(s)" not in narrative
    assert "2 raw response(s)" not in narrative


def test_extract_narrative_without_runresult_format():
    """Tests extract_narrative_from_runresult: returns text as-is when not RunResult format."""
    plain_text = "You enter the tavern. The smell of ale fills the air."
    
    narrative = extract_narrative_from_runresult(plain_text)
    
    assert narrative == plain_text


def test_extract_narrative_empty_result():
    """Tests extract_narrative_from_runresult: handles empty string input."""
    empty = ""
    
    narrative = extract_narrative_from_runresult(empty)
    
    assert narrative == ""


def test_extract_narrative_none_input():
    """Tests extract_narrative_from_runresult: handles None input gracefully."""
    narrative = extract_narrative_from_runresult(None)
    
    assert narrative is None


def test_extract_narrative_multiline_content():
    """Tests extract_narrative_from_runresult: handles multiline narrative content."""
    result_text = """RunResult:
- Final output (str): The goblin chief steps forward.

"You dare enter my domain?" he snarls.

Roll for initiative!
- 1 new item(s)"""
    
    narrative = extract_narrative_from_runresult(result_text)
    
    assert "goblin chief" in narrative
    assert "Roll for initiative" in narrative
    assert "1 new item(s)" not in narrative
