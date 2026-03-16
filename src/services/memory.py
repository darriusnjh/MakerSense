from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.storage.base import DataRepository


class MemoryService:
    def __init__(self, repository: DataRepository):
        self.repository = repository

    def get_memory(self, scope: str) -> dict[str, Any]:
        return self.repository.get_memory(scope)

    def update_memory(
        self,
        scope: str,
        lesson: dict[str, Any],
        confidence: float,
        approved_by: str = "orchestrator",
    ) -> dict[str, Any]:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "approved_by": approved_by,
            "confidence": confidence,
            **lesson,
        }
        return self.repository.update_memory(scope, payload)

