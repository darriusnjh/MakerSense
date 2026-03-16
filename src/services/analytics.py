from __future__ import annotations

from typing import Any

from src.storage.base import DataRepository


class AnalyticsService:
    def __init__(self, repository: DataRepository):
        self.repository = repository

    def get_snapshot(self, brand_id: str) -> dict[str, Any]:
        return self.repository.get_analytics_snapshot(brand_id)

    def get_trend_data(self, brand_id: str) -> dict[str, Any]:
        snapshot = self.get_snapshot(brand_id)
        return snapshot.get("trend_signals", {})

    def get_topic_clusters(self, brand_id: str) -> list[dict[str, Any]]:
        snapshot = self.get_snapshot(brand_id)
        return snapshot.get("topic_clusters", [])

    def get_visual_clusters(self, brand_id: str) -> list[dict[str, Any]]:
        snapshot = self.get_snapshot(brand_id)
        return snapshot.get("visual_clusters", [])

    def get_entity_trends(self, brand_id: str) -> list[dict[str, Any]]:
        snapshot = self.get_snapshot(brand_id)
        return snapshot.get("entity_trends", [])

    def get_comments(self, brand_id: str) -> list[dict[str, Any]]:
        snapshot = self.get_snapshot(brand_id)
        return snapshot.get("comments", [])

    def get_comment_clusters(self, brand_id: str) -> list[dict[str, Any]]:
        snapshot = self.get_snapshot(brand_id)
        return snapshot.get("comment_clusters", [])

    def get_review_summaries(self, brand_id: str) -> list[dict[str, Any]]:
        snapshot = self.get_snapshot(brand_id)
        return snapshot.get("review_summaries", [])

    def get_segment_metrics(self, brand_id: str) -> list[dict[str, Any]]:
        snapshot = self.get_snapshot(brand_id)
        return snapshot.get("segment_metrics", [])

    def get_competitor_posts(self, brand_id: str) -> list[dict[str, Any]]:
        snapshot = self.get_snapshot(brand_id)
        return snapshot.get("competitor_posts", [])

    def get_competitor_summaries(self, brand_id: str) -> list[dict[str, Any]]:
        snapshot = self.get_snapshot(brand_id)
        return snapshot.get("competitor_summaries", [])

    def get_prediction_scores(self, brand_id: str) -> dict[str, Any]:
        snapshot = self.get_snapshot(brand_id)
        return snapshot.get("prediction_scores", {})

    def get_post_data(self, brand_id: str) -> list[dict[str, Any]]:
        snapshot = self.get_snapshot(brand_id)
        return snapshot.get("published_posts", [])

    def search_similar_posts(
        self,
        brand_id: str,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        snapshot = self.get_snapshot(brand_id)
        corpus = snapshot.get("post_objects", []) + snapshot.get("competitor_posts", [])
        query_tokens = {token.strip(".,!?").lower() for token in query.split() if token}
        scored: list[tuple[int, dict[str, Any]]] = []
        for row in corpus:
            text = " ".join(
                str(row.get(field, ""))
                for field in ("caption", "hook", "theme", "offer", "summary", "topic")
            ).lower()
            row_tokens = set(text.split())
            overlap = len(query_tokens.intersection(row_tokens))
            if overlap > 0:
                scored.append((overlap, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:limit]]

