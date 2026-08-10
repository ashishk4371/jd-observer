import hashlib
import json
import uuid
from pathlib import Path
from typing import Dict, Optional, Any

CACHE_DIR = Path.home() / ".jd_analyzer_cache" / "resume_profiles"


class ResumeStore:
    """In-memory resume document store with a disk-backed profile cache.

    Resume text/metadata stay in-memory (per resume_id, per server run), but
    the structured profile extracted from that text is cached to disk keyed
    by a content hash, so re-uploading the same resume — even after a
    restart — reuses the previously extracted profile instead of paying for
    another LLM call.
    """

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def add(self, content: str, filename: str = "resume.txt") -> str:
        rid = str(uuid.uuid4())
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        self._store[rid] = {
            "content": content,
            "filename": filename,
            "char_count": len(content),
            "content_hash": content_hash,
            "profile": self._load_cached_profile(content_hash),
        }
        return rid

    def get(self, rid: str) -> Optional[str]:
        data = self._store.get(rid)
        if data:
            return data["content"]
        return None

    def get_info(self, rid: str) -> Optional[Dict[str, Any]]:
        return self._store.get(rid)

    def get_profile(self, rid: str) -> Optional[dict]:
        data = self._store.get(rid)
        return data.get("profile") if data else None

    def set_profile(self, rid: str, profile: dict) -> None:
        data = self._store.get(rid)
        if not data:
            return
        data["profile"] = profile
        self._save_cached_profile(data["content_hash"], profile)

    def _load_cached_profile(self, content_hash: str) -> Optional[dict]:
        f = CACHE_DIR / f"{content_hash}.json"
        if f.exists():
            try:
                return json.loads(f.read_text())
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def _save_cached_profile(self, content_hash: str, profile: dict) -> None:
        f = CACHE_DIR / f"{content_hash}.json"
        try:
            f.write_text(json.dumps(profile))
        except OSError:
            pass


resume_store = ResumeStore()
