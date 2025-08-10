# tests/test_roll.py

from main import roll_impl

def test_roll_parses_and_sums(monkeypatch):
    # Force two rolls: 3 and 4
    seq = iter([3, 4])
    monkeypatch.setattr("main.random.randint", lambda a,b: next(seq))
    out = roll_impl("2d6+1")
    assert out["rolls"] == [3,4]
    assert out["mod"] == 1
    assert out["total"] == 8

    # And do it again with dodgier inputs
    seq = iter([5, 1])
    monkeypatch.setattr("main.random.randint", lambda a,b: next(seq))
    out = roll_impl("2d6+8")
    assert out["rolls"] == [5,1]
    assert out["mod"] == 8
    assert out["total"] == 14

    # And do it again with dodgier inputs
    seq = iter([1, 1])
    monkeypatch.setattr("main.random.randint", lambda a,b: next(seq))
    out = roll_impl("2 d6 - 3")
    assert out["rolls"] == [1,1]
    assert out["mod"] == -3
    assert out["total"] == -1

def test_roll_bad_input():
    assert "error" in roll_impl("foo")
    assert "error" in roll_impl("2x6")
    assert "error" in roll_impl("2 20-sided dice")
    assert "error" in roll_impl("5d8*6")
