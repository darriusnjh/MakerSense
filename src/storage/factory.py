from __future__ import annotations

from src.config import Settings

from .base import DataRepository
from .json_store import JsonRepository


def build_repository(settings: Settings) -> DataRepository:
    if settings.data_backend == "postgres":
        if not settings.database_url:
            raise ValueError("DATABASE_URL is required when DATA_BACKEND=postgres")
        from .postgres_store import PostgresRepository

        return PostgresRepository(settings.database_url)
    return JsonRepository(settings.json_data_dir)
