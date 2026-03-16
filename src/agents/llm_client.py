from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config import Settings


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._clients: dict[str, ChatOpenAI] = {}

    def _model_for(self, agent_type: str) -> str:
        if agent_type in {"trend", "audience", "competitor"}:
            return self.settings.openai_model_research
        if agent_type == "review":
            return self.settings.openai_model_review
        fallback = self.settings.openai_model_orchestrator
        return self.settings.model_by_agent.get(agent_type, fallback)

    @staticmethod
    def _coerce_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks: list[str] = []
            for block in content:
                if isinstance(block, dict):
                    text = block.get("text") or block.get("content")
                    if text:
                        chunks.append(str(text))
            return "\n".join(chunks)
        return str(content)

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.replace("json", "", 1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(text[start : end + 1])
            raise

    def _repair_json(
        self,
        raw_text: str,
        model: str,
    ) -> dict[str, Any]:
        llm = self._get_client(model)
        repair_message = llm.invoke(
            [
                SystemMessage(
                    content=(
                        "You repair malformed JSON. Return strict JSON only. "
                        "Do not include markdown, explanations, or extra text."
                    )
                ),
                HumanMessage(
                    content=(
                        "Convert this content into valid strict JSON:\n\n"
                        f"{raw_text}\n"
                    )
                ),
            ]
        )
        repaired_text = self._coerce_text(repair_message.content)
        return self._parse_json(repaired_text)

    def _get_client(self, model: str) -> ChatOpenAI:
        client = self._clients.get(model)
        if client is None:
            client = ChatOpenAI(
                model=model,
                api_key=self.settings.openai_api_key,
                temperature=0.2,
                max_retries=2,
            )
            self._clients[model] = client
        return client

    def _mock(self, agent_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        if agent_type == "orchestrator":
            request = str(payload.get("request", "")).lower()
            is_campaign = any(keyword in request for keyword in ("campaign", "creative", "asset", "post", "caption"))
            is_strategy = any(keyword in request for keyword in ("plan", "strategy", "hypothesis", "kpi"))
            is_research = any(
                keyword in request
                for keyword in ("trend", "competitor", "audience", "sentiment", "review", "market")
            )

            if is_campaign:
                mode = "campaign_generation"
                run_planner = True
                run_creative = True
            elif is_strategy:
                mode = "research_planning"
                run_planner = True
                run_creative = False
            elif is_research:
                mode = "simple_query"
                run_planner = False
                run_creative = False
            else:
                mode = "simple_query"
                run_planner = False
                run_creative = False

            run_research = is_campaign or is_strategy or is_research
            return {
                "task_plan": {
                    "mode": mode,
                    "run_trend": run_research,
                    "run_audience": run_research,
                    "run_competitor": run_research,
                    "run_planner": run_planner,
                    "run_creative": run_creative,
                    "run_compliance": run_creative,
                    "run_critic": run_creative,
                    "run_schedule": run_creative,
                },
                "reason": "Mock orchestrator routing used because OPENAI_API_KEY is empty.",
            }
        if agent_type == "trend":
            return {
                "strong_trends": ["educational carousels", "case-study hooks"],
                "emerging_trends": ["AI workflow explainers", "behind-the-scenes demos"],
                "rising_entities": ["automation", "compliance-ready AI"],
                "visual_patterns": ["clean UI screenshots", "annotated dashboards"],
                "confidence_notes": ["Mock response used because OPENAI_API_KEY is empty."],
            }
        if agent_type == "audience":
            return {
                "pain_points": ["hard onboarding", "unclear ROI"],
                "likes": ["concise demos", "practical checklists"],
                "dislikes": ["vague claims", "long intros"],
                "root_causes": ["low trust in generic AI promises"],
                "unanswered_questions": ["How quickly can teams deploy safely?"],
                "segment_insights": {
                    "new_vs_returning": "New users want setup content; returning users want optimization tips.",
                    "intent_split": "High-intent segments respond to case metrics, casual segments to quick wins.",
                    "platform_split": "LinkedIn prefers proof, Instagram prefers visual explainers.",
                },
            }
        if agent_type == "competitor":
            return {
                "strategy_summary": "Competitors lean heavily on speed and automation framing.",
                "recurring_themes": ["AI saves time", "template-driven execution"],
                "oversaturated_angles": ["generic productivity hooks"],
                "whitespace_opportunities": ["compliance-first differentiation", "public-sector case studies"],
                "copy_risk_warnings": ["Avoid '10x faster' style claims used by multiple competitors."],
            }
        if agent_type == "planner":
            return {
                "strategic_summary": "Balance proof-first content with exploratory AI workflow formats.",
                "content_pillars": ["Compliance clarity", "Outcome proof", "Tactical playbooks"],
                "hypotheses": [
                    "Case-study hooks improve saves among returning users.",
                    "Annotated dashboard visuals improve CTR on LinkedIn.",
                ],
                "must_run_assets": ["2 case-study carousels", "1 short demo clip brief"],
                "test_assets": ["hook variants for onboarding pain-point"],
                "optional_exploratory_assets": ["emerging AI workflow meme format"],
                "kpis": ["CTR", "save_rate", "qualified_leads"],
                "creative_brief": {
                    "voice": "Confident and practical",
                    "cta": "Book a workflow walkthrough",
                    "channels": ["LinkedIn", "Instagram"],
                },
            }
        if agent_type == "creative":
            return {
                "assets": [
                    {
                        "asset_id": "asset_001",
                        "pillar": "Outcome proof",
                        "channel": "LinkedIn",
                        "caption": "How one team reduced response times by 38% with compliant AI workflows.",
                        "image_prompt": "Professional dashboard with highlighted response-time trend lines",
                        "cta": "See the full workflow breakdown",
                        "topic_hint": "case study",
                        "visual_hint": "dashboard",
                        "target_segment": "returning_high_intent",
                    },
                    {
                        "asset_id": "asset_002",
                        "pillar": "Compliance clarity",
                        "channel": "Instagram",
                        "caption": "3 policy checks every public-sector AI team should run before launch.",
                        "image_prompt": "Checklist style social graphic with policy icons",
                        "cta": "Get the checklist",
                        "topic_hint": "compliance checklist",
                        "visual_hint": "checklist",
                        "target_segment": "new_high_intent",
                    },
                ]
            }
        if agent_type == "compliance":
            return {
                "recommendation": "approve",
                "summary": "No critical policy issues detected.",
                "top_risks": [],
                "revision_instructions": [],
            }
        if agent_type == "review":
            return {
                "mode": payload.get("mode", "pre_publish"),
                "quality_score": 0.78,
                "critique_points": ["Strengthen differentiation in opening line."],
                "proposed_learnings": ["Dashboard visuals continue to outperform abstract graphics."],
                "confidence": 0.79,
            }
        return {"note": "mock"}

    def run_json(
        self,
        agent_type: str,
        system_prompt: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.settings.openai_api_key:
            return self._mock(agent_type, payload)

        model = self._model_for(agent_type)
        llm = self._get_client(model)
        human_text = (
            "Input JSON:\n"
            f"{json.dumps(payload, indent=2)}\n\n"
            "Return strict JSON only. Do not wrap in markdown fences."
        )
        message = llm.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=human_text)]
        )
        text = self._coerce_text(message.content)
        try:
            return self._parse_json(text)
        except Exception as parse_exc:
            try:
                repaired = self._repair_json(text, model=model)
                if isinstance(repaired, dict):
                    repaired.setdefault(
                        "_warning",
                        "Model output was malformed JSON; repaired via JSON-fix pass.",
                    )
                return repaired
            except Exception:
                fallback = self._mock(agent_type, payload)
                if isinstance(fallback, dict):
                    fallback.setdefault(
                        "_warning",
                        "Model output parsing failed; used fallback response.",
                    )
                    fallback["_parse_error"] = str(parse_exc)
                    return fallback
                raise
