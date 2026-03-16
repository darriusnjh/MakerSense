from __future__ import annotations

from typing import Any, TypedDict


class WorkflowState(TypedDict, total=False):
    request: str
    brand_id: str
    campaign_id: str
    run_reflection: bool
    include_campaign_state_in_planner: bool
    image_subjects: list[str]
    image_elements: list[str]
    image_subject_files: list[dict[str, Any]]

    status: str
    revision_count: int
    task_plan: dict[str, Any]
    assigned_tasks: list[str]
    task_plan_source: str

    brand_profile: dict[str, Any]
    campaign_state: dict[str, Any]
    analytics_snapshot: dict[str, Any]
    shared_memory: dict[str, Any]
    planner_memory: dict[str, Any]
    creative_memory: dict[str, Any]

    trend_report: dict[str, Any]
    audience_report: dict[str, Any]
    competitor_report: dict[str, Any]

    planner_output: dict[str, Any]
    creative_assets: list[dict[str, Any]]
    compliance_result: dict[str, Any]
    critic_result: dict[str, Any]
    orchestrator_summary: dict[str, Any]
    approved_assets: list[dict[str, Any]]
    scheduled_posts: list[dict[str, Any]]

    reflection_report: dict[str, Any]
    memory_update_result: dict[str, Any]

    final_output: dict[str, Any]
    route_decision: str
