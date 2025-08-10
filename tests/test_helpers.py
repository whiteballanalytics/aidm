# tests/test_helpers.py

import json
from types import SimpleNamespace
from main import merge_scene_patch, extract_update_payload, strip_json_block, clip_recap
from main import SceneState, JSON_BLOCK_RE


def test_merge_scene_patch_replaces_only_provided_fields():
    before = SceneState(
        time_of_day="night",
        region="A",
        sub_region="B",
        specific_location="dock",
        participants=["vendor"],
        exits=["north"],
    )

    patch = {
        "time_of_day": "dawn",        # should replace
        "participants": ["guards"],   # should replace
        "specific_location": None,    # should be ignored (keeps "dock")
        # region/sub_region/exits omitted → should remain unchanged
    }

    after = merge_scene_patch(before, patch)

    # updated fields
    assert after.time_of_day == "dawn"
    assert after.participants == ["guards"]

    # unchanged fields
    assert after.region == "A"
    assert after.sub_region == "B"
    assert after.exits == ["north"]
    assert after.specific_location == "dock"  # None is ignored

    # ensure we got a NEW object (not in-place mutation)
    assert after is not before


def test_extract_and_strip():
    prose = "You wake.\n```json\n{\"turn_summary\":\"ok\"}\n```\nTail."
    payload = extract_update_payload(prose)

    # ensure correct parsing
    assert payload["turn_summary"] == "ok"
    assert "```json" not in strip_json_block(prose)


def test_clip_recap_appends_under_limit():
    prev = "We met a guard."
    turn_summary = "We bribed him."
    out = clip_recap(prev, turn_summary, limit_chars=700)

    # ensure it just appends since total is under limit
    assert out == "We met a guard. We bribed him."


def test_clip_recap_truncates_from_front_when_over_limit():
    prev = "A" * 690
    turn_summary = "B" * 30
    # combined: 690 'A' + ' ' + 30 'B' = 721 chars -> should clip to last 700
    out = clip_recap(prev, turn_summary, limit_chars=700)

    # expect 21 leading 'A's dropped: 669 'A' + ' ' + 30 'B'
    assert out == ("A" * 669) + " " + ("B" * 30)


def test_clip_recap_handles_none_summary():
    prev = "Start"
    turn_summary = None
    out = clip_recap(prev, turn_summary, limit_chars=700)

    # should just return the previous text
    assert out == "Start"