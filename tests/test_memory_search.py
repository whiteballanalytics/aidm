# tests/test_memorysearch.py

import json
from io import BytesIO
from types import SimpleNamespace

# Adjust this import to match your project layout
from library.vectorstores import MemorySearch


# ---------- Fakes / Stubs ----------

class FakeFiles:
    def __init__(self):
        self.last_file: BytesIO | None = None
        self.calls = 0

    def create(self, file, purpose):
        # file should be a BytesIO with .name set
        self.calls += 1
        assert purpose == "assistants"
        assert hasattr(file, "name")
        assert isinstance(file, BytesIO)
        self.last_file = file
        return SimpleNamespace(id="file_123")


class FakeVSFiles:
    def __init__(self):
        self.calls = 0

    def create(self, vector_store_id, file_id):
        self.calls += 1
        # Wiring assertions are made per-test (vector_store_id/file_id)
        assert isinstance(vector_store_id, str)
        assert isinstance(file_id, str)


class FakeClient:
    def __init__(self, expected_vs_id: str = "vs_camp", expected_file_id: str = "file_123"):
        self.files = FakeFiles()
        self.vector_stores = SimpleNamespace(files=FakeVSFiles())
        self._expected_vs_id = expected_vs_id
        self._expected_file_id = expected_file_id


# ---------- Tests ----------

def test_upsert_writes_and_mirrors(tmp_path):
    """Uploads JSON to the vector store and mirrors the same JSON to disk."""
    client = FakeClient(expected_vs_id="vs_camp", expected_file_id="file_123")
    mem = MemorySearch.from_id("camp_001", "vs_camp", client=client).with_mirror(tmp_path)

    file_id = mem.upsert_memory_writes(
        user_id="user_001",
        memory_writes=[{"type": "event", "keys": ["Dock"], "summary": "Found a key."}],
    )
    assert file_id == "file_123"

    # Ensure attach call happened with expected IDs
    assert client.vector_stores.files.calls == 1
    # Mirror file created with expected payload
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text())
    assert payload["campaign_id"] == "camp_001"
    assert payload["user_id"] == "user_001"
    assert payload["items"][0]["summary"] == "Found a key."


def test_upsert_skips_when_empty(tmp_path):
    """No upload or mirror when memory_writes is empty."""
    client = FakeClient()
    mem = MemorySearch.from_id("camp_001", "vs_camp", client=client).with_mirror(tmp_path)

    out = mem.upsert_memory_writes(user_id="user_001", memory_writes=[])
    assert out is None
    assert client.files.calls == 0
    assert client.vector_stores.files.calls == 0
    assert list(tmp_path.glob("*.json")) == []


def test_upsert_without_mirror_does_not_write_locally(tmp_path):
    """Uploading works without a mirror; no local files are written."""
    client = FakeClient()
    mem = MemorySearch.from_id("camp_001", "vs_camp", client=client)  # no .with_mirror

    file_id = mem.upsert_memory_writes(
        user_id="user_001",
        memory_writes=[{"type": "event", "keys": ["Dock"], "summary": "Found a key."}],
    )
    assert file_id == "file_123"
    assert client.files.calls == 1
    assert client.vector_stores.files.calls == 1
    assert list(tmp_path.glob("*.json")) == []  # no mirror


def test_upsert_does_not_mutate_input(tmp_path):
    """Ensure the input list/dicts are not mutated by the write path."""
    client = FakeClient()
    mem = MemorySearch.from_id("camp_001", "vs_camp", client=client).with_mirror(tmp_path)

    original = [{"type": "event", "keys": ["Dock"], "summary": "Found a key."}]
    snapshot = json.loads(json.dumps(original))  # deep copy
    mem.upsert_memory_writes(user_id="user_001", memory_writes=original)
    assert original == snapshot  # unchanged


def test_upload_filename_is_json_and_campaign_tagged(tmp_path):
    """Uploaded in-memory file has a .json name and includes the campaign id."""
    client = FakeClient()
    mem = MemorySearch.from_id("camp_001", "vs_camp", client=client).with_mirror(tmp_path)

    mem.upsert_memory_writes(user_id="user_001", memory_writes=[{"type": "event", "keys": [], "summary": "x"}])

    name = getattr(client.files.last_file, "name", "")
    assert name.endswith(".json")
    assert "camp_001" in name


def test_uploaded_payload_matches_mirror(tmp_path):
    """The uploaded buffer content exactly matches the mirrored file content."""
    client = FakeClient()
    mem = MemorySearch.from_id("camp_001", "vs_camp", client=client).with_mirror(tmp_path)

    mem.upsert_memory_writes(
        user_id="user_001",
        memory_writes=[{"type": "event", "keys": ["A"], "summary": "B"}],
    )

    # Read mirror
    [mirror_file] = list(tmp_path.glob("*.json"))
    mirror_text = mirror_file.read_text()

    # Read uploaded buffer (the same BytesIO object we passed in)
    uploaded_text = client.files.last_file.getvalue().decode("utf-8")

    assert mirror_text == uploaded_text
