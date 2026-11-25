"""In-memory API store used when Supabase/PostgreSQL is not configured."""
from __future__ import annotations

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
            item_key = str(payload.get(key) or uuid4())
            existing = target.get(item_key, {}) if isinstance(target, dict) else {}
            item = {**existing, **payload}
            item.setdefault(key, item_key)
            item.setdefault("created_at", self.now())
            item["updated_at"] = self.now()
            if not isinstance(target, dict):
                raise TypeError(f"Table {table} does not support keyed upsert")
            target[str(item[key])] = item
            return item

    def delete(self, table: str, key: str, value: Any) -> bool:
        with self.lock:
            target = getattr(self, table)
            if not isinstance(target, dict):
                raise TypeError(f"Table {table} does not support keyed deletion")
            if str(value) in target:
                del target[str(value)]
                return True
            for item_key, item in list(target.items()):
                if item.get(key) == value:
                    del target[item_key]
                    return True
        return False

    def append(self, table: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            item = dict(payload)
            item.setdefault("id", str(uuid4()))
            item.setdefault("created_at", self.now())
            target = getattr(self, table)
            if not isinstance(target, list):
                raise TypeError(f"Table {table} does not support append")
            target.append(item)
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
