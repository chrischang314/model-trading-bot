from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4


class IngestRunStore:
    """Bounded local history for market-data ingestion attempts."""

    def __init__(self, path: Path, max_runs: int = 100) -> None:
        self.path = path
        self.max_runs = max(1, max_runs)
        self._lock = Lock()

    def record(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        entry = {
            **payload,
            "id": payload.get("id") or uuid4().hex,
            "created_at": payload.get("created_at") or now,
        }
        with self._lock:
            runs = [entry, *self._read_unlocked()]
            runs = runs[: self.max_runs]
            self._write_unlocked(runs)
        return entry

    def list_runs(self, limit: int = 25) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 50))
        with self._lock:
            return self._read_unlocked()[:safe_limit]

    def latest(self) -> dict[str, Any] | None:
        runs = self.list_runs(limit=1)
        return runs[0] if runs else None

    def _read_unlocked(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(raw, list):
            return []
        return [item for item in raw if isinstance(item, dict)]

    def _write_unlocked(self, runs: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(f"{self.path.suffix}.{uuid4().hex}.tmp")
        tmp_path.write_text(json.dumps(runs, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp_path, self.path)
