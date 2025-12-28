# tests/unit/test_campaigns.py
"""Unit tests for campaign functions: load_campaign, list_campaigns, update_last_played."""

import json
import pytest

import game_engine


class TestLoadCampaign:
    """Tests for load_campaign function."""

    @pytest.mark.asyncio
    async def test_load_campaign_returns_none_for_missing(self, tmp_path, monkeypatch):
        """Tests load_campaign: returns None when campaign file does not exist."""
        monkeypatch.setattr("game_engine.CAMPAIGN_BASE_PATH", str(tmp_path / "campaigns"))
        
        result = await game_engine.load_campaign("nonexistent_campaign")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_load_campaign_returns_data_for_existing(self, tmp_path, monkeypatch):
        """Tests load_campaign: returns campaign data when file exists."""
        campaigns_dir = tmp_path / "campaigns"
        campaigns_dir.mkdir(parents=True)
        campaign_data = {
            "campaign_id": "camp_001",
            "name": "Dragon Quest",
            "world_collection": "SwordCoast"
        }
        (campaigns_dir / "camp_001_outline.json").write_text(json.dumps(campaign_data))
        monkeypatch.setattr("game_engine.CAMPAIGN_BASE_PATH", str(tmp_path / "campaigns"))
        
        result = await game_engine.load_campaign("camp_001")
        
        assert result is not None
        assert result["campaign_id"] == "camp_001"
        assert result["name"] == "Dragon Quest"

    @pytest.mark.asyncio
    async def test_load_campaign_returns_none_for_invalid_json(self, tmp_path, monkeypatch):
        """Tests load_campaign: returns None when campaign file contains invalid JSON."""
        campaigns_dir = tmp_path / "campaigns"
        campaigns_dir.mkdir(parents=True)
        (campaigns_dir / "camp_001_outline.json").write_text("not valid json")
        monkeypatch.setattr("game_engine.CAMPAIGN_BASE_PATH", str(tmp_path / "campaigns"))
        
        result = await game_engine.load_campaign("camp_001")
        
        assert result is None


class TestListCampaigns:
    """Tests for list_campaigns function."""

    @pytest.mark.asyncio
    async def test_list_campaigns_returns_empty_for_no_directory(self, tmp_path, monkeypatch):
        """Tests list_campaigns: returns empty list when campaigns directory does not exist."""
        monkeypatch.setattr("game_engine.CAMPAIGN_BASE_PATH", str(tmp_path / "campaigns"))
        
        result = await game_engine.list_campaigns()
        
        assert result == []

    @pytest.mark.asyncio
    async def test_list_campaigns_sorted_newest_first(self, tmp_path, monkeypatch):
        """Tests list_campaigns: returns campaigns sorted by created_at, newest first."""
        campaigns_dir = tmp_path / "campaigns"
        campaigns_dir.mkdir(parents=True)
        
        old_campaign = {"campaign_id": "old", "created_at": "2024-01-01 10:00:00"}
        new_campaign = {"campaign_id": "new", "created_at": "2024-12-01 10:00:00"}
        
        (campaigns_dir / "old_outline.json").write_text(json.dumps(old_campaign))
        (campaigns_dir / "new_outline.json").write_text(json.dumps(new_campaign))
        monkeypatch.setattr("game_engine.CAMPAIGN_BASE_PATH", str(tmp_path / "campaigns"))
        
        result = await game_engine.list_campaigns()
        
        assert len(result) == 2
        assert result[0]["campaign_id"] == "new"
        assert result[1]["campaign_id"] == "old"

    @pytest.mark.asyncio
    async def test_list_campaigns_skips_invalid_json(self, tmp_path, monkeypatch):
        """Tests list_campaigns: skips files with invalid JSON, returns valid ones."""
        campaigns_dir = tmp_path / "campaigns"
        campaigns_dir.mkdir(parents=True)
        
        valid_campaign = {"campaign_id": "valid", "created_at": "2024-01-01"}
        (campaigns_dir / "valid_outline.json").write_text(json.dumps(valid_campaign))
        (campaigns_dir / "invalid_outline.json").write_text("not json")
        monkeypatch.setattr("game_engine.CAMPAIGN_BASE_PATH", str(tmp_path / "campaigns"))
        
        result = await game_engine.list_campaigns()
        
        assert len(result) == 1
        assert result[0]["campaign_id"] == "valid"


class TestUpdateLastPlayed:
    """Tests for update_last_played function."""

    @pytest.mark.asyncio
    async def test_update_last_played_returns_false_for_missing(self, tmp_path, monkeypatch):
        """Tests update_last_played: returns False when campaign does not exist."""
        monkeypatch.setattr("game_engine.CAMPAIGN_BASE_PATH", str(tmp_path / "campaigns"))
        
        result = await game_engine.update_last_played("nonexistent")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_update_last_played_sets_timestamp(self, tmp_path, monkeypatch):
        """Tests update_last_played: sets last_played field in campaign file."""
        campaigns_dir = tmp_path / "campaigns"
        campaigns_dir.mkdir(parents=True)
        
        campaign_data = {"campaign_id": "camp_001", "last_played": None}
        campaign_file = campaigns_dir / "camp_001_outline.json"
        campaign_file.write_text(json.dumps(campaign_data))
        monkeypatch.setattr("game_engine.CAMPAIGN_BASE_PATH", str(tmp_path / "campaigns"))
        
        result = await game_engine.update_last_played("camp_001")
        
        assert result is True
        
        updated_data = json.loads(campaign_file.read_text())
        assert updated_data["last_played"] is not None
        assert len(updated_data["last_played"]) > 0

    @pytest.mark.asyncio
    async def test_update_last_played_overwrites_previous(self, tmp_path, monkeypatch):
        """Tests update_last_played: overwrites existing last_played with new timestamp."""
        campaigns_dir = tmp_path / "campaigns"
        campaigns_dir.mkdir(parents=True)
        
        campaign_data = {"campaign_id": "camp_001", "last_played": "2020-01-01 00:00:00"}
        campaign_file = campaigns_dir / "camp_001_outline.json"
        campaign_file.write_text(json.dumps(campaign_data))
        monkeypatch.setattr("game_engine.CAMPAIGN_BASE_PATH", str(tmp_path / "campaigns"))
        
        await game_engine.update_last_played("camp_001")
        
        updated_data = json.loads(campaign_file.read_text())
        assert updated_data["last_played"] != "2020-01-01 00:00:00"
