from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Integer, JSON, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .base import DataRepository


class Base(DeclarativeBase):
    pass


class BrandProfileRow(Base):
    __tablename__ = "brand_profiles"

    brand_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class CampaignStateRow(Base):
    __tablename__ = "campaign_states"

    campaign_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class AnalyticsSnapshotRow(Base):
    __tablename__ = "analytics_snapshots"

    brand_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class PolicyRuleRow(Base):
    __tablename__ = "policy_rules"

    brand_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class MemoryRow(Base):
    __tablename__ = "memories"

    scope: Mapped[str] = mapped_column(String(128), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ScheduleRow(Base):
    __tablename__ = "scheduled_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    asset_id: Mapped[str] = mapped_column(String(128), nullable=True)
    channel: Mapped[str] = mapped_column(String(64), nullable=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class PostgresRepository(DataRepository):
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url, future=True)
        Base.metadata.create_all(self.engine)

    def _read_payload(self, model: type[Base], key_name: str, key_value: str) -> dict[str, Any]:
        with Session(self.engine) as session:
            stmt = select(model).where(getattr(model, key_name) == key_value)
            row = session.scalar(stmt)
            return dict(row.payload) if row else {}

    def _upsert_payload(
        self, model: type[Base], key_name: str, key_value: str, payload: dict[str, Any]
    ) -> None:
        with Session(self.engine) as session:
            row = session.scalar(select(model).where(getattr(model, key_name) == key_value))
            if row is None:
                row = model(**{key_name: key_value, "payload": payload})
                session.add(row)
            else:
                row.payload = payload
                if hasattr(row, "updated_at"):
                    row.updated_at = datetime.now(UTC)
            session.commit()

    def get_brand_profile(self, brand_id: str) -> dict[str, Any]:
        return self._read_payload(BrandProfileRow, "brand_id", brand_id)

    def get_campaign_state(self, campaign_id: str) -> dict[str, Any]:
        return self._read_payload(CampaignStateRow, "campaign_id", campaign_id)

    def write_campaign_state(self, campaign_id: str, payload: dict[str, Any]) -> None:
        self._upsert_payload(CampaignStateRow, "campaign_id", campaign_id, payload)

    def get_analytics_snapshot(self, brand_id: str) -> dict[str, Any]:
        return self._read_payload(AnalyticsSnapshotRow, "brand_id", brand_id)

    def get_policy_rules(self, brand_id: str) -> dict[str, Any]:
        return self._read_payload(PolicyRuleRow, "brand_id", brand_id)

    def get_memory(self, scope: str) -> dict[str, Any]:
        payload = self._read_payload(MemoryRow, "scope", scope)
        return payload or {"scope": scope, "lessons": []}

    def update_memory(self, scope: str, lesson: dict[str, Any]) -> dict[str, Any]:
        with Session(self.engine) as session:
            row = session.scalar(select(MemoryRow).where(MemoryRow.scope == scope))
            if row is None:
                payload = {"scope": scope, "lessons": [lesson]}
                row = MemoryRow(scope=scope, payload=payload)
                session.add(row)
            else:
                payload = dict(row.payload)
                payload.setdefault("scope", scope)
                payload.setdefault("lessons", []).append(lesson)
                row.payload = payload
            session.commit()
            return dict(row.payload)

    def append_schedule(
        self,
        campaign_id: str,
        asset_payload: dict[str, Any],
        scheduled_for: datetime,
    ) -> dict[str, Any]:
        with Session(self.engine) as session:
            row = ScheduleRow(
                campaign_id=campaign_id,
                asset_id=asset_payload.get("asset_id"),
                channel=asset_payload.get("channel"),
                scheduled_for=scheduled_for,
                payload=asset_payload,
            )
            session.add(row)
            session.commit()
            return {
                "campaign_id": campaign_id,
                "asset_id": row.asset_id,
                "channel": row.channel,
                "scheduled_for": row.scheduled_for.isoformat(),
                "payload": row.payload,
            }

