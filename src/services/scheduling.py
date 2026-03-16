from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from src.storage.base import DataRepository


class SchedulingService:
    def __init__(self, repository: DataRepository):
        self.repository = repository

    def schedule_assets(
        self,
        campaign_id: str,
        assets: list[dict[str, Any]],
        start_at: datetime | None = None,
    ) -> list[dict[str, Any]]:
        if start_at is None:
            start_at = datetime.now(UTC) + timedelta(hours=4)

        scheduled: list[dict[str, Any]] = []
        for idx, asset in enumerate(assets):
            publish_time = start_at + timedelta(hours=12 * idx)
            scheduled.append(
                self.repository.append_schedule(
                    campaign_id=campaign_id,
                    asset_payload=asset,
                    scheduled_for=publish_time,
                )
            )
        return scheduled

