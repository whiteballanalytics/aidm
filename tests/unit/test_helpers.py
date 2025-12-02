# tests/unit/test_helpers.py
"""Unit tests for helper functions: merge_scene_patch, extract_update_payload, strip_json_block, clip_recap."""

import json
from game_engine import SceneState, merge_scene_patch, extract_update_payload, strip_json_block
from main import clip_recap


def test_merge_scene_patch_replaces_only_provided_fields():
    """Tests merge_scene_patch: replaces provided fields, ignores None, preserves omitted fields."""
    before = SceneState(
        time_of_day="night",
        region="A",
        sub_region="B",
        specific_location="dock",
        participants=["vendor"],
        exits=["north"],
    )

    patch = {
        "time_of_day": "dawn",
        "participants": ["guards"],
        "specific_location": None,
    }

    after = merge_scene_patch(before, patch)

    assert after.time_of_day == "dawn"
    assert after.participants == ["guards"]
    assert after.region == "A"
    assert after.sub_region == "B"
    assert after.exits == ["north"]
    assert after.specific_location == "dock"
    assert after is not before


def test_extract_update_payload_valid_json_in_markdown():
    """Tests extract_update_payload: extracts dict from valid JSON in markdown block."""
    prose = "You wake.\n```json\n{\"turn_summary\":\"ok\"}\n```\nTail."
    payload = extract_update_payload(prose)
    
    assert payload is not None
    assert payload["turn_summary"] == "ok"


def test_extract_update_payload_bare_json():
    """Tests extract_update_payload: returns None for bare JSON (requires markdown fencing)."""
    bare = '{"turn_summary": "ok"}'
    payload = extract_update_payload(bare)
    
    assert payload is None


def test_extract_update_payload_malformed_json():
    """Tests extract_update_payload: returns None for malformed JSON (does not crash)."""
    malformed = "```json\n{broken: json\n```"
    payload = extract_update_payload(malformed)
    
    assert payload is None


def test_extract_update_payload_no_json_present():
    """Tests extract_update_payload: returns None when no JSON block is present."""
    prose = "Just some regular text without any JSON."
    payload = extract_update_payload(prose)
    
    assert payload is None


def test_extract_update_payload_multiple_json_blocks():
    """Tests extract_update_payload: extracts the last JSON block when multiple are present (design choice)."""
    prose = """
First block:
```json
{"first": true}
```

Second block:
```json
{"second": true, "value": 42}
```
End.
"""
    payload = extract_update_payload(prose)
    
    assert payload is not None
    assert "second" in payload
    assert payload["value"] == 42
    assert "first" not in payload


def test_strip_json_block_removes_json():
    """Tests strip_json_block: removes JSON block and returns only narrative text."""
    prose = "You wake.\n```json\n{\"turn_summary\":\"ok\"}\n```\nTail."
    stripped = strip_json_block(prose)
    
    assert "```json" not in stripped
    assert "turn_summary" not in stripped
    assert "You wake." in stripped
    assert "Tail." in stripped


def test_clip_recap_appends_under_limit():
    """Tests clip_recap: appends turn_summary when total is under limit."""
    prev = "We met a guard."
    turn_summary = "We bribed him."
    out = clip_recap(prev, turn_summary, limit_chars=700)

    assert out == "We met a guard. We bribed him."


def test_clip_recap_truncates_from_front_when_over_limit():
    """Tests clip_recap: truncates from front when over limit, keeping most recent content."""
    prev = "A" * 690
    turn_summary = "B" * 30
    out = clip_recap(prev, turn_summary, limit_chars=700)

    assert out == ("A" * 669) + " " + ("B" * 30)


def test_clip_recap_handles_none_summary():
    """Tests clip_recap: handles None turn_summary gracefully."""
    prev = "Start"
    turn_summary = None
    out = clip_recap(prev, turn_summary, limit_chars=700)

    assert out == "Start"
