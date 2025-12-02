# tests/unit/test_dice.py
"""Unit tests for dice rolling function roll_impl."""

from main import roll_impl


def test_roll_parses_and_sums_basic(monkeypatch):
    """Tests roll_impl: parses 2d6+1 formula and sums correctly."""
    seq = iter([3, 4])
    monkeypatch.setattr("main.random.randint", lambda a, b: next(seq))
    out = roll_impl("2d6+1")
    
    assert out["rolls"] == [3, 4]
    assert out["mod"] == 1
    assert out["total"] == 8


def test_roll_parses_and_sums_larger_modifier(monkeypatch):
    """Tests roll_impl: parses formula with larger modifier."""
    seq = iter([5, 1])
    monkeypatch.setattr("main.random.randint", lambda a, b: next(seq))
    out = roll_impl("2d6+8")
    
    assert out["rolls"] == [5, 1]
    assert out["mod"] == 8
    assert out["total"] == 14


def test_roll_parses_and_sums_negative_modifier(monkeypatch):
    """Tests roll_impl: parses formula with negative modifier and spaces."""
    seq = iter([1, 1])
    monkeypatch.setattr("main.random.randint", lambda a, b: next(seq))
    out = roll_impl("2 d6 - 3")
    
    assert out["rolls"] == [1, 1]
    assert out["mod"] == -3
    assert out["total"] == -1


def test_roll_bad_input_word():
    """Tests roll_impl: returns error for non-formula word input."""
    assert "error" in roll_impl("foo")


def test_roll_bad_input_wrong_separator():
    """Tests roll_impl: returns error for wrong separator (x instead of d)."""
    assert "error" in roll_impl("2x6")


def test_roll_bad_input_spelled_out():
    """Tests roll_impl: returns error for spelled-out dice notation."""
    assert "error" in roll_impl("2 20-sided dice")


def test_roll_bad_input_multiplication():
    """Tests roll_impl: returns error for unsupported multiplication operator."""
    assert "error" in roll_impl("5d8*6")
