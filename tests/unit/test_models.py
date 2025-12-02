# tests/unit/test_models.py
"""Unit tests for data model serialization: SceneState."""

import json

from game_engine import SceneState


def test_scenestate_model_dump_all_fields():
    """Tests SceneState.model_dump: all fields serialize without error."""
    scene = SceneState(
        time_of_day="morning",
        region="Sword Coast",
        sub_region="Waterdeep",
        specific_location="The Yawning Portal",
        participants=["Durnan", "adventurer"],
        exits=["street", "cellar"],
    )
    
    data = scene.model_dump()
    
    assert data["time_of_day"] == "morning"
    assert data["region"] == "Sword Coast"
    assert data["sub_region"] == "Waterdeep"
    assert data["specific_location"] == "The Yawning Portal"
    assert data["participants"] == ["Durnan", "adventurer"]
    assert data["exits"] == ["street", "cellar"]


def test_scenestate_json_roundtrip():
    """Tests SceneState: JSON can be deserialized back to identical SceneState."""
    original = SceneState(
        time_of_day="dusk",
        region="Neverwinter",
        sub_region="Docks",
        specific_location="The Sunken Flagon",
        participants=["Sand", "Neeshka"],
        exits=["main door", "back alley"],
    )
    
    json_str = json.dumps(original.model_dump())
    restored_data = json.loads(json_str)
    restored = SceneState(**restored_data)
    
    assert restored.time_of_day == original.time_of_day
    assert restored.region == original.region
    assert restored.sub_region == original.sub_region
    assert restored.specific_location == original.specific_location
    assert restored.participants == original.participants
    assert restored.exits == original.exits


def test_scenestate_empty_lists():
    """Tests SceneState: handles empty lists for participants and exits."""
    scene = SceneState(
        time_of_day="midnight",
        region="Underdark",
        sub_region="Menzoberranzan",
        specific_location="Empty cavern",
        participants=[],
        exits=[],
    )
    
    data = scene.model_dump()
    assert data["participants"] == []
    assert data["exits"] == []
    
    json_str = json.dumps(data)
    restored = SceneState(**json.loads(json_str))
    assert restored.participants == []
    assert restored.exits == []


def test_scenestate_unicode_content():
    """Tests SceneState: handles unicode characters in string fields."""
    scene = SceneState(
        time_of_day="午後",
        region="東方",
        sub_region="龍の巣",
        specific_location="宝物庫",
        participants=["竜", "魔法使い"],
        exits=["北への通路", "南への扉"],
    )
    
    data = scene.model_dump()
    json_str = json.dumps(data, ensure_ascii=False)
    restored = SceneState(**json.loads(json_str))
    
    assert restored.time_of_day == "午後"
    assert restored.region == "東方"
    assert "竜" in restored.participants
