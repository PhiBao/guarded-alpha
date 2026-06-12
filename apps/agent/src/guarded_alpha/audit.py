from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

from guarded_alpha.models import AgentRun, to_jsonable


class AuditLog:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, run: AgentRun) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(to_jsonable(run), sort_keys=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(payload + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def read_recent(self, limit: int = 25) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows[-limit:]

    def has_submitted_trade_on(self, target_date: date) -> bool:
        for row in self.read_recent(limit=500):
            receipt = row.get("receipt") or {}
            created_at = str(row.get("created_at", ""))
            if not receipt.get("submitted") or not created_at.startswith(target_date.isoformat()):
                continue
            return True
        return False

    def has_run_on(self, target_date: date) -> bool:
        for row in self.read_recent(limit=500):
            created_at = str(row.get("created_at", ""))
            if created_at.startswith(target_date.isoformat()):
                return True
        return False

    def find_run(self, run_id: str) -> dict[str, Any] | None:
        for row in reversed(self.read_recent(limit=1000)):
            if row.get("run_id") == run_id:
                return row
        return None
