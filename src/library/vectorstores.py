import json, io, time, hashlib
from pathlib import Path
from pydantic import BaseModel, PrivateAttr
from agents import FileSearchTool
from openai import OpenAI
from typing import Optional, Any

CONFIG_PATH = Path("config/vectorstores.json")
MEM_REGISTRY_PATH = Path("config/memorystores.json")

def add_to_vector_store(category: str, store_name: str, id: str):

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text())
        except json.JSONDecodeError:
            data = {}
            
    data.setdefault(category, {})
    data[category][store_name] = {"vector_store_id": id}

    CONFIG_PATH.write_text(json.dumps(data, indent=2))

class LoreSearch(BaseModel):
    """
    Thin facade that: 
      1) reads your config file,
      2) exposes a preconfigured FileSearchTool for the DM agent,
      3) (optionally) lets you tune max results / filters.
    """
    vector_store_id: str
    max_num_results: int = 6
    include_search_results: bool = True  # let the model see snippets it retrieved

    @classmethod
    def set_lore(cls, collection: str, domain: str = "world") -> "LoreSearch":
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        try:
            vs_id = data[domain][collection]["vector_store_id"]
        except KeyError as e:
            raise KeyError(
                f"Could not find vector store id at path [{domain}][{collection}][vector_store_id] "
                f"in {CONFIG_PATH}"
            ) from e
        return cls(vector_store_id=vs_id)

    def as_tool(self) -> FileSearchTool:
        """
        Return an Agents SDK FileSearchTool configured to query *this* vector store.
        The agent will call this tool automatically when it needs canon.
        """
        return FileSearchTool(
            vector_store_ids=[self.vector_store_id],
            max_num_results=self.max_num_results,
            include_search_results=self.include_search_results,
        )

def ensure_campaign_mem_store(client: OpenAI, campaign_id: str) -> str:
    """Create or load the vector store id for this campaign and cache it locally."""
    if MEM_REGISTRY_PATH.exists():
        try:
            reg = json.loads(MEM_REGISTRY_PATH.read_text(encoding="utf-8"))
        except Exception:
            reg = {}
    else:
        reg = {}

    if campaign_id in reg:
        return reg[campaign_id]

    vs = client.vector_stores.create(name=f"mem_{campaign_id}")
    reg[campaign_id] = vs.id
    MEM_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEM_REGISTRY_PATH.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
    return vs.id
    
class MemorySearch(BaseModel):
    """
    Per-campaign long-term memory:
      1) ensures/loads the campaign vector store id,
      2) exposes a FileSearchTool for the DM agent,
      3) can append 'memory_writes' cheaply (upload+attach JSON).
    """
    campaign_id: str
    vector_store_id: str
    max_num_results: int = 6
    include_search_results: bool = True  # let the model see snippets it retrieved
    
    _client: OpenAI = PrivateAttr(default_factory=OpenAI)  # injected client
    _mirror_dir: Optional[Path] = PrivateAttr(default=None)  # optional local mirror for files

    # --- constructors ---
    @classmethod
    def from_id(cls, campaign_id: str, vector_store_id: str, client: Optional[OpenAI] = None) -> "MemorySearch":
        inst = cls(campaign_id=campaign_id, vector_store_id=vector_store_id)
        inst._client = client or OpenAI()
        return inst
    
    # --- tool exposure ---
    def as_tool(self) -> FileSearchTool:
        """
        Return an Agents SDK FileSearchTool configured to query this campaign's memory store.
        """
        return FileSearchTool(
            vector_store_ids=[self.vector_store_id],
            max_num_results=self.max_num_results,
            include_search_results=self.include_search_results,
        )

    # --- append memory writes (no LLM tokens) ---
    def with_mirror(self, path: str | Path) -> "MemorySearch":
        """Enable local mirroring so you can read memories later."""
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        self._mirror_dir = p
        return self
    
    def upsert_memory_writes(self, user_id: str, memory_writes: list[dict]) -> Optional[str]:
        if not memory_writes:
            return None

        payload = {
            "campaign_id": self.campaign_id,
            "user_id": user_id,
            "items": memory_writes,
            "ts": int(time.time()),
        }
        raw = json.dumps(payload, ensure_ascii=False, indent=2)

        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
        fname = f"mem_{self.campaign_id}_{int(time.time())}_{digest}.json"
        buf = io.BytesIO(raw.encode("utf-8"))
        buf.name = fname

        # Upload to vector store (for retrieval by the model)
        f = self._client.files.create(file=buf, purpose="assistants")
        self._client.vector_stores.files.create(vector_store_id=self.vector_store_id, file_id=f.id)

        # Mirror locally so you can read later
        if self._mirror_dir:
            (self._mirror_dir / fname).write_text(raw, encoding="utf-8")

        return f.id

    # ---- Read from the local mirror (not from OpenAI) ----
    def read_mirror_files(self, parse_json: bool = True) -> list[dict[str, Any]]:
        """
        Return a list of {path, text, json?} from the local mirror directory.
        """
        if not self._mirror_dir or not self._mirror_dir.exists():
            return []
        out: list[dict[str, Any]] = []
        for p in sorted(self._mirror_dir.glob("*.json")):
            text = p.read_text(encoding="utf-8")
            item: dict[str, Any] = {"path": str(p), "text": text}
            if parse_json:
                try:
                    item["json"] = json.loads(text)
                except Exception:
                    pass
            out.append(item)
        return out