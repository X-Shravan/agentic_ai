"""In-memory API store used when Supabase/PostgreSQL is not configured."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List
from uuid import uuid4


class EnterpriseStore:
    def __init__(self):
        self.lock = Lock()
        self.exam_sessions: Dict[str, Dict[str, Any]] = {}
        self.camera_streams: Dict[str, Dict[str, Any]] = {}
        self.students: Dict[str, Dict[str, Any]] = {}
        self.alerts: Dict[str, Dict[str, Any]] = {}
        self.risk_scores: List[Dict[str, Any]] = []
        self.evidence: Dict[str, Dict[str, Any]] = {}
        self.reports: Dict[str, Dict[str, Any]] = {}
        self.behavior_history: List[Dict[str, Any]] = []

    def now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def upsert(self, table: str, key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            target = getattr(self, table)
            item = dict(payload)
            item.setdefault(key, payload.get(key) or str(uuid4()))
            item.setdefault("created_at", self.now())
            item["updated_at"] = self.now()
            target[str(item[key])] = item
            return item

    def append(self, table: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            item = dict(payload)
            item.setdefault("id", str(uuid4()))
            item.setdefault("created_at", self.now())
            getattr(self, table).append(item)
            return item

    def list(self, table: str, **filters: Any) -> List[Dict[str, Any]]:
        with self.lock:
            data = getattr(self, table)
            values = list(data.values()) if isinstance(data, dict) else list(data)
        for key, value in filters.items():
            if value is not None:
                values = [item for item in values if item.get(key) == value]
        return values


store = EnterpriseStore()
