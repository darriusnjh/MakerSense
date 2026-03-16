from __future__ import annotations

import html
import json
import re
import sys
import textwrap
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.agents.llm_client import LLMClient
from src.agents.nodes import AgentRuntime
from src.config import Settings, get_settings
from src.services import build_services
from src.storage import build_repository
from src.workflow import build_workflow

RUN_LOG_PATH = ROOT_DIR / "logs" / "campaign_runs.jsonl"
SCHEDULE_JSON_PATH = ROOT_DIR / "data" / "schedule.json"
SUBJECT_UPLOAD_ROOT = ROOT_DIR / "data" / "subject_uploads"
DEFAULT_TRACE_FILE = "logs/workflow_trace_ui.jsonl"

NODE_W = 190
NODE_H = 88

WORKFLOW_NODES: list[dict[str, Any]] = [
    {"id": "trigger", "label": "Campaign Trigger", "subtitle": "entrypoint", "x": 60, "y": 240},
    {"id": "load_context", "label": "Load Context", "subtitle": "brand + analytics", "x": 320, "y": 240},
    {
        "id": "orchestrator_assign_tasks",
        "label": "Orchestrator Router",
        "subtitle": "task assignment",
        "x": 580,
        "y": 240,
    },
    {"id": "trend_research", "label": "Trend Agent", "subtitle": "research", "x": 860, "y": 90},
    {"id": "audience_research", "label": "Audience Agent", "subtitle": "research", "x": 860, "y": 240},
    {"id": "competitor_research", "label": "Competitor Agent", "subtitle": "research", "x": 860, "y": 390},
    {"id": "planner", "label": "Planner Agent", "subtitle": "strategy", "x": 1140, "y": 240},
    {"id": "creative", "label": "Creator Agent", "subtitle": "assets + images", "x": 1420, "y": 240},
    {"id": "compliance", "label": "Compliance Agent", "subtitle": "policy check", "x": 1690, "y": 130},
    {"id": "critic", "label": "Reviewer Agent", "subtitle": "quality check", "x": 1690, "y": 350},
    {
        "id": "orchestrator_review",
        "label": "Orchestrator Review",
        "subtitle": "approve/revise/block",
        "x": 1970,
        "y": 240,
    },
    {"id": "schedule", "label": "Schedule", "subtitle": "publish plan", "x": 2250, "y": 140},
    {"id": "finalize", "label": "Finalize", "subtitle": "final output", "x": 2250, "y": 340},
    {"id": "reflection", "label": "Reflection", "subtitle": "post-run learning", "x": 2520, "y": 280},
    {"id": "memory_commit", "label": "Memory Commit", "subtitle": "persist lessons", "x": 2780, "y": 280},
]

NODE_IDS = [node["id"] for node in WORKFLOW_NODES]
NODE_POSITIONS = {node["id"]: (node["x"], node["y"]) for node in WORKFLOW_NODES}

WORKFLOW_EDGES: list[tuple[str, str, bool, str]] = [
    ("trigger", "load_context", False, ""),
    ("load_context", "orchestrator_assign_tasks", False, ""),
    ("orchestrator_assign_tasks", "trend_research", True, ""),
    ("orchestrator_assign_tasks", "audience_research", True, ""),
    ("orchestrator_assign_tasks", "competitor_research", True, ""),
    ("trend_research", "planner", True, ""),
    ("audience_research", "planner", True, ""),
    ("competitor_research", "planner", True, ""),
    ("planner", "creative", False, ""),
    ("creative", "compliance", True, ""),
    ("creative", "critic", True, ""),
    ("compliance", "orchestrator_review", True, ""),
    ("critic", "orchestrator_review", True, ""),
    ("orchestrator_review", "creative", True, "revise"),
    ("orchestrator_review", "schedule", True, "approved"),
    ("orchestrator_review", "finalize", True, "blocked"),
    ("schedule", "finalize", False, ""),
    ("finalize", "reflection", True, "reflect"),
    ("reflection", "memory_commit", True, ""),
]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _slug(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip())
    return clean.strip("-") or "item"


def _split_values(raw: str) -> list[str]:
    values: list[str] = []
    for part in re.split(r"[,\n]", raw or ""):
        value = part.strip()
        if value:
            values.append(value)
    return values


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, (bytes, bytearray)):
        return f"<{len(value)} bytes>"
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_json_safe(record), ensure_ascii=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8-sig").strip()
    if not raw:
        return {}
    return json.loads(raw)


def _resolve_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return ROOT_DIR / path


def _default_request_placeholder(brand_id: str) -> str:
    profiles = _read_json(ROOT_DIR / "data" / "brand_profiles.json")
    profile = profiles.get(brand_id, {}) if isinstance(profiles, dict) else {}
    brand_name = str(profile.get("brand_name", "")).strip() or brand_id or "our brand"
    return (
        f"Create Instagram content for {brand_name}'s upcoming Fragrant Lemon Tea release "
        "for Chinese New Year."
    )


def _initial_node_status() -> dict[str, str]:
    return {node_id: "pending" for node_id in NODE_IDS}


def _status_from_payload(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "done"
    for value in payload.values():
        if isinstance(value, dict) and value.get("skipped") is True:
            return "skipped"
    return "done"


def _extract_skip_reason(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for value in payload.values():
        if isinstance(value, dict) and value.get("skipped") is True:
            reason = value.get("reason")
            if isinstance(reason, str):
                return reason
    return ""


def _extract_error_node(text: str) -> str:
    match = re.search(r"During task with name '([^']+)'", text)
    if match:
        return match.group(1)
    return ""


def _write_trace(trace_path: Path, event: dict[str, Any]) -> None:
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_json_safe(event), ensure_ascii=True) + "\n")


@st.cache_resource(show_spinner=False)
def _load_runtime_graph() -> tuple[Settings, Any]:
    settings = get_settings()
    repository = build_repository(settings)
    services = build_services(settings, repository)
    runtime = AgentRuntime(settings=settings, services=services, llm=LLMClient(settings))
    graph = build_workflow(runtime)
    return settings, graph


def _edge_points(source_id: str, target_id: str) -> tuple[float, float, float, float]:
    sx, sy = NODE_POSITIONS[source_id]
    tx, ty = NODE_POSITIONS[target_id]
    return (sx + NODE_W, sy + NODE_H / 2, tx, ty + NODE_H / 2)


def _edge_active(status_map: dict[str, str], source_id: str, target_id: str, active_node: str) -> bool:
    source_status = status_map.get(source_id, "pending")
    target_status = status_map.get(target_id, "pending")
    if active_node in {source_id, target_id}:
        return True
    if source_status in {"running", "done", "skipped"} and target_status in {"running", "done", "skipped", "error"}:
        return True
    return False


def _stream_workflow(
    graph: Any,
    input_state: dict[str, Any],
    status_map: dict[str, str],
    on_update: Callable[[list[dict[str, Any]], dict[str, str], dict[str, Any], str], None],
    trace_file: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    merged_state = dict(input_state)
    events: list[dict[str, Any]] = []

    trace_path: Path | None = None
    if trace_file.strip():
        trace_candidate = Path(trace_file.strip())
        trace_path = trace_candidate if trace_candidate.is_absolute() else ROOT_DIR / trace_candidate
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_path.write_text("", encoding="utf-8")

    status_map["trigger"] = "done"
    on_update(events, status_map, merged_state, "trigger")

    try:
        for update in graph.stream(input_state, stream_mode="updates"):
            ts = _now_iso()
            if not isinstance(update, dict):
                event = {
                    "ts": ts,
                    "node": "system",
                    "status": "info",
                    "keys": [],
                    "message": str(update),
                }
                events.append(event)
                on_update(events, status_map, merged_state, "")
                continue

            for node_name, payload in update.items():
                status_map[node_name] = "running"
                on_update(events, status_map, merged_state, node_name)

                keys = list(payload.keys()) if isinstance(payload, dict) else []
                if isinstance(payload, dict):
                    merged_state.update(payload)

                node_status = _status_from_payload(payload)
                status_map[node_name] = node_status

                event = {
                    "ts": ts,
                    "node": node_name,
                    "status": node_status,
                    "keys": keys,
                }
                skip_reason = _extract_skip_reason(payload)
                if skip_reason:
                    event["message"] = skip_reason
                events.append(event)

                if trace_path:
                    _write_trace(
                        trace_path,
                        {
                            "ts": ts,
                            "type": "node_update",
                            "node": node_name,
                            "keys": keys,
                            "payload": payload,
                        },
                    )

                on_update(events, status_map, merged_state, node_name)
    except Exception as exc:
        text = str(exc)
        error_node = _extract_error_node(text)
        if error_node:
            status_map[error_node] = "error"
        events.append(
            {
                "ts": _now_iso(),
                "node": error_node or "system",
                "status": "error",
                "keys": [],
                "message": text,
            }
        )
        merged_state["frontend_error"] = {
            "message": text,
            "node": error_node,
        }
        on_update(events, status_map, merged_state, error_node)
        return merged_state, events, text

    for node_id, status in list(status_map.items()):
        if status == "pending":
            status_map[node_id] = "skipped"
    on_update(events, status_map, merged_state, "")
    return merged_state, events, ""

def _render_canvas(status_map: dict[str, str], active_node: str, state: dict[str, Any]) -> None:
    task_plan = state.get("task_plan", {})
    enabled = [
        key.replace("run_", "")
        for key, value in task_plan.items()
        if isinstance(key, str) and key.startswith("run_") and value
    ]
    mode = str(task_plan.get("mode", state.get("final_output", {}).get("mode", ""))).strip() or "n/a"
    source = str(state.get("task_plan_source", "n/a"))
    route = str(state.get("route_decision", "n/a"))

    legend = "".join(
        [
            '<span class="wf-legend-chip pending">pending</span>',
            '<span class="wf-legend-chip running">running</span>',
            '<span class="wf-legend-chip done">done</span>',
            '<span class="wf-legend-chip skipped">skipped</span>',
            '<span class="wf-legend-chip error">error</span>',
        ]
    )

    edge_svg_parts: list[str] = []
    for source_id, target_id, dashed, label in WORKFLOW_EDGES:
        x1, y1, x2, y2 = _edge_points(source_id, target_id)
        classes = ["wf-edge"]
        if dashed:
            classes.append("dashed")
        if _edge_active(status_map, source_id, target_id, active_node):
            classes.append("on")
        class_attr = " ".join(classes)
        edge_svg_parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" class="{class_attr}" />'
        )
        if label:
            lx = (x1 + x2) / 2
            ly = (y1 + y2) / 2 - 8
            edge_svg_parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" class="wf-edge-label">{html.escape(label)}</text>')

    node_parts: list[str] = []
    for node in WORKFLOW_NODES:
        node_id = node["id"]
        status = status_map.get(node_id, "pending")
        status_label = status.upper()
        active_cls = " active" if node_id == active_node else ""
        node_parts.append(
            (
                f'<div class="wf-node {status}{active_cls}" style="left: {node["x"]}px; top: {node["y"]}px;">'
                '<div class="wf-node-top">'
                '<span class="wf-node-dot"></span>'
                f'<span class="wf-node-title">{html.escape(node["label"])}</span>'
                "</div>"
                f'<div class="wf-node-sub">{html.escape(node["subtitle"])}</div>'
                f'<div class="wf-node-badge">{status_label}</div>'
                "</div>"
            )
        )

    active_text = html.escape(active_node or "idle")
    enabled_text = html.escape(", ".join(enabled) if enabled else "none")
    canvas_html = f"""
    <div class="wf-header-strip">
      <div class="wf-header-left">
        <span class="wf-pill">Editor</span>
        <span class="wf-pill muted">Executions</span>
        <span class="wf-pill muted">Evaluations</span>
      </div>
      <div class="wf-header-right">
        <span class="wf-meta">mode: {html.escape(mode)}</span>
        <span class="wf-meta">router: {html.escape(source)}</span>
        <span class="wf-meta">route: {html.escape(route)}</span>
      </div>
    </div>
    <div class="wf-legend">{legend}</div>
    <div class="wf-meta-row">
      <span>active node: <strong>{active_text}</strong></span>
      <span>enabled tasks: <strong>{enabled_text}</strong></span>
    </div>
    <div class="wf-scroll">
      <div class="wf-canvas">
        <svg class="wf-svg" viewBox="0 0 3100 640" preserveAspectRatio="none">{"".join(edge_svg_parts)}</svg>{"".join(node_parts)}
      </div>
    </div>
    """
    st.markdown(textwrap.dedent(canvas_html).strip(), unsafe_allow_html=True)


def _render_event_feed(events: list[dict[str, Any]]) -> None:
    if not events:
        st.info("No workflow events yet.")
        return
    rows: list[str] = []
    for event in events[-18:]:
        ts = str(event.get("ts", ""))
        node = str(event.get("node", ""))
        status = str(event.get("status", "info"))
        keys = event.get("keys", [])
        key_text = ", ".join(keys) if isinstance(keys, list) and keys else "-"
        message = str(event.get("message", "")).strip()
        extra = f" | {html.escape(message)}" if message else ""
        rows.append(
            (
                '<div class="wf-log-row">'
                f'<span class="wf-log-time">{html.escape(ts[11:19] if len(ts) >= 19 else ts)}</span>'
                f'<span class="wf-log-node">{html.escape(node)}</span>'
                f'<span class="wf-log-status {html.escape(status)}">{html.escape(status)}</span>'
                f'<span class="wf-log-keys">{html.escape(key_text)}{extra}</span>'
                "</div>"
            )
        )
    st.markdown(f'<div class="wf-log-box">{"".join(rows)}</div>', unsafe_allow_html=True)


def _extract_assets_from_state(state: dict[str, Any]) -> list[dict[str, Any]]:
    final_output = state.get("final_output", {})
    if isinstance(final_output, dict):
        approved = final_output.get("approved_assets")
        if isinstance(approved, list):
            return [item for item in approved if isinstance(item, dict)]
    approved_assets = state.get("approved_assets", [])
    if isinstance(approved_assets, list):
        return [item for item in approved_assets if isinstance(item, dict)]
    return []


def _render_asset_gallery(assets: list[dict[str, Any]], key_prefix: str) -> None:
    del key_prefix
    if not assets:
        st.caption("No generated assets.")
        return

    columns = st.columns(2)
    for index, asset in enumerate(assets, start=1):
        with columns[(index - 1) % 2]:
            asset_id = str(asset.get("asset_id", f"asset_{index:03d}"))
            channel = str(asset.get("channel", ""))
            title = f"{asset_id} | {channel}" if channel else asset_id
            st.markdown(f"**{title}**")
            pillar = str(asset.get("pillar", "")).strip()
            if pillar:
                st.caption(pillar)

            caption_text = str(asset.get("caption", "")).strip()
            if caption_text:
                st.write(caption_text)

            cta = str(asset.get("cta", "")).strip()
            if cta:
                st.markdown(f"`CTA:` {cta}")

            generated = asset.get("generated_image", {})
            if isinstance(generated, dict):
                image_path = str(generated.get("image_path", "")).strip()
                image_url = str(generated.get("image_url", "")).strip()
                if image_path:
                    resolved = _resolve_path(image_path)
                    if resolved.exists():
                        st.image(str(resolved), use_container_width=True)
                    else:
                        st.caption(image_path)
                elif image_url:
                    local_url_path = _resolve_path(image_url)
                    if local_url_path.exists():
                        st.image(str(local_url_path), use_container_width=True)
                    else:
                        st.caption(image_url)

                status = str(generated.get("status", "")).strip()
                if status == "error":
                    st.error(str(generated.get("error", "Image generation failed.")))
                warnings = generated.get("subject_warnings", [])
                if isinstance(warnings, list) and warnings:
                    for warning in warnings:
                        st.caption(f"warning: {warning}")

            constraints = asset.get("image_constraints_applied", {})
            if isinstance(constraints, dict):
                subjects = constraints.get("subjects", [])
                elements = constraints.get("elements", [])
                if subjects:
                    st.caption(f"subjects: {', '.join(str(item) for item in subjects)}")
                if elements:
                    st.caption(f"elements: {', '.join(str(item) for item in elements)}")
            st.divider()


def _render_non_image_output(final_output: dict[str, Any], state: dict[str, Any] | None = None) -> None:
    strategic_summary = str(final_output.get("strategic_summary", "")).strip()
    if strategic_summary:
        st.markdown("**Strategic Summary**")
        st.write(strategic_summary)

    hypotheses = final_output.get("hypotheses", [])
    if isinstance(hypotheses, list) and hypotheses:
        st.markdown("**Hypotheses**")
        for item in hypotheses:
            if isinstance(item, str) and item.strip():
                st.markdown(f"- {item.strip()}")

    content_pillars = final_output.get("content_pillars", [])
    if isinstance(content_pillars, list) and content_pillars:
        st.markdown("**Content Pillars**")
        for item in content_pillars:
            if isinstance(item, str) and item.strip():
                st.markdown(f"- {item.strip()}")

    answer = final_output.get("answer", {})
    if isinstance(answer, dict) and answer:
        st.markdown("**Answer**")
        st.json(answer)

    if state:
        planner_output = state.get("planner_output", {})
        if isinstance(planner_output, dict) and planner_output:
            with st.expander("Planner Output", expanded=False):
                st.json(planner_output)


def _persist_subject_uploads(uploaded_files: list[Any], campaign_id: str) -> list[dict[str, Any]]:
    if not uploaded_files:
        return []
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target_dir = SUBJECT_UPLOAD_ROOT / _slug(campaign_id or "campaign_default")
    target_dir.mkdir(parents=True, exist_ok=True)

    specs: list[dict[str, Any]] = []
    for index, uploaded in enumerate(uploaded_files, start=1):
        original_name = _slug(getattr(uploaded, "name", f"subject-{index}.bin"))
        mime_type = str(getattr(uploaded, "type", "") or "application/octet-stream")
        content = uploaded.getvalue()
        filename = f"{timestamp}-{index:02d}-{original_name}"
        file_path = target_dir / filename
        file_path.write_bytes(content)
        specs.append(
            {
                "name": original_name,
                "mime_type": mime_type,
                "path": str(file_path),
            }
        )
    return specs


def _render_final_output_section(state: dict[str, Any], events: list[dict[str, Any]]) -> None:
    final_output = state.get("final_output", {})
    if not isinstance(final_output, dict):
        st.info("No final output yet.")
        return

    status = str(final_output.get("status", state.get("status", "")))
    mode = str(final_output.get("mode", state.get("task_plan", {}).get("mode", "")))
    task_source = str(final_output.get("task_plan_source", state.get("task_plan_source", "")))
    st.markdown(f"**Result**: `{status or 'unknown'}`  |  **Mode**: `{mode or 'n/a'}`  |  **Router**: `{task_source or 'n/a'}`")

    if mode == "simple_query":
        st.subheader("Query Answer")
        answer = final_output.get("answer", {})
        if isinstance(answer, dict) and answer:
            st.json(answer)
        else:
            st.info("No structured answer payload returned.")
    else:
        _render_non_image_output(final_output, state=state)
        st.subheader("Campaign Assets")
        assets = _extract_assets_from_state(state)
        if assets:
            _render_asset_gallery(assets, key_prefix="current")
        else:
            st.info("This run produced strategy/research output without generated image assets.")

    download_name = f"run-output-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    st.download_button(
        "Download Final Output",
        data=json.dumps(_json_safe(final_output), indent=2),
        file_name=download_name,
        mime="application/json",
        use_container_width=True,
    )

    with st.expander("Full Final Output JSON", expanded=False):
        st.json(final_output)
    with st.expander("Live Event Trace", expanded=False):
        st.json(events)


def _save_run_record(
    started_at: str,
    finished_at: str,
    input_state: dict[str, Any],
    final_state: dict[str, Any],
    events: list[dict[str, Any]],
    error_text: str,
) -> None:
    final_output = final_state.get("final_output", {})
    mode = ""
    status = ""
    if isinstance(final_output, dict):
        mode = str(final_output.get("mode", ""))
        status = str(final_output.get("status", ""))

    record = {
        "started_at": started_at,
        "finished_at": finished_at,
        "request": input_state.get("request", ""),
        "brand_id": input_state.get("brand_id", ""),
        "campaign_id": input_state.get("campaign_id", ""),
        "reflect": bool(input_state.get("run_reflection", False)),
        "mode": mode or str(final_state.get("task_plan", {}).get("mode", "")),
        "status": status or str(final_state.get("status", "")),
        "route_decision": final_state.get("route_decision", ""),
        "final_output": final_output,
        "events": events,
        "error": error_text,
    }
    _append_jsonl(RUN_LOG_PATH, record)


def _render_schedule_snapshot() -> None:
    schedule_data = _read_json(SCHEDULE_JSON_PATH)
    if not schedule_data:
        st.caption("No schedule records found yet.")
        return

    rows: list[dict[str, Any]] = []
    for campaign_id, entries in schedule_data.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            payload = entry.get("payload", {}) if isinstance(entry.get("payload"), dict) else {}
            rows.append(
                {
                    "campaign_id": campaign_id,
                    "asset_id": entry.get("asset_id", ""),
                    "channel": entry.get("channel", payload.get("channel", "")),
                    "scheduled_for": entry.get("scheduled_for", ""),
                }
            )

    if not rows:
        st.caption("No scheduled posts captured.")
        return
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_run_outputs_page() -> None:
    st.markdown("## Run Outputs")
    records = _read_jsonl(RUN_LOG_PATH)
    records = sorted(records, key=lambda item: str(item.get("finished_at", "")), reverse=True)

    if not records:
        st.info("No run outputs yet. Execute a workflow from the editor first.")
        st.subheader("Current Schedule Snapshot")
        _render_schedule_snapshot()
        return

    top_cols = st.columns(4)
    top_cols[0].metric("Total Runs", len(records))
    top_cols[1].metric(
        "Campaign Runs",
        sum(1 for row in records if str(row.get("mode", "")).strip() == "campaign_generation"),
    )
    top_cols[2].metric(
        "Simple Queries",
        sum(1 for row in records if str(row.get("mode", "")).strip() == "simple_query"),
    )
    top_cols[3].metric("Errors", sum(1 for row in records if bool(str(row.get("error", "")).strip())))

    filter_cols = st.columns(4)
    request_filter = filter_cols[0].text_input("Filter request", value="")
    brand_filter = filter_cols[1].text_input("Filter brand", value="")
    campaign_filter = filter_cols[2].text_input("Filter campaign", value="")
    mode_filter = filter_cols[3].selectbox("Mode", ["all", "campaign_generation", "simple_query", "research_planning"])

    filtered: list[dict[str, Any]] = []
    for record in records:
        request = str(record.get("request", ""))
        brand_id = str(record.get("brand_id", ""))
        campaign_id = str(record.get("campaign_id", ""))
        mode = str(record.get("mode", ""))
        if request_filter and request_filter.lower() not in request.lower():
            continue
        if brand_filter and brand_filter.lower() not in brand_id.lower():
            continue
        if campaign_filter and campaign_filter.lower() not in campaign_id.lower():
            continue
        if mode_filter != "all" and mode != mode_filter:
            continue
        filtered.append(record)

    st.caption(f"Showing {len(filtered)} of {len(records)} runs")

    for index, record in enumerate(filtered, start=1):
        finished = str(record.get("finished_at", ""))
        mode = str(record.get("mode", ""))
        status = str(record.get("status", ""))
        request = str(record.get("request", ""))
        heading = f"{finished} | {mode or 'n/a'} | {status or 'n/a'} | {request[:80]}"

        with st.expander(heading, expanded=index == 1):
            st.markdown(
                f"**Brand**: `{record.get('brand_id', '')}`  |  **Campaign**: `{record.get('campaign_id', '')}`  |  "
                f"**Route**: `{record.get('route_decision', '')}`"
            )

            error_text = str(record.get("error", "")).strip()
            if error_text:
                st.error(error_text)

            final_output = record.get("final_output", {})
            if isinstance(final_output, dict):
                if final_output.get("mode") == "simple_query":
                    st.subheader("Query Answer")
                    answer = final_output.get("answer", {})
                    if isinstance(answer, dict) and answer:
                        st.json(answer)
                    else:
                        st.info("No structured answer payload returned.")
                else:
                    _render_non_image_output(final_output)
                    st.subheader("Campaign Assets")
                    approved_assets = final_output.get("approved_assets", [])
                    if isinstance(approved_assets, list):
                        valid_assets = [item for item in approved_assets if isinstance(item, dict)]
                        if valid_assets:
                            _render_asset_gallery(valid_assets, f"history_{index}")
                        else:
                            st.info("No image assets were generated in this run.")
                with st.expander("Final Output JSON", expanded=False):
                    st.json(final_output)

            with st.expander("Execution Events", expanded=False):
                events = record.get("events", [])
                if isinstance(events, list):
                    st.json(events)

    st.subheader("Current Schedule Snapshot")
    _render_schedule_snapshot()


def _render_editor_page(settings: Settings, graph: Any) -> None:
    st.markdown("## Workflow Editor")

    control_col, canvas_col = st.columns([0.30, 0.70], gap="large")

    with control_col:
        st.markdown("### Run Controls")
        brand_id = st.text_input("Brand ID", value=settings.default_brand_id)
        campaign_id = st.text_input("Campaign ID", value=settings.default_campaign_id)
        request_placeholder = _default_request_placeholder(brand_id.strip() or settings.default_brand_id)
        request = st.text_area(
            "Request",
            value="",
            placeholder=request_placeholder,
            height=120,
        )
        reflect = st.checkbox("Run reflection", value=False)

        st.markdown("### Nano Banana Inputs")
        uploaded_subject_files = st.file_uploader(
            "Subject images",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            help="Uploaded files will be saved under data/subject_uploads/<campaign_id>/ and passed as subject images.",
        )
        subject_labels_text = st.text_area(
            "Subject labels (optional, comma/newline)",
            value="",
            height=70,
        )
        image_elements_text = st.text_area(
            "Required elements (comma/newline)",
            value="",
            height=70,
        )

        st.markdown("### Runtime")
        include_campaign_state_in_planner = st.checkbox(
            "Include campaign state in planner context",
            value=True,
        )
        trace_file = st.text_input("Trace file", value=DEFAULT_TRACE_FILE)
        run_clicked = st.button("Execute Workflow", type="primary", use_container_width=True)
        reload_clicked = st.button("Reload Runtime Graph", use_container_width=True)

        if reload_clicked:
            st.cache_resource.clear()
            st.rerun()

    with canvas_col:
        canvas_placeholder = st.empty()
        log_placeholder = st.empty()
        result_placeholder = st.empty()

        current_state = st.session_state.get("frontend_last_state", {})
        current_status = st.session_state.get("frontend_node_status", _initial_node_status())
        current_events = st.session_state.get("frontend_events", [])

        def _draw_live_panels(
            events: list[dict[str, Any]],
            status_map: dict[str, str],
            state: dict[str, Any],
            active_node: str,
        ) -> None:
            with canvas_placeholder.container():
                _render_canvas(status_map, active_node, state)
            with log_placeholder.container():
                st.markdown("### Live Event Feed")
                _render_event_feed(events)

        _draw_live_panels(
            current_events if isinstance(current_events, list) else [],
            current_status if isinstance(current_status, dict) else _initial_node_status(),
            current_state if isinstance(current_state, dict) else {},
            "",
        )

        if run_clicked:
            if not request.strip():
                st.error("Request is required.")
                return

            subject_specs = _persist_subject_uploads(uploaded_subject_files or [], campaign_id)
            subject_labels = _split_values(subject_labels_text)
            image_elements = _split_values(image_elements_text)
            if not subject_labels and subject_specs:
                subject_labels = [str(spec.get("name", "")) for spec in subject_specs if spec.get("name")]

            input_state: dict[str, Any] = {
                "request": request,
                "brand_id": brand_id.strip() or settings.default_brand_id,
                "campaign_id": campaign_id.strip() or settings.default_campaign_id,
                "run_reflection": reflect,
                "include_campaign_state_in_planner": include_campaign_state_in_planner,
                "image_subjects": subject_labels,
                "image_elements": image_elements,
                "image_subject_files": subject_specs,
            }

            node_status = _initial_node_status()
            started_at = _now_iso()

            def _on_update(
                events: list[dict[str, Any]],
                status_map: dict[str, str],
                state: dict[str, Any],
                active_node: str,
            ) -> None:
                _draw_live_panels(events, status_map, state, active_node)

            with st.spinner("Workflow running..."):
                final_state, events, error_text = _stream_workflow(
                    graph=graph,
                    input_state=input_state,
                    status_map=node_status,
                    on_update=_on_update,
                    trace_file=trace_file,
                )
            finished_at = _now_iso()
            _save_run_record(
                started_at=started_at,
                finished_at=finished_at,
                input_state=input_state,
                final_state=final_state,
                events=events,
                error_text=error_text,
            )

            st.session_state["frontend_last_state"] = final_state
            st.session_state["frontend_events"] = events
            st.session_state["frontend_node_status"] = node_status

            with result_placeholder.container():
                st.markdown("### Final Output")
                if error_text:
                    st.error(error_text)
                _render_final_output_section(final_state, events)
        else:
            previous_state = st.session_state.get("frontend_last_state", {})
            previous_events = st.session_state.get("frontend_events", [])
            if previous_state:
                with result_placeholder.container():
                    st.markdown("### Final Output")
                    _render_final_output_section(previous_state, previous_events if isinstance(previous_events, list) else [])

def _inject_styles() -> None:
    st.markdown(
        textwrap.dedent(
            """
        <style>
        :root {
          --wf-bg-page: #f3f8ff;
          --wf-bg-sidebar: #edf4ff;
          --wf-bg-surface: #ffffff;
          --wf-bg-soft: #eef5ff;
          --wf-bg-canvas-top: #f8fbff;
          --wf-bg-canvas-bottom: #eaf2ff;
          --wf-text-strong: #102a4a;
          --wf-text-mid: #2d4f77;
          --wf-text-soft: #5b7da6;
          --wf-border: #c7d9ef;
          --wf-border-strong: #a8c4e6;
          --wf-accent: #1f63c7;
          --wf-accent-strong: #174f9f;
          --wf-accent-soft: #e7f0ff;
          --wf-shadow: 0 10px 24px rgba(26, 73, 135, 0.10);
          --wf-shadow-soft: 0 2px 8px rgba(26, 73, 135, 0.08);
        }

        html, body, [data-testid="stAppViewContainer"], .stApp {
          background: var(--wf-bg-page);
          color: var(--wf-text-strong);
          font-family: "Aptos", "Trebuchet MS", "Segoe UI", "Tahoma", sans-serif;
          line-height: 1.45;
        }

        [data-testid="stHeader"] {
          background: var(--wf-bg-page);
        }

        [data-testid="stSidebar"] {
          background: var(--wf-bg-sidebar);
          border-right: 1px solid var(--wf-border);
        }

        [data-baseweb="radio"] label,
        [data-baseweb="radio"] label * {
          color: var(--wf-text-mid) !important;
          font-weight: 600 !important;
        }

        .stTextInput input, .stTextArea textarea, .stFileUploader, .stSelectbox div[data-baseweb="select"] > div {
          background: var(--wf-bg-surface) !important;
          color: var(--wf-text-strong) !important;
          border-color: var(--wf-border) !important;
        }

        [data-testid="stTextInput"] label p,
        [data-testid="stTextArea"] label p,
        [data-testid="stFileUploader"] label p,
        [data-testid="stCheckbox"] label p,
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li {
          color: var(--wf-text-mid) !important;
          font-size: 15px !important;
        }

        [data-testid="stMarkdownContainer"] h1,
        [data-testid="stMarkdownContainer"] h2,
        [data-testid="stMarkdownContainer"] h3 {
          color: var(--wf-text-strong) !important;
        }

        [data-testid="stButton"] > button {
          border: 1px solid var(--wf-border-strong) !important;
          background: var(--wf-bg-surface) !important;
          color: var(--wf-text-mid) !important;
          border-radius: 10px !important;
          font-weight: 700 !important;
          transition: all 0.15s ease !important;
          box-shadow: var(--wf-shadow-soft) !important;
        }

        [data-testid="stButton"] > button:hover {
          border-color: var(--wf-accent) !important;
          background: var(--wf-accent-soft) !important;
          color: var(--wf-accent-strong) !important;
        }

        [data-testid="stButton"] > button[kind="primary"],
        [data-testid="stButton"] > button[data-testid="baseButton-primary"] {
          background: var(--wf-accent) !important;
          color: #ffffff !important;
          border-color: var(--wf-accent) !important;
        }

        [data-testid="stButton"] > button[kind="primary"]:hover,
        [data-testid="stButton"] > button[data-testid="baseButton-primary"]:hover {
          background: var(--wf-accent-strong) !important;
          border-color: var(--wf-accent-strong) !important;
          color: #ffffff !important;
        }

        [data-testid="stFileUploaderDropzone"] {
          background: var(--wf-bg-surface) !important;
          border: 1px dashed var(--wf-border-strong) !important;
          border-radius: 12px !important;
        }

        [data-testid="stFileUploaderDropzone"] * {
          color: var(--wf-text-mid) !important;
        }

        [data-testid="stFileUploader"] {
          color: var(--wf-text-mid) !important;
        }

        [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] {
          background: #f5f9ff !important;
          border: 1px solid var(--wf-border) !important;
          border-radius: 8px !important;
        }

        [data-testid="stFileUploader"] [data-testid="stFileUploaderFileName"],
        [data-testid="stFileUploader"] [data-testid="stFileUploaderFileSize"],
        [data-testid="stFileUploader"] [data-testid="stFileUploaderDeleteBtn"],
        [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] * {
          color: var(--wf-text-mid) !important;
        }

        [data-testid="stAlert"] {
          border-radius: 10px !important;
        }

        .stCheckbox label, .stMarkdown p, .stMarkdown li, .stCaption {
          color: var(--wf-text-mid) !important;
        }

        .wf-header-strip {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 12px;
          margin-bottom: 10px;
        }

        .wf-header-left, .wf-header-right {
          display: flex;
          align-items: center;
          gap: 10px;
          flex-wrap: wrap;
        }

        .wf-pill {
          display: inline-flex;
          align-items: center;
          border-radius: 999px;
          padding: 6px 12px;
          background: var(--wf-accent);
          color: #ffffff;
          font-size: 12px;
          font-weight: 700;
          letter-spacing: 0.03em;
        }

        .wf-pill.muted {
          background: var(--wf-accent-soft);
          color: var(--wf-text-mid);
          font-weight: 500;
        }

        .wf-meta {
          border: 1px solid var(--wf-border);
          border-radius: 10px;
          padding: 5px 10px;
          font-size: 12px;
          color: var(--wf-text-mid);
          background: var(--wf-bg-surface);
        }

        .wf-legend {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
          margin-bottom: 8px;
        }

        .wf-legend-chip {
          font-size: 11px;
          border-radius: 999px;
          border: 1px solid;
          padding: 3px 10px;
          letter-spacing: 0.04em;
          text-transform: uppercase;
        }

        .wf-legend-chip.pending { color: #1f63c7; border-color: #9fc1ea; background: #eaf2ff; }
        .wf-legend-chip.running { color: #1f63c7; border-color: #9fc1ea; background: #eaf2ff; }
        .wf-legend-chip.done { color: #1f8c5d; border-color: #9ad2b5; background: #ebfff4; }
        .wf-legend-chip.skipped { color: #9b7800; border-color: #e2cc85; background: #fff9e8; }
        .wf-legend-chip.error { color: #c43e4c; border-color: #e8b9c0; background: #fff2f4; }

        .wf-meta-row {
          display: flex;
          justify-content: space-between;
          gap: 10px;
          color: var(--wf-text-soft);
          font-size: 12px;
          margin-bottom: 8px;
          flex-wrap: wrap;
        }

        .wf-scroll {
          overflow-x: auto;
          border-radius: 16px;
          border: 1px solid var(--wf-border);
          background: var(--wf-bg-soft);
          box-shadow: inset 0 0 0 1px #d8e5f7, var(--wf-shadow);
        }

        .wf-canvas {
          position: relative;
          width: 3100px;
          height: 640px;
          background:
            radial-gradient(circle at 1px 1px, rgba(96, 140, 198, 0.20) 1px, transparent 0) 0 0 / 18px 18px,
            linear-gradient(180deg, var(--wf-bg-canvas-top) 0%, var(--wf-bg-canvas-bottom) 100%);
        }

        .wf-svg {
          position: absolute;
          inset: 0;
          width: 100%;
          height: 100%;
          pointer-events: none;
        }

        .wf-edge {
          stroke: #89a9cf;
          stroke-width: 2;
          fill: none;
          opacity: 0.65;
        }

        .wf-edge.on {
          stroke: var(--wf-accent);
          opacity: 0.95;
        }

        .wf-edge.dashed {
          stroke-dasharray: 6 5;
        }

        .wf-edge-label {
          fill: var(--wf-text-soft);
          font-size: 12px;
          font-family: "IBM Plex Mono", monospace;
        }

        .wf-node {
          position: absolute;
          width: 190px;
          min-height: 88px;
          border-radius: 14px;
          padding: 10px 12px 12px;
          border: 1px solid var(--wf-border);
          background: rgba(255, 255, 255, 0.98);
          color: var(--wf-text-strong);
          box-shadow: var(--wf-shadow);
          backdrop-filter: blur(4px);
        }

        .wf-node.active {
          box-shadow: 0 0 0 1px var(--wf-accent), 0 0 18px rgba(31, 99, 199, 0.22);
          animation: wfPulse 1.25s ease-in-out infinite;
        }

        @keyframes wfPulse {
          0% { transform: translateY(0px); }
          50% { transform: translateY(-2px); }
          100% { transform: translateY(0px); }
        }

        .wf-node.pending { border-color: #7eaedd; background: #edf5ff; }
        .wf-node.running { border-color: #7eaedd; background: #edf5ff; }
        .wf-node.done { border-color: #84c9a5; background: #edfff5; }
        .wf-node.skipped { border-color: #e4cc7d; background: #fff9e8; }
        .wf-node.error { border-color: #e6a0a9; background: #fff1f3; }

        .wf-node-top {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 8px;
        }

        .wf-node-dot {
          width: 10px;
          height: 10px;
          border-radius: 999px;
          background: #7e99be;
          flex-shrink: 0;
        }

        .wf-node.pending .wf-node-dot { background: #2f7de1; }
        .wf-node.running .wf-node-dot { background: #2f7de1; }
        .wf-node.done .wf-node-dot { background: #1f8c5d; }
        .wf-node.skipped .wf-node-dot { background: #b58900; }
        .wf-node.error .wf-node-dot { background: #df5f6f; }

        .wf-node-title {
          font-size: 14px;
          font-weight: 700;
          letter-spacing: 0.01em;
          line-height: 1.2;
        }

        .wf-node-sub {
          font-size: 12px;
          color: var(--wf-text-soft);
          min-height: 18px;
          margin-bottom: 10px;
        }

        .wf-node-badge {
          display: inline-block;
          font-size: 10px;
          letter-spacing: 0.08em;
          font-family: "IBM Plex Mono", monospace;
          border: 1px solid var(--wf-border);
          border-radius: 999px;
          padding: 2px 8px;
          color: var(--wf-text-mid);
          background: #f4f8ff;
        }

        .wf-node.pending .wf-node-badge,
        .wf-node.running .wf-node-badge {
          color: #1f63c7;
          border-color: #9fc1ea;
          background: #eaf2ff;
        }

        .wf-node.done .wf-node-badge {
          color: #1f8c5d;
          border-color: #9ad2b5;
          background: #ebfff4;
        }

        .wf-node.skipped .wf-node-badge {
          color: #9b7800;
          border-color: #e2cc85;
          background: #fff9e8;
        }

        .wf-node.error .wf-node-badge {
          color: #c43e4c;
          border-color: #e8b9c0;
          background: #fff2f4;
        }

        .wf-log-box {
          border: 1px solid var(--wf-border);
          border-radius: 14px;
          background: var(--wf-bg-surface);
          padding: 10px;
          max-height: 380px;
          overflow-y: auto;
        }

        .wf-log-row {
          display: grid;
          grid-template-columns: 72px 190px 88px 1fr;
          gap: 8px;
          align-items: center;
          border-bottom: 1px solid #deebf9;
          padding: 7px 3px;
          font-size: 12px;
        }

        .wf-log-row:last-child {
          border-bottom: none;
        }

        .wf-log-time {
          color: var(--wf-text-soft);
          font-family: "IBM Plex Mono", monospace;
        }

        .wf-log-node {
          color: var(--wf-text-strong);
          font-weight: 600;
        }

        .wf-log-status {
          font-family: "IBM Plex Mono", monospace;
          text-transform: uppercase;
          font-size: 11px;
        }

        .wf-log-status.done { color: #1f8c5d; }
        .wf-log-status.running { color: #1f63c7; }
        .wf-log-status.skipped { color: #9b7800; }
        .wf-log-status.error { color: #c43e4c; }
        .wf-log-status.info { color: var(--wf-text-soft); }

        .wf-log-keys {
          color: var(--wf-text-mid);
          overflow-wrap: anywhere;
        }

        .wf-app-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          border: 1px solid var(--wf-border);
          background: linear-gradient(135deg, #ffffff 0%, #f5f9ff 100%);
          border-radius: 12px 12px 0 0;
          border-bottom-width: 0;
          padding: 18px 22px;
          margin-bottom: 0;
          box-shadow: 0 10px 30px rgba(30, 90, 170, 0.08);
        }

        .wf-app-strip {
          height: 10px;
          border-left: 1px solid var(--wf-border);
          border-right: 1px solid var(--wf-border);
          border-bottom: 1px solid var(--wf-border);
          border-radius: 0 0 12px 12px;
          margin-bottom: 12px;
          background: linear-gradient(90deg, #c8dcff 0%, #d6e6ff 52%, #d6f0ff 100%);
        }

        .wf-app-name {
          font-size: 36px;
          font-weight: 900;
          letter-spacing: 0.015em;
          color: var(--wf-accent-strong);
          margin: 0;
          line-height: 1.1;
          text-shadow: 0 1px 0 #ffffff, 0 10px 20px rgba(31, 99, 199, 0.15);
        }

        .wf-app-subtitle {
          font-size: 13px;
          color: var(--wf-text-soft);
          margin: 4px 0 0 0;
          font-weight: 600;
        }

        .wf-app-nav {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .wf-app-nav-item {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          text-decoration: none;
          font-size: 13px;
          font-weight: 800;
          color: #2f4b73;
          border: 1px solid #b8cdea;
          background: #f2f7ff;
          border-radius: 999px;
          padding: 7px 14px;
          transition: all 140ms ease-in-out;
        }

        .wf-app-nav-item:hover {
          color: #1f63c7;
          border-color: #8db3e5;
          background: #e8f1ff;
        }

        .wf-app-nav-item.active {
          color: #ffffff;
          border-color: #1f63c7;
          background: linear-gradient(135deg, #1f63c7 0%, #2f7de1 100%);
          box-shadow: 0 6px 16px rgba(31, 99, 199, 0.25);
        }
        </style>
        """
        ).strip(),
        unsafe_allow_html=True,
    )


def _resolve_page() -> str:
    raw_page: Any = st.query_params.get("page", "workflow_editor")
    if isinstance(raw_page, list):
        page_value = str(raw_page[0]) if raw_page else "workflow_editor"
    else:
        page_value = str(raw_page)
    normalized = page_value.strip().lower().replace("-", "_")
    if normalized in {"output", "outputs", "run_outputs"}:
        return "output"
    return "workflow_editor"


def main() -> None:
    st.set_page_config(
        page_title="Multiagent Marketing Workflow",
        layout="wide",
    )
    _inject_styles()

    settings, graph = _load_runtime_graph()
    page = _resolve_page()
    editor_class = "wf-app-nav-item active" if page == "workflow_editor" else "wf-app-nav-item"
    output_class = "wf-app-nav-item active" if page == "output" else "wf-app-nav-item"

    st.markdown(
        textwrap.dedent(
            f"""
        <div class="wf-app-header">
          <div>
            <p class="wf-app-name">Maker'Sense</p>
            <p class="wf-app-subtitle">Multiagent Campaign Workspace</p>
          </div>
          <div class="wf-app-nav">
            <a class="{editor_class}" href="?page=workflow_editor">Workflow Editor</a>
            <a class="{output_class}" href="?page=output">Output</a>
          </div>
        </div>
        <div class="wf-app-strip"></div>
        """
        ).strip(),
        unsafe_allow_html=True,
    )

    if page == "workflow_editor":
        _render_editor_page(settings=settings, graph=graph)
    else:
        _render_run_outputs_page()


if __name__ == "__main__":
    main()


