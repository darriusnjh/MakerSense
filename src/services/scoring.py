from __future__ import annotations

from typing import Any


class ScoringService:
    def __init__(self, analytics_service):
        self.analytics_service = analytics_service

    @staticmethod
    def _tokenize(*values: str) -> set[str]:
        tokens: set[str] = set()
        for value in values:
            if not isinstance(value, str):
                value = str(value)
            for token in value.lower().replace("/", " ").split():
                token = token.strip(".,!?()[]{}:\"'")
                if token:
                    tokens.add(token)
        return tokens

    @staticmethod
    def _safe_dict(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _safe_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_segment_key(value: Any) -> str:
        if isinstance(value, str):
            text = value.strip()
            return text or "all"
        return "all"

    def _match_topic(
        self,
        candidate: dict[str, Any],
        topic_clusters: list[dict[str, Any]],
    ) -> dict[str, Any]:
        candidate_tokens = self._tokenize(
            candidate.get("caption", ""),
            candidate.get("topic_hint", ""),
            candidate.get("pillar", ""),
        )
        best_cluster = topic_clusters[0] if topic_clusters else {"topic_id": "unknown", "keywords": []}
        best_score = -1
        for cluster in topic_clusters:
            keywords = set(cluster.get("keywords", []))
            overlap = len(candidate_tokens.intersection(keywords))
            if overlap > best_score:
                best_score = overlap
                best_cluster = cluster
        return best_cluster

    def _match_visual(
        self,
        candidate: dict[str, Any],
        visual_clusters: list[dict[str, Any]],
    ) -> dict[str, Any]:
        candidate_tokens = self._tokenize(
            candidate.get("image_prompt", ""),
            candidate.get("visual_hint", ""),
            candidate.get("caption", ""),
        )
        best_cluster = (
            visual_clusters[0] if visual_clusters else {"visual_cluster_id": "unknown", "motifs": []}
        )
        best_score = -1
        for cluster in visual_clusters:
            motifs = set(cluster.get("motifs", []))
            overlap = len(candidate_tokens.intersection(motifs))
            if overlap > best_score:
                best_score = overlap
                best_cluster = cluster
        return best_cluster

    def score_candidate(self, brand_id: str, candidate: dict[str, Any]) -> dict[str, Any]:
        snapshot = self._safe_dict(self.analytics_service.get_snapshot(brand_id))
        topic_clusters = snapshot.get("topic_clusters", [])
        visual_clusters = snapshot.get("visual_clusters", [])
        prediction_scores = self._safe_dict(snapshot.get("prediction_scores", {}))

        matched_topic = self._match_topic(candidate, topic_clusters)
        matched_visual = self._match_visual(candidate, visual_clusters)

        topic_cluster_ctr = self._safe_dict(prediction_scores.get("topic_cluster_ctr", {}))
        visual_cluster_ctr = self._safe_dict(prediction_scores.get("visual_cluster_ctr", {}))
        baseline_segment_bonus = self._safe_dict(prediction_scores.get("baseline_segment_bonus", {}))

        topic_ctr_raw = topic_cluster_ctr.get(matched_topic.get("topic_id", ""), 0.015)
        visual_ctr_raw = visual_cluster_ctr.get(matched_visual.get("visual_cluster_id", ""), 0.015)
        segment_key = self._safe_segment_key(candidate.get("target_segment", "all"))
        segment_bonus_raw = baseline_segment_bonus.get(segment_key, baseline_segment_bonus.get("all", 0.0))

        topic_ctr = self._safe_float(topic_ctr_raw, 0.015)
        visual_ctr = self._safe_float(visual_ctr_raw, 0.015)
        segment_bonus = self._safe_float(segment_bonus_raw, 0.0)

        predicted_ctr = round((0.55 * topic_ctr) + (0.35 * visual_ctr) + (0.10 * segment_bonus), 4)
        score = min(1.0, round(predicted_ctr / 0.08, 3))

        return {
            "asset_id": candidate.get("asset_id"),
            "topic_cluster_id": matched_topic.get("topic_id", "unknown"),
            "visual_cluster_id": matched_visual.get("visual_cluster_id", "unknown"),
            "predicted_ctr": predicted_ctr,
            "score": score,
            "rationale": (
                f"Matched topic {matched_topic.get('label', 'unknown')} and visual "
                f"{matched_visual.get('style', 'unknown')}."
            ),
        }

    def rank_candidates(
        self,
        brand_id: str,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        scored = []
        for candidate in candidates:
            result = dict(candidate)
            result["ranking"] = self.score_candidate(brand_id, candidate)
            scored.append(result)
        scored.sort(
            key=lambda row: (row["ranking"]["score"], row["ranking"]["predicted_ctr"]),
            reverse=True,
        )
        return scored
