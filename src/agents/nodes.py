from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any

from src.agents.llm_client import LLMClient
from src.agents.prompts import (
    AUDIENCE_AGENT_PROMPT,
    COMPETITOR_AGENT_PROMPT,
    COMPLIANCE_AGENT_PROMPT,
    CREATIVE_AGENT_PROMPT,
    CRITIC_AGENT_PROMPT,
    ORCHESTRATOR_PROMPT,
    ORCHESTRATOR_ROUTER_PROMPT,
    PLANNER_AGENT_PROMPT,
    TREND_AGENT_PROMPT,
)
from src.config import Settings
from src.services import ServiceContainer
from src.workflow.state import WorkflowState


@dataclass
class AgentRuntime:
    settings: Settings
    services: ServiceContainer
    llm: LLMClient


def _safe_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _safe_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    result.append(text)
            elif item is not None:
                text = str(item).strip()
                if text:
                    result.append(text)
        return result
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
        return [part for part in parts if part]
    return []


def _safe_subject_file_specs(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    specs: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        mime_type = str(item.get("mime_type", "")).strip()
        path = str(item.get("path", "")).strip()
        raw_data = item.get("data")
        data = bytes(raw_data) if isinstance(raw_data, (bytes, bytearray)) else None

        if not any([path, data]):
            continue
        spec: dict[str, Any] = {}
        if name:
            spec["name"] = name
        if mime_type:
            spec["mime_type"] = mime_type
        if path:
            spec["path"] = path
        if data:
            spec["data"] = data
        specs.append(spec)
    return specs


def _task_enabled(state: WorkflowState, key: str, default: bool = True) -> bool:
    task_plan = state.get("task_plan", {})
    if not isinstance(task_plan, dict):
        return default
    return bool(task_plan.get(key, default))


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _derive_mode(run_planner: bool, run_creative: bool) -> str:
    if not (run_planner or run_creative):
        return "simple_query"
    if run_creative:
        return "campaign_generation"
    return "research_planning"


def _normalize_orchestrator_plan(raw_plan: Any, fallback_plan: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(raw_plan, dict):
        return None

    candidate = raw_plan.get("task_plan", raw_plan)
    if not isinstance(candidate, dict):
        return None

    run_trend = _coerce_bool(candidate.get("run_trend"), bool(fallback_plan.get("run_trend", False)))
    run_audience = _coerce_bool(candidate.get("run_audience"), bool(fallback_plan.get("run_audience", False)))
    run_competitor = _coerce_bool(candidate.get("run_competitor"), bool(fallback_plan.get("run_competitor", False)))
    run_planner = _coerce_bool(candidate.get("run_planner"), bool(fallback_plan.get("run_planner", False)))
    run_creative = _coerce_bool(candidate.get("run_creative"), bool(fallback_plan.get("run_creative", False)))

    if run_creative:
        run_planner = True

    run_compliance = run_creative
    run_critic = run_creative
    run_schedule = run_creative

    mode_value = str(candidate.get("mode", "")).strip().lower()
    allowed_modes = {"simple_query", "research_planning", "campaign_generation"}
    mode = mode_value if mode_value in allowed_modes else _derive_mode(run_planner, run_creative)

    if mode == "simple_query" and (run_planner or run_creative):
        mode = _derive_mode(run_planner, run_creative)
    if mode == "campaign_generation" and not run_creative:
        mode = _derive_mode(run_planner, run_creative)
    if mode == "research_planning" and run_creative:
        mode = _derive_mode(run_planner, run_creative)

    return {
        "mode": mode,
        "run_trend": run_trend,
        "run_audience": run_audience,
        "run_competitor": run_competitor,
        "run_planner": run_planner,
        "run_creative": run_creative,
        "run_compliance": run_compliance,
        "run_critic": run_critic,
        "run_schedule": run_schedule,
    }


def _build_task_plan(request: str) -> tuple[dict[str, Any], list[str]]:
    text = request.lower().strip()

    wants_competitor = any(keyword in text for keyword in ("competitor", "competition", "rival"))
    wants_trend = any(keyword in text for keyword in ("trend", "trending", "rising", "theme", "topic"))
    wants_audience = any(
        keyword in text
        for keyword in ("audience", "customer", "segment", "sentiment", "comment", "review", "pain point")
    )
    wants_planner = any(
        keyword in text for keyword in ("plan", "strategy", "campaign", "kpi", "hypothesis", "roadmap")
    )
    wants_campaign = "campaign" in text
    wants_creative = any(
        keyword in text
        for keyword in ("creative", "caption", "post", "asset", "image", "copy", "write", "generate")
    )
    disable_research = any(keyword in text for keyword in ("no research", "without research"))

    run_trend = wants_trend
    run_audience = wants_audience
    run_competitor = wants_competitor

    if (wants_planner or wants_creative) and not disable_research and not (run_trend or run_audience or run_competitor):
        # Default campaign mode uses all research signals unless user explicitly asks to skip them.
        run_trend = True
        run_audience = True
        run_competitor = True

    run_planner = wants_planner or wants_creative
    run_creative = wants_creative or wants_campaign
    run_compliance = run_creative
    run_critic = run_creative
    run_schedule = run_creative

    if not (run_planner or run_creative):
        mode = "simple_query"
    elif run_creative:
        mode = "campaign_generation"
    else:
        mode = "research_planning"

    task_plan = {
        "mode": mode,
        "run_trend": run_trend,
        "run_audience": run_audience,
        "run_competitor": run_competitor,
        "run_planner": run_planner,
        "run_creative": run_creative,
        "run_compliance": run_compliance,
        "run_critic": run_critic,
        "run_schedule": run_schedule,
    }
    assigned_tasks = [key for key, value in task_plan.items() if key.startswith("run_") and value]
    return task_plan, assigned_tasks


def _build_trend_web_query(state: WorkflowState, topic_clusters: list[dict[str, Any]]) -> str:
    request = state.get("request", "").strip()
    brand = state.get("brand_profile", {}).get("brand_name", "").strip()
    top_labels = [row.get("label", "") for row in topic_clusters[:2] if row.get("label")]
    label_hint = " ".join(top_labels)
    base = request if request else "social media marketing campaign trends"
    return f"{base} {brand} {label_hint} latest social trends".strip()


def _build_competitor_web_query(state: WorkflowState, competitor_posts: list[dict[str, Any]]) -> str:
    request = state.get("request", "").strip()
    competitor_names = [row.get("competitor", "") for row in competitor_posts[:3] if row.get("competitor")]
    names_hint = " ".join(competitor_names)
    base = request if request else "social media competitor strategies"
    return f"{base} {names_hint} latest competitor campaigns".strip()


def _collect_competitor_web_signals(
    runtime: AgentRuntime,
    state: WorkflowState,
    competitor_posts: list[dict[str, Any]],
) -> dict[str, Any]:
    combined_query = _build_competitor_web_query(state, competitor_posts)
    combined = runtime.services.web_search.search(
        query=combined_query,
        max_results=runtime.settings.web_search_max_results,
    )

    unique_names: list[str] = []
    for row in competitor_posts:
        if not isinstance(row, dict):
            continue
        name = str(row.get("competitor", "")).strip()
        if name and name not in unique_names:
            unique_names.append(name)

    per_competitor: list[dict[str, Any]] = []
    focused_limit = max(1, runtime.settings.web_search_max_results // 2)
    for name in unique_names[:3]:
        focused_query = (
            f"{name} bubble tea social media campaign Instagram TikTok latest posts"
        )
        focused_result = runtime.services.web_search.search(
            query=focused_query,
            max_results=focused_limit,
        )
        per_competitor.append(
            {
                "competitor": name,
                "query": focused_query,
                "search": focused_result,
            }
        )

    return {
        "combined_query": combined_query,
        "combined_search": combined,
        "per_competitor_searches": per_competitor,
    }


def _summarize_competitor_sources(web_signals: dict[str, Any]) -> dict[str, Any]:
    combined = web_signals.get("combined_search", {}) if isinstance(web_signals, dict) else {}
    per_competitor = web_signals.get("per_competitor_searches", []) if isinstance(web_signals, dict) else []

    combined_results = combined.get("results", []) if isinstance(combined, dict) else []
    combined_status = str(combined.get("status", "")).lower() if isinstance(combined, dict) else ""
    combined_provider = str(combined.get("provider", "")) if isinstance(combined, dict) else ""
    combined_error = str(combined.get("error", "")) if isinstance(combined, dict) else ""

    per_competitor_count = 0
    urls: list[str] = []
    for result in combined_results:
        if not isinstance(result, dict):
            continue
        url = str(result.get("url", "")).strip()
        if url and url not in urls:
            urls.append(url)

    for row in per_competitor:
        if not isinstance(row, dict):
            continue
        search_payload = row.get("search", {})
        if not isinstance(search_payload, dict):
            continue
        rows = search_payload.get("results", [])
        if isinstance(rows, list):
            per_competitor_count += len(rows)
            for item in rows:
                if not isinstance(item, dict):
                    continue
                url = str(item.get("url", "")).strip()
                if url and url not in urls:
                    urls.append(url)

    total_result_count = len(combined_results) + per_competitor_count
    web_available = combined_status == "ok" and total_result_count > 0
    return {
        "evidence_mode": "web_primary" if web_available else "snapshot_fallback",
        "combined_provider": combined_provider or "unknown",
        "combined_status": combined_status or "unknown",
        "combined_result_count": len(combined_results),
        "total_web_result_count": total_result_count,
        "combined_error": combined_error,
        "sample_urls": urls[:6],
    }


def load_context(runtime: AgentRuntime, state: WorkflowState) -> dict[str, Any]:
    brand_id = state.get("brand_id", runtime.settings.default_brand_id)
    campaign_id = state.get("campaign_id", runtime.settings.default_campaign_id)

    brand_profile = runtime.services.repository.get_brand_profile(brand_id)
    campaign_state = runtime.services.repository.get_campaign_state(campaign_id)
    analytics_snapshot = runtime.services.analytics.get_snapshot(brand_id)

    return {
        "brand_id": brand_id,
        "campaign_id": campaign_id,
        "status": "researching",
        "revision_count": state.get("revision_count", 0),
        "brand_profile": brand_profile,
        "campaign_state": campaign_state,
        "analytics_snapshot": analytics_snapshot,
        "shared_memory": runtime.services.memory.get_memory("shared"),
        "planner_memory": runtime.services.memory.get_memory("planner"),
        "creative_memory": runtime.services.memory.get_memory("creative"),
    }


def orchestrator_assign_tasks(runtime: AgentRuntime, state: WorkflowState) -> dict[str, Any]:
    request = state.get("request", "")
    fallback_task_plan, _ = _build_task_plan(request)
    task_plan = fallback_task_plan
    task_plan_source = "heuristic_fallback"

    payload = {
        "request": request,
        "brand_profile": {
            "brand_id": state.get("brand_profile", {}).get("brand_id", ""),
            "brand_name": state.get("brand_profile", {}).get("brand_name", ""),
            "industry": state.get("brand_profile", {}).get("industry", ""),
        },
        "campaign_state": {
            "campaign_id": state.get("campaign_state", {}).get("campaign_id", ""),
            "objective": state.get("campaign_state", {}).get("objective", ""),
            "channels": state.get("campaign_state", {}).get("channels", []),
            "status": state.get("campaign_state", {}).get("status", ""),
        },
        "available_agents": [
            "trend_research",
            "audience_research",
            "competitor_research",
            "planner",
            "creative",
            "compliance",
            "critic",
            "schedule",
        ],
    }

    try:
        routing_response = runtime.llm.run_json("orchestrator", ORCHESTRATOR_ROUTER_PROMPT, payload)
        normalized = _normalize_orchestrator_plan(routing_response, fallback_task_plan)
        if normalized is not None:
            task_plan = normalized
            task_plan_source = "orchestrator"
    except Exception:
        task_plan = fallback_task_plan
        task_plan_source = "heuristic_fallback"

    assigned_tasks = [key for key, value in task_plan.items() if key.startswith("run_") and value]
    return {
        "task_plan": task_plan,
        "assigned_tasks": assigned_tasks,
        "status": "researching" if assigned_tasks else "answered",
        "task_plan_source": task_plan_source,
    }


def trend_agent(runtime: AgentRuntime, state: WorkflowState) -> dict[str, Any]:
    if not _task_enabled(state, "run_trend"):
        return {"trend_report": {"skipped": True, "reason": "Trend agent not required for this request."}}

    topic_clusters = runtime.services.analytics.get_topic_clusters(state["brand_id"])
    web_query = _build_trend_web_query(state, topic_clusters)
    web_signals = runtime.services.web_search.search(
        query=web_query,
        max_results=runtime.settings.web_search_max_results,
    )

    payload = {
        "request": state.get("request", ""),
        "trend_data": runtime.services.analytics.get_trend_data(state["brand_id"]),
        "topic_clusters": topic_clusters,
        "visual_clusters": runtime.services.analytics.get_visual_clusters(state["brand_id"]),
        "entity_trends": runtime.services.analytics.get_entity_trends(state["brand_id"]),
        "web_signals": web_signals,
    }
    trend_report = runtime.llm.run_json("trend", TREND_AGENT_PROMPT, payload)
    return {"trend_report": trend_report}


def audience_agent(runtime: AgentRuntime, state: WorkflowState) -> dict[str, Any]:
    if not _task_enabled(state, "run_audience"):
        return {"audience_report": {"skipped": True, "reason": "Audience agent not required for this request."}}

    payload = {
        "request": state.get("request", ""),
        "comments": runtime.services.analytics.get_comments(state["brand_id"]),
        "comment_clusters": runtime.services.analytics.get_comment_clusters(state["brand_id"]),
        "review_summaries": runtime.services.analytics.get_review_summaries(state["brand_id"]),
        "segment_metrics": runtime.services.analytics.get_segment_metrics(state["brand_id"]),
    }
    audience_report = runtime.llm.run_json("audience", AUDIENCE_AGENT_PROMPT, payload)
    return {"audience_report": audience_report}


def competitor_agent(runtime: AgentRuntime, state: WorkflowState) -> dict[str, Any]:
    if not _task_enabled(state, "run_competitor"):
        return {"competitor_report": {"skipped": True, "reason": "Competitor agent not required for this request."}}

    competitor_posts = runtime.services.analytics.get_competitor_posts(state["brand_id"])
    web_signals = _collect_competitor_web_signals(runtime, state, competitor_posts)
    source_summary = _summarize_competitor_sources(web_signals)

    payload = {
        "request": state.get("request", ""),
        "competitor_posts": competitor_posts,
        "competitor_summaries": runtime.services.analytics.get_competitor_summaries(state["brand_id"]),
        "similar_posts": runtime.services.analytics.search_similar_posts(
            brand_id=state["brand_id"], query=state.get("request", "")
        ),
        "web_signals": web_signals,
        "source_policy": {
            "prefer_live_web": source_summary.get("evidence_mode") == "web_primary",
            "snapshot_role": "baseline_context_only",
            "source_summary": source_summary,
        },
    }
    competitor_report = runtime.llm.run_json("competitor", COMPETITOR_AGENT_PROMPT, payload)
    if isinstance(competitor_report, dict):
        competitor_report["source_summary"] = source_summary
    return {"competitor_report": competitor_report}


def planner_agent(runtime: AgentRuntime, state: WorkflowState) -> dict[str, Any]:
    if not _task_enabled(state, "run_planner"):
        return {
            "planner_output": {"skipped": True, "reason": "Planner not required for this request."},
            "status": "planning",
        }

    include_campaign_state = _coerce_bool(state.get("include_campaign_state_in_planner"), True)
    planner_campaign_state = state.get("campaign_state", {}) if include_campaign_state else {}

    payload = {
        "request": state.get("request", ""),
        "brand_profile": state.get("brand_profile", {}),
        "campaign_state": planner_campaign_state,
        "trend_report": state.get("trend_report", {}),
        "audience_report": state.get("audience_report", {}),
        "competitor_report": state.get("competitor_report", {}),
        "prediction_scores": runtime.services.analytics.get_prediction_scores(state["brand_id"]),
        "memory": {
            "shared": state.get("shared_memory", {}),
            "planner": state.get("planner_memory", {}),
        },
        "context_controls": {
            "include_campaign_state": include_campaign_state,
        },
    }
    planner_output = runtime.llm.run_json("planner", PLANNER_AGENT_PROMPT, payload)
    planner_output.setdefault("must_run_assets", [])
    planner_output.setdefault("test_assets", [])
    planner_output.setdefault("optional_exploratory_assets", [])
    return {"planner_output": planner_output, "status": "planning"}


def creative_agent(runtime: AgentRuntime, state: WorkflowState) -> dict[str, Any]:
    if not _task_enabled(state, "run_creative"):
        return {
            "creative_assets": [],
            "status": "creating",
        }

    image_subjects = _safe_str_list(state.get("image_subjects", []))
    image_elements = _safe_str_list(state.get("image_elements", []))
    image_subject_files = _safe_subject_file_specs(state.get("image_subject_files", []))
    if not image_subjects and image_subject_files:
        image_subjects = [spec.get("name", "subject image") for spec in image_subject_files if spec.get("name")]

    payload = {
        "request": state.get("request", ""),
        "brand_profile": state.get("brand_profile", {}),
        "creative_brief": state.get("planner_output", {}).get("creative_brief", {}),
        "must_run_assets": state.get("planner_output", {}).get("must_run_assets", []),
        "test_assets": state.get("planner_output", {}).get("test_assets", []),
        "memory": state.get("creative_memory", {}),
        "revision_notes": state.get("compliance_result", {}).get("revision_instructions", []),
        "image_constraints": {
            "subjects": image_subjects,
            "elements": image_elements,
            "subject_image_count": len(image_subject_files),
            "subject_image_names": [spec.get("name", "") for spec in image_subject_files if spec.get("name")],
        },
    }
    creative_response = runtime.llm.run_json("creative", CREATIVE_AGENT_PROMPT, payload)
    assets = _safe_list(creative_response.get("assets"))

    enriched: list[dict[str, Any]] = []
    for idx, asset in enumerate(assets, start=1):
        asset.setdefault("asset_id", f"asset_{idx:03d}")
        if not isinstance(asset.get("target_segment"), str) or not str(asset.get("target_segment", "")).strip():
            asset["target_segment"] = "all"
        for text_key in ("caption", "image_prompt", "cta", "topic_hint", "visual_hint", "pillar", "channel"):
            if text_key in asset and not isinstance(asset[text_key], str):
                asset[text_key] = str(asset[text_key])

        image_guidance_parts: list[str] = []
        if image_subjects:
            image_guidance_parts.append(f"Primary product subjects: {', '.join(image_subjects)}.")
        if image_elements:
            image_guidance_parts.append(f"Required scene elements: {', '.join(image_elements)}.")
        image_guidance = " ".join(image_guidance_parts).strip()

        image_prompt = str(asset.get("image_prompt", ""))
        image_style = str(asset.get("visual_hint", ""))
        if image_guidance:
            image_prompt = f"{image_prompt}\nAdditional visual constraints: {image_guidance}".strip()
            image_style = f"{image_style}. {image_guidance}".strip(". ").strip()

        image = runtime.services.image_generation.generate_image(
            prompt=image_prompt,
            style=image_style,
            subject_images=image_subject_files,
        )
        score = runtime.services.scoring.score_candidate(state["brand_id"], asset)
        enriched_asset = {
            **asset,
            "generated_image": image,
            "image_constraints_applied": {
                "subjects": image_subjects,
                "elements": image_elements,
                "subject_image_count": len(image_subject_files),
                "subject_image_names": [spec.get("name", "") for spec in image_subject_files if spec.get("name")],
            },
            "ranking": score,
        }
        enriched.append(enriched_asset)

    ranked = sorted(
        enriched,
        key=lambda item: (
            item.get("ranking", {}).get("score", 0.0),
            item.get("ranking", {}).get("predicted_ctr", 0.0),
        ),
        reverse=True,
    )
    return {"creative_assets": ranked, "status": "creating"}


def compliance_agent(runtime: AgentRuntime, state: WorkflowState) -> dict[str, Any]:
    if not _task_enabled(state, "run_compliance"):
        return {
            "compliance_result": {
                "aggregate_score": 1.0,
                "recommendation": "approve",
                "llm_recommendation": "approve",
                "summary": "Compliance step skipped; no creative assets requested.",
                "top_risks": [],
                "revision_instructions": [],
                "per_asset": [],
            },
            "status": "reviewing",
        }

    per_asset = [
        runtime.services.compliance.score_asset(state["brand_id"], asset)
        for asset in state.get("creative_assets", [])
    ]
    scores = [result["score"] for result in per_asset] or [0.0]
    recommendations = [result["recommendation"] for result in per_asset]

    if "block" in recommendations:
        aggregate_recommendation = "block"
    elif "revise" in recommendations:
        aggregate_recommendation = "revise"
    else:
        aggregate_recommendation = "approve"

    payload = {
        "policy_rules": runtime.services.compliance.get_policy_rules(state["brand_id"]),
        "per_asset_results": per_asset,
        "aggregate_score": round(mean(scores), 3),
    }
    review = runtime.llm.run_json("compliance", COMPLIANCE_AGENT_PROMPT, payload)
    return {
        "compliance_result": {
            "aggregate_score": round(mean(scores), 3),
            "recommendation": aggregate_recommendation,
            "llm_recommendation": review.get("recommendation", aggregate_recommendation),
            "summary": review.get("summary", ""),
            "top_risks": review.get("top_risks", []),
            "revision_instructions": review.get("revision_instructions", []),
            "per_asset": per_asset,
        },
        "status": "reviewing",
    }


def critic_agent(runtime: AgentRuntime, state: WorkflowState) -> dict[str, Any]:
    if not _task_enabled(state, "run_critic"):
        return {
            "critic_result": {
                "mode": "pre_publish",
                "quality_score": 1.0,
                "critique_points": [],
                "proposed_learnings": [],
                "confidence": 1.0,
                "summary": "Critic skipped; no creative assets requested.",
            }
        }

    payload = {
        "mode": "pre_publish",
        "request": state.get("request", ""),
        "planner_output": state.get("planner_output", {}),
        "creative_assets": state.get("creative_assets", []),
        "prediction_scores": runtime.services.analytics.get_prediction_scores(state["brand_id"]),
    }
    critic = runtime.llm.run_json("review", CRITIC_AGENT_PROMPT, payload)
    return {"critic_result": critic}


def orchestrator_review(runtime: AgentRuntime, state: WorkflowState) -> dict[str, Any]:
    if not _task_enabled(state, "run_creative"):
        return {
            "route_decision": "blocked",
            "approved_assets": [],
            "revision_count": state.get("revision_count", 0),
            "status": "answered",
            "orchestrator_summary": {
                "summary": "Creative/compliance/review pipeline skipped for this request.",
                "assigned_tasks": state.get("assigned_tasks", []),
            },
        }

    compliance = state.get("compliance_result", {})
    critic = state.get("critic_result", {})
    revision_count = state.get("revision_count", 0)

    compliance_score = compliance.get("aggregate_score", 0.0)
    compliance_recommendation = compliance.get("recommendation", "revise")
    quality_score = critic.get("quality_score", 0.0)

    if compliance_recommendation == "block":
        route_decision = "blocked"
    elif compliance_score < 0.72 or quality_score < 0.64:
        route_decision = (
            "revise"
            if revision_count < runtime.settings.max_creative_revisions
            else "blocked"
        )
    else:
        route_decision = "approved"

    payload = {
        "request": state.get("request", ""),
        "compliance_result": compliance,
        "critic_result": critic,
        "route_decision": route_decision,
    }
    orchestrator_summary = runtime.llm.run_json("orchestrator", ORCHESTRATOR_PROMPT, payload)

    approved_assets = state.get("creative_assets", []) if route_decision == "approved" else []
    updated_revisions = revision_count + 1 if route_decision == "revise" else revision_count
    if route_decision == "approved":
        status = "approved"
    elif route_decision == "blocked":
        status = "blocked"
    else:
        status = "reviewing"

    return {
        "route_decision": route_decision,
        "approved_assets": approved_assets,
        "revision_count": updated_revisions,
        "status": status,
        "orchestrator_summary": orchestrator_summary,
    }


def schedule_assets(runtime: AgentRuntime, state: WorkflowState) -> dict[str, Any]:
    if not _task_enabled(state, "run_schedule"):
        return {"scheduled_posts": [], "status": state.get("status", "approved")}

    approved_assets = state.get("approved_assets", [])
    top_assets = approved_assets[:3]
    scheduled = runtime.services.scheduling.schedule_assets(
        campaign_id=state["campaign_id"],
        assets=top_assets,
    )

    campaign_state = dict(state.get("campaign_state", {}))
    campaign_state["status"] = "scheduled"
    campaign_state["scheduled_posts"] = scheduled
    runtime.services.repository.write_campaign_state(state["campaign_id"], campaign_state)

    return {"scheduled_posts": scheduled, "status": "scheduled"}


def finalize(runtime: AgentRuntime, state: WorkflowState) -> dict[str, Any]:
    task_plan = state.get("task_plan", {})
    if task_plan.get("mode") == "simple_query":
        research_answer: dict[str, Any] = {}
        for key in ("trend_report", "audience_report", "competitor_report"):
            value = state.get(key)
            if isinstance(value, dict) and not value.get("skipped"):
                research_answer[key] = value

        final_output = {
            "request": state.get("request", ""),
            "status": "answered",
            "mode": "simple_query",
            "assigned_tasks": state.get("assigned_tasks", []),
            "task_plan_source": state.get("task_plan_source", "heuristic_fallback"),
            "answer": research_answer,
            "next_actions": [
                "Ask for a campaign plan if you want strategy and assets.",
                "Ask for content generation if you want draft posts/images.",
            ],
        }
        return {"final_output": final_output}

    final_output = {
        "request": state.get("request", ""),
        "status": state.get("status", "approved"),
        "mode": task_plan.get("mode", "campaign_generation"),
        "assigned_tasks": state.get("assigned_tasks", []),
        "task_plan_source": state.get("task_plan_source", "heuristic_fallback"),
        "strategic_summary": state.get("planner_output", {}).get("strategic_summary", ""),
        "hypotheses": state.get("planner_output", {}).get("hypotheses", []),
        "content_pillars": state.get("planner_output", {}).get("content_pillars", []),
        "approved_assets": state.get("approved_assets", []),
        "scheduled_posts": state.get("scheduled_posts", []),
        "rationale": state.get("orchestrator_summary", {}),
        "next_actions": [
            "Monitor CTR and save rate for 7 days.",
            "Run post-performance reflection to validate memory updates.",
        ],
    }
    return {"final_output": final_output}


def reflection_agent(runtime: AgentRuntime, state: WorkflowState) -> dict[str, Any]:
    payload = {
        "mode": "post_performance",
        "published_posts": runtime.services.analytics.get_post_data(state["brand_id"]),
        "scheduled_posts": state.get("scheduled_posts", []),
        "planner_output": state.get("planner_output", {}),
        "creative_assets": state.get("approved_assets", []),
    }
    reflection = runtime.llm.run_json("review", CRITIC_AGENT_PROMPT, payload)
    return {"reflection_report": reflection, "status": "reflecting"}


def memory_commit(runtime: AgentRuntime, state: WorkflowState) -> dict[str, Any]:
    reflection = state.get("reflection_report", {})
    confidence = float(reflection.get("confidence", 0.0))
    proposed = _safe_list(reflection.get("proposed_learnings"))

    if confidence < 0.7 or not proposed:
        return {
            "memory_update_result": {
                "updated": False,
                "reason": "Confidence too low or no learnings proposed.",
                "confidence": confidence,
            },
            "status": "reflecting",
        }

    update_payload = {
        "lesson": "; ".join(proposed[:2]),
        "evidence": reflection.get("critique_points", []),
    }
    updated_shared = runtime.services.memory.update_memory(
        scope="shared",
        lesson=update_payload,
        confidence=confidence,
    )
    updated_planner = runtime.services.memory.update_memory(
        scope="planner",
        lesson=update_payload,
        confidence=confidence,
    )
    updated_creative = runtime.services.memory.update_memory(
        scope="creative",
        lesson=update_payload,
        confidence=confidence,
    )

    return {
        "memory_update_result": {
            "updated": True,
            "confidence": confidence,
            "scopes": {
                "shared": updated_shared,
                "planner": updated_planner,
                "creative": updated_creative,
            },
        },
        "status": "memory_updated",
    }
