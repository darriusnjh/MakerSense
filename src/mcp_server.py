from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from mcp.server.fastmcp import FastMCP

from src.config import get_settings
from src.schemas import CandidateAsset
from src.services import build_services
from src.storage import build_repository

settings = get_settings()
repository = build_repository(settings)
services = build_services(settings, repository)

mcp = FastMCP("social-marketing-tools")


@mcp.tool()
def get_analytics_snapshot(brand_id: str = settings.default_brand_id) -> dict[str, Any]:
    return services.analytics.get_snapshot(brand_id)


@mcp.tool()
def assign_task(agent_name: str, task: str, priority: str = "medium") -> dict[str, Any]:
    return {
        "agent_name": agent_name,
        "task": task,
        "priority": priority,
        "status": "assigned",
    }


@mcp.tool()
def read_campaign_state(campaign_id: str = settings.default_campaign_id) -> dict[str, Any]:
    return services.repository.get_campaign_state(campaign_id)


@mcp.tool()
def write_campaign_state(
    campaign_id: str,
    status: str,
    objective: str = "",
    channels_csv: str = "",
    kpis_csv: str = "",
) -> dict[str, Any]:
    current = services.repository.get_campaign_state(campaign_id)
    updated = dict(current)
    updated["campaign_id"] = campaign_id
    updated["status"] = status
    if objective:
        updated["objective"] = objective
    if channels_csv:
        updated["channels"] = [part.strip() for part in channels_csv.split(",") if part.strip()]
    if kpis_csv:
        updated["kpis"] = [part.strip() for part in kpis_csv.split(",") if part.strip()]
    services.repository.write_campaign_state(campaign_id, updated)
    return updated


@mcp.tool()
def get_trend_data(brand_id: str = settings.default_brand_id) -> dict[str, Any]:
    return services.analytics.get_trend_data(brand_id)


@mcp.tool()
def web_search(
    query: str,
    max_results: int = 5,
) -> dict[str, Any]:
    return services.web_search.search(query=query, max_results=max_results)


@mcp.tool()
def get_topic_clusters(brand_id: str = settings.default_brand_id) -> list[dict[str, Any]]:
    return services.analytics.get_topic_clusters(brand_id)


@mcp.tool()
def get_visual_clusters(brand_id: str = settings.default_brand_id) -> list[dict[str, Any]]:
    return services.analytics.get_visual_clusters(brand_id)


@mcp.tool()
def get_entity_trends(brand_id: str = settings.default_brand_id) -> list[dict[str, Any]]:
    return services.analytics.get_entity_trends(brand_id)


@mcp.tool()
def get_comments(brand_id: str = settings.default_brand_id) -> list[dict[str, Any]]:
    return services.analytics.get_comments(brand_id)


@mcp.tool()
def get_comment_clusters(brand_id: str = settings.default_brand_id) -> list[dict[str, Any]]:
    return services.analytics.get_comment_clusters(brand_id)


@mcp.tool()
def get_review_summaries(brand_id: str = settings.default_brand_id) -> list[dict[str, Any]]:
    return services.analytics.get_review_summaries(brand_id)


@mcp.tool()
def get_segment_metrics(brand_id: str = settings.default_brand_id) -> list[dict[str, Any]]:
    return services.analytics.get_segment_metrics(brand_id)


@mcp.tool()
def get_competitor_posts(brand_id: str = settings.default_brand_id) -> list[dict[str, Any]]:
    return services.analytics.get_competitor_posts(brand_id)


@mcp.tool()
def get_competitor_summaries(brand_id: str = settings.default_brand_id) -> list[dict[str, Any]]:
    return services.analytics.get_competitor_summaries(brand_id)


@mcp.tool()
def search_similar_posts(
    query: str,
    brand_id: str = settings.default_brand_id,
    limit: int = 5,
) -> list[dict[str, Any]]:
    return services.analytics.search_similar_posts(brand_id=brand_id, query=query, limit=limit)


@mcp.tool()
def get_prediction_scores(brand_id: str = settings.default_brand_id) -> dict[str, Any]:
    return services.analytics.get_prediction_scores(brand_id)


@mcp.tool()
def get_brand_guidelines(brand_id: str = settings.default_brand_id) -> dict[str, Any]:
    profile = services.repository.get_brand_profile(brand_id)
    return {
        "brand_name": profile.get("brand_name"),
        "voice": profile.get("voice"),
        "guidelines": profile.get("guidelines", {}),
    }


@mcp.tool()
def get_brand_constraints(brand_id: str = settings.default_brand_id) -> dict[str, Any]:
    return services.compliance.get_policy_rules(brand_id)


@mcp.tool()
def get_memory(scope: str = "shared") -> dict[str, Any]:
    return services.memory.get_memory(scope)


@mcp.tool()
def update_memory(
    scope: str,
    lesson: str,
    confidence: float = 0.8,
) -> dict[str, Any]:
    return services.memory.update_memory(
        scope=scope,
        lesson={"lesson": lesson},
        confidence=confidence,
    )


@mcp.tool()
def approve_memory_write(
    scope: str,
    lesson: str,
    confidence: float,
    approved: bool = True,
) -> dict[str, Any]:
    if not approved:
        return {
            "updated": False,
            "reason": "Approval denied by orchestrator gate.",
            "scope": scope,
        }
    updated = services.memory.update_memory(
        scope=scope,
        lesson={"lesson": lesson},
        confidence=confidence,
    )
    return {"updated": True, "scope": scope, "memory": updated}


@mcp.tool()
def score_candidate_post(
    asset_id: str,
    pillar: str,
    channel: str,
    caption: str,
    image_prompt: str,
    cta: str,
    topic_hint: str = "",
    visual_hint: str = "",
    target_segment: str = "all",
    brand_id: str = settings.default_brand_id,
) -> dict[str, Any]:
    candidate = CandidateAsset(
        asset_id=asset_id,
        pillar=pillar,
        channel=channel,
        caption=caption,
        image_prompt=image_prompt,
        cta=cta,
        topic_hint=topic_hint or None,
        visual_hint=visual_hint or None,
    ).model_dump()
    candidate["target_segment"] = target_segment
    return services.scoring.score_candidate(brand_id=brand_id, candidate=candidate)


@mcp.tool()
def score_compliance(
    asset_id: str,
    caption: str,
    cta: str,
    image_prompt: str = "",
    pillar: str = "",
    channel: str = "",
    brand_id: str = settings.default_brand_id,
) -> dict[str, Any]:
    asset = {
        "asset_id": asset_id,
        "caption": caption,
        "cta": cta,
        "image_prompt": image_prompt,
        "pillar": pillar,
        "channel": channel,
    }
    return services.compliance.score_asset(brand_id=brand_id, asset=asset)


@mcp.tool()
def schedule_post(
    campaign_id: str,
    asset_id: str,
    pillar: str,
    channel: str,
    caption: str,
    image_prompt: str,
    cta: str,
    topic_hint: str = "",
    visual_hint: str = "",
    target_segment: str = "all",
    offset_hours: int = 4,
) -> dict[str, Any]:
    asset = CandidateAsset(
        asset_id=asset_id,
        pillar=pillar,
        channel=channel,
        caption=caption,
        image_prompt=image_prompt,
        cta=cta,
        topic_hint=topic_hint or None,
        visual_hint=visual_hint or None,
    ).model_dump()
    asset["target_segment"] = target_segment
    start = datetime.now(UTC) + timedelta(hours=max(0, offset_hours))
    scheduled = services.scheduling.schedule_assets(campaign_id=campaign_id, assets=[asset], start_at=start)
    return scheduled[0] if scheduled else {}


if __name__ == "__main__":
    mcp.run(transport="stdio")
