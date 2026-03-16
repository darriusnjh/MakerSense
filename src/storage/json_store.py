from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .base import DataRepository


class JsonRepository(DataRepository):
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _read(self, filename: str) -> dict[str, Any]:
        path = self.data_dir / filename
        if not path.exists():
            return {}
        # Accept files with or without UTF-8 BOM (common when edited via PowerShell).
        raw = path.read_text(encoding="utf-8-sig")
        if not raw.strip():
            return {}
        return json.loads(raw)

    def _write(self, filename: str, payload: dict[str, Any]) -> None:
        path = self.data_dir / filename
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def get_brand_profile(self, brand_id: str) -> dict[str, Any]:
        data = self._read("brand_profiles.json")
        return data.get(brand_id, {})

    def get_campaign_state(self, campaign_id: str) -> dict[str, Any]:
        data = self._read("campaign_states.json")
        return data.get(campaign_id, {})

    def write_campaign_state(self, campaign_id: str, payload: dict[str, Any]) -> None:
        data = self._read("campaign_states.json")
        data[campaign_id] = payload
        self._write("campaign_states.json", data)

    def get_analytics_snapshot(self, brand_id: str) -> dict[str, Any]:
        data = self._read("analytics_snapshots.json")
        return data.get(brand_id, {})

    def get_policy_rules(self, brand_id: str) -> dict[str, Any]:
        data = self._read("policy_rules.json")
        return data.get(brand_id, {})

    def get_memory(self, scope: str) -> dict[str, Any]:
        data = self._read("memories.json")
        return data.get(scope, {"scope": scope, "lessons": []})

    def update_memory(self, scope: str, lesson: dict[str, Any]) -> dict[str, Any]:
        data = self._read("memories.json")
        memory = data.setdefault(scope, {"scope": scope, "lessons": []})
        memory.setdefault("lessons", []).append(lesson)
        data[scope] = memory
        self._write("memories.json", data)
        return memory

    def append_schedule(
        self,
        campaign_id: str,
        asset_payload: dict[str, Any],
        scheduled_for: datetime,
    ) -> dict[str, Any]:
        data = self._read("schedule.json")
        items = data.setdefault(campaign_id, [])
        record = {
            "campaign_id": campaign_id,
            "asset_id": asset_payload.get("asset_id"),
            "channel": asset_payload.get("channel"),
            "scheduled_for": scheduled_for.isoformat(),
            "payload": asset_payload,
        }
        items.append(record)
        data[campaign_id] = items
        self._write("schedule.json", data)
        return record
