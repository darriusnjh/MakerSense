from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class DataRepository(ABC):
    @abstractmethod
    def get_brand_profile(self, brand_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_campaign_state(self, campaign_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def write_campaign_state(self, campaign_id: str, payload: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_analytics_snapshot(self, brand_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_policy_rules(self, brand_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_memory(self, scope: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def update_memory(self, scope: str, lesson: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def append_schedule(
        self,
        campaign_id: str,
        asset_payload: dict[str, Any],
        scheduled_for: datetime,
    ) -> dict[str, Any]:
        raise NotImplementedError

