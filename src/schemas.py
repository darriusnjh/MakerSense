from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TopicCluster(BaseModel):
    topic_id: str
    label: str
    keywords: list[str]
    growth_rate: float = Field(ge=-1.0)
    engagement_rate: float = Field(ge=0.0)


class VisualCluster(BaseModel):
    visual_cluster_id: str
    style: str
    motifs: list[str]
    growth_rate: float = Field(ge=-1.0)
    engagement_rate: float = Field(ge=0.0)


class EntityTrend(BaseModel):
    entity: str
    category: str
    mention_count: int = Field(ge=0)
    growth_rate: float = Field(ge=-1.0)


class CommentSignal(BaseModel):
    comment_id: str
    platform: str
    segment: str
    sentiment: Literal["positive", "neutral", "negative"]
    text: str
    extracted_topics: list[str]


class CompetitorPost(BaseModel):
    post_id: str
    competitor: str
    platform: str
    hook: str
    theme: str
    offer: str
    performance_index: float = Field(ge=0.0)


class SegmentMetric(BaseModel):
    segment: str
    ctr: float = Field(ge=0.0)
    saves_rate: float = Field(ge=0.0)
    conversion_rate: float = Field(ge=0.0)


class CandidateAsset(BaseModel):
    asset_id: str
    pillar: str
    channel: str
    caption: str
    image_prompt: str
    cta: str
    topic_hint: str | None = None
    visual_hint: str | None = None


class ScoredCandidate(BaseModel):
    asset_id: str
    topic_cluster_id: str
    visual_cluster_id: str
    predicted_ctr: float = Field(ge=0.0)
    score: float = Field(ge=0.0, le=1.0)
    rationale: str


class ComplianceResult(BaseModel):
    asset_id: str
    score: float = Field(ge=0.0, le=1.0)
    recommendation: Literal["approve", "revise", "block"]
    flags: list[str]
    suggestions: list[str]


class ScheduledPost(BaseModel):
    campaign_id: str
    asset_id: str
    channel: str
    scheduled_for: datetime
    payload: dict

