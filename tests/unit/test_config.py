# tests/unit/test_config.py
"""Unit tests for configuration functions: get_available_worlds, jl_write."""

import json
import pytest
from pathlib import Path

import game_engine
from library.logginghooks import jl_write, LOG_PATH


class TestGetAvailableWorlds:
    """Tests for get_available_worlds function."""

    def test_get_available_worlds_returns_empty_without_config(self, tmp_path, monkeypatch):
        """Tests get_available_worlds: returns empty dict when config file is missing."""
        monkeypatch.chdir(tmp_path)
        
        result = game_engine.get_available_worlds()
        
        assert result == {}

    def test_get_available_worlds_returns_worlds_dict(self, tmp_path, monkeypatch):
        """Tests get_available_worlds: returns world dict from config file."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        
        config_data = {
            "world": {
                "SwordCoast": {"id": "vs_123", "name": "Sword Coast"},
                "Ravenloft": {"id": "vs_456", "name": "Ravenloft"}
            }
        }
        (config_dir / "vectorstores.json").write_text(json.dumps(config_data))
        monkeypatch.chdir(tmp_path)
        
        result = game_engine.get_available_worlds()
        
        assert "SwordCoast" in result
        assert "Ravenloft" in result

    def test_get_available_worlds_returns_empty_for_invalid_json(self, tmp_path, monkeypatch):
        """Tests get_available_worlds: returns empty dict when config contains invalid JSON."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "vectorstores.json").write_text("not valid json")
        monkeypatch.chdir(tmp_path)
        
        result = game_engine.get_available_worlds()
        
        assert result == {}

    def test_get_available_worlds_returns_empty_when_no_world_key(self, tmp_path, monkeypatch):
        """Tests get_available_worlds: returns empty dict when config lacks 'world' key."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        
        config_data = {"other_key": "some_value"}
        (config_dir / "vectorstores.json").write_text(json.dumps(config_data))
        monkeypatch.chdir(tmp_path)
        
        result = game_engine.get_available_worlds()
        
        assert result == {}


class TestJlWrite:
    """Tests for jl_write logging function."""

    def test_jl_write_appends_json_line(self, tmp_path, monkeypatch):
        """Tests jl_write: appends a JSON line to the log file."""
        log_file = tmp_path / "test.jsonl"
        monkeypatch.setattr("library.logginghooks.LOG_PATH", log_file)
        
        jl_write({"event": "test_event", "value": 42})
        
        assert log_file.exists()
        content = log_file.read_text()
        record = json.loads(content.strip())
        assert record["event"] == "test_event"
        assert record["value"] == 42

    def test_jl_write_appends_multiple_records(self, tmp_path, monkeypatch):
        """Tests jl_write: appends multiple records as separate lines."""
        log_file = tmp_path / "test.jsonl"
        monkeypatch.setattr("library.logginghooks.LOG_PATH", log_file)
        
        jl_write({"event": "first"})
        jl_write({"event": "second"})
        jl_write({"event": "third"})
        
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 3
        assert json.loads(lines[0])["event"] == "first"
        assert json.loads(lines[2])["event"] == "third"

    def test_jl_write_handles_unicode(self, tmp_path, monkeypatch):
        """Tests jl_write: correctly handles unicode characters in records."""
        log_file = tmp_path / "test.jsonl"
        monkeypatch.setattr("library.logginghooks.LOG_PATH", log_file)
        
        jl_write({"message": "The dragon's lair has treasures!"})
        
        content = log_file.read_text()
        record = json.loads(content.strip())
        assert "dragon's" in record["message"]
