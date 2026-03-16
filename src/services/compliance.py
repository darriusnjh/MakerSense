from __future__ import annotations

from typing import Any

from src.storage.base import DataRepository


class ComplianceService:
    def __init__(self, repository: DataRepository):
        self.repository = repository

    def get_policy_rules(self, brand_id: str) -> dict[str, Any]:
        return self.repository.get_policy_rules(brand_id)

    def score_asset(self, brand_id: str, asset: dict[str, Any]) -> dict[str, Any]:
        rules = self.get_policy_rules(brand_id)
        banned_claims = [item.lower() for item in rules.get("banned_claims", [])]
        required_disclosures = [item.lower() for item in rules.get("required_disclosures", [])]
        brand_tone = [item.lower() for item in rules.get("tone_requirements", [])]

        text_blob = " ".join(
            str(asset.get(key, "")) for key in ("caption", "cta", "image_prompt")
        ).lower()

        flags: list[str] = []
        suggestions: list[str] = []
        score = 1.0

        for claim in banned_claims:
            if claim and claim in text_blob:
                flags.append(f"Contains banned claim: {claim}")
                suggestions.append(f"Remove or rephrase banned claim: {claim}")
                score -= 0.35

        for disclosure in required_disclosures:
            if disclosure and disclosure not in text_blob:
                flags.append(f"Missing disclosure: {disclosure}")
                suggestions.append(f"Add disclosure text: {disclosure}")
                score -= 0.15

        if brand_tone and not any(tone in text_blob for tone in brand_tone):
            suggestions.append("Add clearer brand tone markers from guidelines.")
            score -= 0.1

        score = max(0.0, min(1.0, score))
        if score >= 0.8:
            recommendation = "approve"
        elif score >= 0.55:
            recommendation = "revise"
        else:
            recommendation = "block"

        return {
            "asset_id": asset.get("asset_id"),
            "score": round(score, 3),
            "recommendation": recommendation,
            "flags": flags,
            "suggestions": suggestions,
        }

