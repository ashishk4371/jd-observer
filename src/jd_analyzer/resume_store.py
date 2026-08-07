import uuid
from typing import Dict, Optional, Any

class ResumeStore:
    """In-memory resume document store."""
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    def add(self, content: str, filename: str = "resume.txt") -> str:
        rid = str(uuid.uuid4())
        self._store[rid] = {
            "content": content,
            "filename": filename,
            "char_count": len(content)
        }
        return rid

    def get(self, rid: str) -> Optional[str]:
        data = self._store.get(rid)
        if data:
            return data["content"]
        return None

    def get_info(self, rid: str) -> Optional[Dict[str, Any]]:
        return self._store.get(rid)

resume_store = ResumeStore()