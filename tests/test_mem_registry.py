# tests/test_mem_registry.py

import json
from types import SimpleNamespace
from library.vectorstores import get_campaign_mem_store, MEM_REGISTRY_PATH

class FakeOpenAI:
    class vector_stores:
        @staticmethod
        def create(name: str):
            return SimpleNamespace(id="vs_test123")


def test_get_campaign_mem_store_creates_and_caches(tmp_path, monkeypatch):
    
    # point registry to tmp
    monkeypatch.setattr("library.vectorstores.MEM_REGISTRY_PATH", tmp_path/"memorystores.json")
    client = FakeOpenAI()

    # first call creates new store
    vs_id = get_campaign_mem_store(client, "camp_001")
    assert vs_id == "vs_test123"

    # second call reuses cached id
    vs_id2 = get_campaign_mem_store(client, "camp_001")
    assert vs_id2 == "vs_test123"
    saved = json.loads((tmp_path/"memorystores.json").read_text())
    assert saved["camp_001"] == "vs_test123"
