from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.agents.llm_client import LLMClient
from src.agents.nodes import AgentRuntime
from src.config import get_settings
from src.services import build_services
from src.storage import build_repository
from src.workflow import build_workflow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the LangGraph multi-agent campaign workflow.")
    parser.add_argument("--request", required=True, help="Campaign request from user.")
    parser.add_argument("--brand-id", default=None, help="Brand ID.")
    parser.add_argument("--campaign-id", default=None, help="Campaign ID.")
    parser.add_argument(
        "--reflect",
        action="store_true",
        help="Run post-performance reflection and memory update loop.",
    )
    parser.add_argument(
        "--realtime",
        action="store_true",
        help="Stream workflow progress in real time.",
    )
    parser.add_argument(
        "--trace-file",
        default="",
        help="Optional path to write JSONL runtime trace events.",
    )
    parser.add_argument(
        "--exclude-campaign-state-from-planner",
        action="store_true",
        help="Do not pass current campaign_state into planner agent context.",
    )
    return parser.parse_args()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _format_keys(payload: Any) -> str:
    if isinstance(payload, dict):
        keys = list(payload.keys())
        return ", ".join(keys) if keys else "(no keys)"
    return "(non-dict payload)"


def _write_trace(trace_path: Path, event: dict[str, Any]) -> None:
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=True) + "\n")


def _stream_workflow(graph, initial_state: dict[str, Any], trace_file: str = "") -> dict[str, Any]:
    merged_state = dict(initial_state)
    trace_path = Path(trace_file) if trace_file else None

    for update in graph.stream(initial_state, stream_mode="updates"):
        ts = _now_iso()
        if not isinstance(update, dict):
            print(f"[{ts}] update: {update}", flush=True)
            if trace_path:
                _write_trace(trace_path, {"ts": ts, "type": "raw_update", "data": str(update)})
            continue

        for node_name, payload in update.items():
            key_text = _format_keys(payload)
            print(f"[{ts}] {node_name} -> updated: {key_text}", flush=True)
            if isinstance(payload, dict):
                merged_state.update(payload)
            if trace_path:
                _write_trace(
                    trace_path,
                    {
                        "ts": ts,
                        "type": "node_update",
                        "node": node_name,
                        "keys": list(payload.keys()) if isinstance(payload, dict) else [],
                        "payload": payload,
                    },
                )

    return merged_state


def main() -> None:
    args = parse_args()
    settings = get_settings()
    repository = build_repository(settings)
    services = build_services(settings, repository)
    runtime = AgentRuntime(settings=settings, services=services, llm=LLMClient(settings))

    graph = build_workflow(runtime)
    input_state = {
        "request": args.request,
        "brand_id": args.brand_id or settings.default_brand_id,
        "campaign_id": args.campaign_id or settings.default_campaign_id,
        "run_reflection": args.reflect,
        "include_campaign_state_in_planner": not args.exclude_campaign_state_from_planner,
    }

    if args.realtime:
        print(f"[{_now_iso()}] realtime workflow started", flush=True)
        if args.trace_file:
            trace_path = Path(args.trace_file)
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            trace_path.write_text("", encoding="utf-8")
            print(f"[{_now_iso()}] writing trace to {trace_path}", flush=True)
        state = _stream_workflow(graph, input_state, trace_file=args.trace_file)
        print(f"[{_now_iso()}] realtime workflow finished", flush=True)
    else:
        state = graph.invoke(input_state)

    print(json.dumps(state.get("final_output", state), indent=2))
    if args.reflect:
        print("\nReflection:")
        print(json.dumps(state.get("reflection_report", {}), indent=2))
        print("\nMemory update:")
        print(json.dumps(state.get("memory_update_result", {}), indent=2))


if __name__ == "__main__":
    main()
