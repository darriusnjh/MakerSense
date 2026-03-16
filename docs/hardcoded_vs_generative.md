# Hardcoded vs Generative Inventory (MVP)

Last updated: 2026-03-14

This file lists what is currently deterministic/hardcoded vs model-generated, so you can prioritize upgrades.

## Generative (LLM/model-driven)

| Area | What is generative now | Source |
|---|---|---|
| Trend report | `strong_trends`, `emerging_trends`, `rising_entities`, `visual_patterns` | `src/agents/nodes.py` (`trend_agent`), `src/agents/prompts.py`, `src/agents/llm_client.py` |
| Audience report | Pain points, likes/dislikes, segment synthesis | `src/agents/nodes.py` (`audience_agent`) |
| Competitor report | Strategy summary, themes, whitespace, copy-risk notes | `src/agents/nodes.py` (`competitor_agent`) |
| Planner output | Strategic summary, hypotheses, pillars, brief | `src/agents/nodes.py` (`planner_agent`) |
| Creative output | Asset concepts (caption, image prompt, CTA, etc.) | `src/agents/nodes.py` (`creative_agent`) |
| Critic output | Quality score, critique points, proposed learnings | `src/agents/nodes.py` (`critic_agent`, `reflection_agent`) |
| Orchestrator summary text | Rationale narrative object | `src/agents/nodes.py` (`orchestrator_review`) |
| Compliance narrative | `summary`, `top_risks`, `revision_instructions` from compliance LLM call | `src/agents/nodes.py` (`compliance_agent`) |
| Image generation | Gemini image bytes from `gemini-2.5-flash-image` (when key is valid) | `src/services/image_generation.py` |

## Hardcoded / deterministic

| Area | What is hardcoded now | Source |
|---|---|---|
| Graph structure | Fixed node sequence and branch graph | `src/workflow/graph.py` |
| Routing rules | `approved/revise/blocked` thresholds and branch logic | `src/agents/nodes.py` (`orchestrator_review`) |
| Reflection gate | Memory write only if `confidence >= 0.7` and learnings exist | `src/agents/nodes.py` (`memory_commit`) |
| Compliance scoring | Penalty weights and score bands (`0.8`, `0.55`) | `src/services/compliance.py` |
| Scoring formula | Topic/visual/segment weighting (`0.55/0.35/0.10`) and normalization | `src/services/scoring.py` |
| Scheduling cadence | Start `+4h`, then `+12h` intervals, top 3 assets only | `src/services/scheduling.py`, `src/agents/nodes.py` |
| Web query templates | Static query builders for trend/competitor search | `src/agents/nodes.py` |
| Prompt templates | Static prompt strings | `src/agents/prompts.py` |
| Config defaults | Models, max revisions, provider defaults, IDs | `src/config.py` |
| Storage schema | JSON file shapes and key names | `src/storage/json_store.py`, `data/*.json` |
| MCP tool behavior | Mostly direct deterministic wrappers around services | `src/mcp_server.py` |
| Mock mode | Fixed mock payloads when API key is missing | `src/agents/llm_client.py` (`_mock`) |

## Hybrid (both hardcoded and generative)

| Area | Hybrid behavior | Source |
|---|---|---|
| Compliance stage | Deterministic policy score + LLM narrative advice | `src/services/compliance.py`, `src/agents/nodes.py` (`compliance_agent`) |
| Approval stage | Deterministic route decision + LLM orchestrator explanation | `src/agents/nodes.py` (`orchestrator_review`) |
| Creative ranking | LLM-generated assets + deterministic ranking service | `src/agents/nodes.py` (`creative_agent`), `src/services/scoring.py` |
| Reflection learning | LLM learnings + deterministic commit gate/persistence | `src/agents/nodes.py` (`reflection_agent`, `memory_commit`) |

## Priority "work on next" checklist

1. Move hardcoded thresholds/weights into config or policy store (compliance, routing, scoring, scheduling).
2. Enforce `platform_rules` in compliance scoring (currently loaded but not used).
3. Persist compliance outcomes with scheduled assets (not currently written into `schedule.json` payloads).
4. Replace simplistic query builders with retrieval/query planning using brand/campaign context.
5. Add strict structured output validation for all agent responses (Pydantic schema per agent output).
6. Add run-level provenance: save prompts, tool inputs/outputs, and model IDs per node.
7. Add per-agent evaluation metrics and regression tests (quality, policy pass rate, memory quality).
8. Parameterize scheduling strategy (time windows, channel-specific cadence, A/B splits).
9. Add a mode switch for "no mocks in production" and explicit startup validation for required keys.

