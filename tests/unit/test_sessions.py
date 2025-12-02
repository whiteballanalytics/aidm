# tests/unit/test_sessions.py
"""Unit tests for session functions: load_session, list_sessions, get_active_session, close_session."""

import json
import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import game_engine


class TestLoadSession:
    """Tests for load_session function."""

    @pytest.mark.asyncio
    async def test_load_session_returns_none_for_missing(self, tmp_path, monkeypatch):
        """Tests load_session: returns None when session file does not exist."""
        monkeypatch.setattr("game_engine.SESSIONS_BASE_PATH", str(tmp_path / "sessions"))
        
        result = await game_engine.load_session("camp_001", "nonexistent_session")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_load_session_returns_data_for_existing(self, tmp_path, monkeypatch):
        """Tests load_session: returns session data when file exists."""
        sessions_dir = tmp_path / "sessions" / "camp_001"
        sessions_dir.mkdir(parents=True)
        session_data = {"session_id": "sess_001", "status": "open", "turn_count": 5}
        (sessions_dir / "sess_001_session.json").write_text(json.dumps(session_data))
        monkeypatch.setattr("game_engine.SESSIONS_BASE_PATH", str(tmp_path / "sessions"))
        
        result = await game_engine.load_session("camp_001", "sess_001")
        
        assert result is not None
        assert result["session_id"] == "sess_001"
        assert result["turn_count"] == 5

    @pytest.mark.asyncio
    async def test_load_session_returns_none_for_invalid_json(self, tmp_path, monkeypatch):
        """Tests load_session: returns None when session file contains invalid JSON."""
        sessions_dir = tmp_path / "sessions" / "camp_001"
        sessions_dir.mkdir(parents=True)
        (sessions_dir / "sess_001_session.json").write_text("not valid json {{{")
        monkeypatch.setattr("game_engine.SESSIONS_BASE_PATH", str(tmp_path / "sessions"))
        
        result = await game_engine.load_session("camp_001", "sess_001")
        
        assert result is None


class TestListSessions:
    """Tests for list_sessions function."""

    @pytest.mark.asyncio
    async def test_list_sessions_returns_empty_for_no_directory(self, tmp_path, monkeypatch):
        """Tests list_sessions: returns empty list when campaign directory does not exist."""
        monkeypatch.setattr("game_engine.SESSIONS_BASE_PATH", str(tmp_path / "sessions"))
        
        result = await game_engine.list_sessions("nonexistent_campaign")
        
        assert result == []

    @pytest.mark.asyncio
    async def test_list_sessions_sorted_newest_first(self, tmp_path, monkeypatch):
        """Tests list_sessions: returns sessions sorted by created_at, newest first."""
        sessions_dir = tmp_path / "sessions" / "camp_001"
        sessions_dir.mkdir(parents=True)
        
        old_session = {"session_id": "old", "created_at": "2024-01-01 10:00:00", "status": "complete"}
        new_session = {"session_id": "new", "created_at": "2024-12-01 10:00:00", "status": "open"}
        
        (sessions_dir / "old_session.json").write_text(json.dumps(old_session))
        (sessions_dir / "new_session.json").write_text(json.dumps(new_session))
        monkeypatch.setattr("game_engine.SESSIONS_BASE_PATH", str(tmp_path / "sessions"))
        
        result = await game_engine.list_sessions("camp_001")
        
        assert len(result) == 2
        assert result[0]["session_id"] == "new"
        assert result[1]["session_id"] == "old"

    @pytest.mark.asyncio
    async def test_list_sessions_adds_default_status(self, tmp_path, monkeypatch):
        """Tests list_sessions: adds status='complete' to old sessions missing that field."""
        sessions_dir = tmp_path / "sessions" / "camp_001"
        sessions_dir.mkdir(parents=True)
        
        old_format_session = {"session_id": "legacy", "created_at": "2024-01-01 10:00:00"}
        (sessions_dir / "legacy_session.json").write_text(json.dumps(old_format_session))
        monkeypatch.setattr("game_engine.SESSIONS_BASE_PATH", str(tmp_path / "sessions"))
        
        result = await game_engine.list_sessions("camp_001")
        
        assert len(result) == 1
        assert result[0]["status"] == "complete"


class TestGetActiveSession:
    """Tests for get_active_session function."""

    @pytest.mark.asyncio
    async def test_get_active_session_finds_open(self, tmp_path, monkeypatch):
        """Tests get_active_session: returns session with status='open' when one exists."""
        sessions_dir = tmp_path / "sessions" / "camp_001"
        sessions_dir.mkdir(parents=True)
        
        complete_session = {"session_id": "done", "created_at": "2024-01-01", "status": "complete"}
        open_session = {"session_id": "active", "created_at": "2024-12-01", "status": "open"}
        
        (sessions_dir / "done_session.json").write_text(json.dumps(complete_session))
        (sessions_dir / "active_session.json").write_text(json.dumps(open_session))
        monkeypatch.setattr("game_engine.SESSIONS_BASE_PATH", str(tmp_path / "sessions"))
        
        result = await game_engine.get_active_session("camp_001")
        
        assert result is not None
        assert result["session_id"] == "active"
        assert result["status"] == "open"

    @pytest.mark.asyncio
    async def test_get_active_session_returns_none_when_all_complete(self, tmp_path, monkeypatch):
        """Tests get_active_session: returns None when all sessions are complete."""
        sessions_dir = tmp_path / "sessions" / "camp_001"
        sessions_dir.mkdir(parents=True)
        
        complete_session = {"session_id": "done", "created_at": "2024-01-01", "status": "complete"}
        (sessions_dir / "done_session.json").write_text(json.dumps(complete_session))
        monkeypatch.setattr("game_engine.SESSIONS_BASE_PATH", str(tmp_path / "sessions"))
        
        result = await game_engine.get_active_session("camp_001")
        
        assert result is None


class TestCloseSession:
    """Tests for close_session function."""

    @pytest.mark.asyncio
    async def test_close_session_raises_for_missing(self, tmp_path, monkeypatch):
        """Tests close_session: raises ValueError when session does not exist."""
        monkeypatch.setattr("game_engine.SESSIONS_BASE_PATH", str(tmp_path / "sessions"))
        
        with pytest.raises(ValueError, match="not found"):
            await game_engine.close_session("camp_001", "nonexistent")

    @pytest.mark.asyncio
    async def test_close_session_sets_status_complete(self, tmp_path, monkeypatch):
        """Tests close_session: sets session status to 'complete' after closing."""
        sessions_dir = tmp_path / "sessions" / "camp_001"
        sessions_dir.mkdir(parents=True)
        
        session_data = {
            "session_id": "sess_001",
            "campaign_id": "camp_001",
            "status": "open",
            "created_at": "2024-01-01",
            "chat_history": []
        }
        session_file = sessions_dir / "sess_001_session.json"
        session_file.write_text(json.dumps(session_data))
        
        monkeypatch.setattr("game_engine.SESSIONS_BASE_PATH", str(tmp_path / "sessions"))
        
        with patch("game_engine.generate_post_session_analysis", new_callable=AsyncMock) as mock_analysis:
            mock_analysis.return_value = "Session analysis text."
            
            result = await game_engine.close_session("camp_001", "sess_001")
        
        assert result["status"] == "complete"

    @pytest.mark.asyncio
    async def test_close_session_saves_post_analysis(self, tmp_path, monkeypatch):
        """Tests close_session: saves post_session_analysis from LLM to session data."""
        sessions_dir = tmp_path / "sessions" / "camp_001"
        sessions_dir.mkdir(parents=True)
        
        session_data = {
            "session_id": "sess_001",
            "campaign_id": "camp_001",
            "status": "open",
            "created_at": "2024-01-01",
            "chat_history": []
        }
        session_file = sessions_dir / "sess_001_session.json"
        session_file.write_text(json.dumps(session_data))
        
        monkeypatch.setattr("game_engine.SESSIONS_BASE_PATH", str(tmp_path / "sessions"))
        
        with patch("game_engine.generate_post_session_analysis", new_callable=AsyncMock) as mock_analysis:
            mock_analysis.return_value = "The party defeated the dragon."
            
            result = await game_engine.close_session("camp_001", "sess_001")
        
        assert result["post_session_analysis"] == "The party defeated the dragon."

    @pytest.mark.asyncio
    async def test_close_session_writes_to_disk(self, tmp_path, monkeypatch):
        """Tests close_session: writes updated session data to disk."""
        sessions_dir = tmp_path / "sessions" / "camp_001"
        sessions_dir.mkdir(parents=True)
        
        session_data = {
            "session_id": "sess_001",
            "campaign_id": "camp_001",
            "status": "open",
            "created_at": "2024-01-01",
            "chat_history": []
        }
        session_file = sessions_dir / "sess_001_session.json"
        session_file.write_text(json.dumps(session_data))
        
        monkeypatch.setattr("game_engine.SESSIONS_BASE_PATH", str(tmp_path / "sessions"))
        
        with patch("game_engine.generate_post_session_analysis", new_callable=AsyncMock) as mock_analysis:
            mock_analysis.return_value = "Analysis."
            
            await game_engine.close_session("camp_001", "sess_001")
        
        saved_data = json.loads(session_file.read_text())
        assert saved_data["status"] == "complete"
        assert "post_session_analysis" in saved_data

    @pytest.mark.asyncio
    async def test_close_session_updates_last_activity(self, tmp_path, monkeypatch):
        """Tests close_session: updates last_activity timestamp when closing."""
        sessions_dir = tmp_path / "sessions" / "camp_001"
        sessions_dir.mkdir(parents=True)
        
        session_data = {
            "session_id": "sess_001",
            "campaign_id": "camp_001",
            "status": "open",
            "created_at": "2024-01-01",
            "last_activity": "2024-01-01 10:00:00",
            "chat_history": []
        }
        session_file = sessions_dir / "sess_001_session.json"
        session_file.write_text(json.dumps(session_data))
        
        monkeypatch.setattr("game_engine.SESSIONS_BASE_PATH", str(tmp_path / "sessions"))
        
        with patch("game_engine.generate_post_session_analysis", new_callable=AsyncMock) as mock_analysis:
            mock_analysis.return_value = "Analysis."
            
            result = await game_engine.close_session("camp_001", "sess_001")
        
        assert result["last_activity"] != "2024-01-01 10:00:00"
