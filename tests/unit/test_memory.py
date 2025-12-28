# tests/unit/test_memory.py
"""Unit tests for memory/vectorstore functions: get_campaign_mem_store, MemorySearch.upsert_memory_writes."""

import json
from io import BytesIO
from types import SimpleNamespace

from library.vectorstores import get_campaign_mem_store, MemorySearch


class FakeOpenAI:
    """Fake OpenAI client for testing get_campaign_mem_store."""
    class vector_stores:
        @staticmethod
        def create(name: str):
            return SimpleNamespace(id="vs_test123")


class FakeFiles:
    """Fake files API for testing upsert_memory_writes."""
    def __init__(self):
        self.last_file: BytesIO | None = None
        self.calls = 0

    def create(self, file, purpose):
        self.calls += 1
        assert purpose == "assistants"
        assert hasattr(file, "name")
        assert isinstance(file, BytesIO)
        self.last_file = file
        return SimpleNamespace(id="file_123")


class FakeVSFiles:
    """Fake vector_stores.files API for testing upsert_memory_writes."""
    def __init__(self):
        self.calls = 0

    def create(self, vector_store_id, file_id):
        self.calls += 1
        assert isinstance(vector_store_id, str)
        assert isinstance(file_id, str)


class FakeClient:
    """Fake OpenAI client for testing MemorySearch."""
    def __init__(self, expected_vs_id: str = "vs_camp", expected_file_id: str = "file_123"):
        self.files = FakeFiles()
        self.vector_stores = SimpleNamespace(files=FakeVSFiles())
        self._expected_vs_id = expected_vs_id
        self._expected_file_id = expected_file_id


def test_get_campaign_mem_store_creates_and_caches(tmp_path, monkeypatch):
    """Tests get_campaign_mem_store: creates new store on first call, caches on subsequent calls."""
    monkeypatch.setattr("library.vectorstores.MEM_REGISTRY_PATH", tmp_path / "memorystores.json")
    client = FakeOpenAI()

    vs_id = get_campaign_mem_store(client, "camp_001")
    assert vs_id == "vs_test123"

    vs_id2 = get_campaign_mem_store(client, "camp_001")
    assert vs_id2 == "vs_test123"
    
    saved = json.loads((tmp_path / "memorystores.json").read_text())
    assert saved["camp_001"] == "vs_test123"


def test_upsert_writes_and_mirrors(tmp_path):
    """Tests upsert_memory_writes: uploads JSON to vector store and mirrors to disk."""
    client = FakeClient(expected_vs_id="vs_camp", expected_file_id="file_123")
    mem = MemorySearch.from_id("camp_001", "vs_camp", client=client).with_mirror(tmp_path)

    file_id = mem.upsert_memory_writes(
        user_id="user_001",
        memory_writes=[{"type": "event", "keys": ["Dock"], "summary": "Found a key."}],
    )
    assert file_id == "file_123"

    assert client.vector_stores.files.calls == 1
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text())
    assert payload["campaign_id"] == "camp_001"
    assert payload["user_id"] == "user_001"
    assert payload["items"][0]["summary"] == "Found a key."


def test_upsert_skips_when_empty(tmp_path):
    """Tests upsert_memory_writes: no upload or mirror when memory_writes is empty."""
    client = FakeClient()
    mem = MemorySearch.from_id("camp_001", "vs_camp", client=client).with_mirror(tmp_path)

    out = mem.upsert_memory_writes(user_id="user_001", memory_writes=[])
    assert out is None
    assert client.files.calls == 0
    assert client.vector_stores.files.calls == 0
    assert list(tmp_path.glob("*.json")) == []


def test_upsert_without_mirror_does_not_write_locally(tmp_path):
    """Tests upsert_memory_writes: uploads work without mirror; no local files written."""
    client = FakeClient()
    mem = MemorySearch.from_id("camp_001", "vs_camp", client=client)

    file_id = mem.upsert_memory_writes(
        user_id="user_001",
        memory_writes=[{"type": "event", "keys": ["Dock"], "summary": "Found a key."}],
    )
    assert file_id == "file_123"
    assert client.files.calls == 1
    assert client.vector_stores.files.calls == 1
    assert list(tmp_path.glob("*.json")) == []


def test_upsert_does_not_mutate_input(tmp_path):
    """Tests upsert_memory_writes: input list/dicts are not mutated by write path."""
    client = FakeClient()
    mem = MemorySearch.from_id("camp_001", "vs_camp", client=client).with_mirror(tmp_path)

    original = [{"type": "event", "keys": ["Dock"], "summary": "Found a key."}]
    snapshot = json.loads(json.dumps(original))
    mem.upsert_memory_writes(user_id="user_001", memory_writes=original)
    assert original == snapshot


def test_upload_filename_is_json_and_campaign_tagged(tmp_path):
    """Tests upsert_memory_writes: uploaded file has .json extension and includes campaign id."""
    client = FakeClient()
    mem = MemorySearch.from_id("camp_001", "vs_camp", client=client).with_mirror(tmp_path)

    mem.upsert_memory_writes(user_id="user_001", memory_writes=[{"type": "event", "keys": [], "summary": "x"}])

    name = getattr(client.files.last_file, "name", "")
    assert name.endswith(".json")
    assert "camp_001" in name


def test_uploaded_payload_matches_mirror(tmp_path):
    """Tests upsert_memory_writes: uploaded buffer content matches mirrored file content."""
    client = FakeClient()
    mem = MemorySearch.from_id("camp_001", "vs_camp", client=client).with_mirror(tmp_path)

    mem.upsert_memory_writes(
        user_id="user_001",
        memory_writes=[{"type": "event", "keys": ["A"], "summary": "B"}],
    )

    [mirror_file] = list(tmp_path.glob("*.json"))
    mirror_text = mirror_file.read_text()

    uploaded_text = client.files.last_file.getvalue().decode("utf-8")

    assert mirror_text == uploaded_text
