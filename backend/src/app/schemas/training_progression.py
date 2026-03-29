from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class TrainingProgressionExtractedEdge(BaseModel):
    from_label: str
    from_reps: int = Field(ge=1)
    to_label: str
    to_reps: int = Field(ge=1)
    evidence_text: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class TrainingProgressionSourceResponse(BaseModel):
    id: UUID
    platform: str
    channel_handle: str
    channel_id: str | None = None
    video_id: str
    video_title: str
    video_url: str
    published_at: datetime | None = None
    title_query: str | None = None
    transcript_language: str | None = None
    transcript_quality_json: dict[str, Any] = Field(default_factory=dict)
    ingest_status: str
    raw_extraction_json: Any | None = None
    created_at: datetime


class TrainingProgressionEdgeResponse(BaseModel):
    id: UUID
    source_id: UUID
    from_label_raw: str
    from_exercise_id: str | None = None
    from_reps: int
    to_label_raw: str
    to_exercise_id: str | None = None
    to_reps: int
    relation_type: str
    goal_scope: list[str] = Field(default_factory=list)
    evidence_text: str | None = None
    confidence: float = 0.0
    review_status: str
    review_note: str | None = None
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    created_at: datetime


class TrainingProgressionPresetReview(BaseModel):
    from_exercise_id: str
    from_reps: int = Field(ge=1)
    to_exercise_id: str
    to_reps: int = Field(ge=1)
    goal_scope: list[str] = Field(default_factory=list)
    review_note: str | None = None
    add_aliases: list[str] = Field(default_factory=list)


class TrainingProgressionReviewItem(BaseModel):
    edge: TrainingProgressionEdgeResponse
    source: TrainingProgressionSourceResponse
    preset_review: TrainingProgressionPresetReview | None = None


class TrainingProgressionIngestRequest(BaseModel):
    channel_handle: str = "@CalisthenicsTokyo"
    title_keyword: str = "ができるなら"
    max_results: int = Field(default=25, ge=1, le=100)


class TrainingProgressionIngestVideoResult(BaseModel):
    video_id: str
    video_title: str
    status: str
    source_id: str | None = None
    edges_created: int = 0
    error: str | None = None


class TrainingProgressionIngestResponse(BaseModel):
    channel_handle: str
    title_keyword: str
    videos_found: int
    videos_scanned: int = 0
    videos_title_matched: int = 0
    videos_processed: int
    transcripts_fetched: int = 0
    transcripts_naturalized: int = 0
    videos_with_edges: int = 0
    edges_created: int
    results: list[TrainingProgressionIngestVideoResult]


class TrainingProgressionReviewActionRequest(BaseModel):
    review_status: Literal["approved", "rejected"]
    from_exercise_id: str | None = None
    from_reps: int | None = Field(default=None, ge=1)
    to_exercise_id: str | None = None
    to_reps: int | None = Field(default=None, ge=1)
    goal_scope: list[str] | None = None
    review_note: str | None = None
    add_aliases: list[str] = Field(default_factory=list)


class TrainingProgressionReviewListResponse(BaseModel):
    items: list[TrainingProgressionReviewItem]
    total: int


class TrainingProgressionSourceListResponse(BaseModel):
    items: list[TrainingProgressionSourceResponse]
    total: int


class TrainingProgressionApplyPresetsResponse(BaseModel):
    reviewed: int
    skipped: int


class TrainingSkillTreeNode(BaseModel):
    exercise_id: str
    name_ja: str
    required_equipment: list[str] = Field(default_factory=list)
    best_completed_reps: int = 0
    status: Literal["locked", "unlocked", "current", "recommended", "mastered", "blocked"]
    next_threshold_reps: int | None = None
    recommendation_reason: str | None = None
    latest_log_summary: dict[str, Any] | None = None
    latest_feedback_summary: dict[str, Any] | None = None


class TrainingSkillTreeEdge(BaseModel):
    from_exercise_id: str
    to_exercise_id: str
    from_reps_required: int
    to_reps_target: int
    is_recommended_path: bool = False


class TrainingSkillTreeTrack(BaseModel):
    track_id: str
    title: str
    nodes: list[TrainingSkillTreeNode]
    edges: list[TrainingSkillTreeEdge]


class TrainingSkillTreeSummary(BaseModel):
    goal_type: str
    available_edge_count: int = 0
    recommended_count: int = 0
    has_negative_feedback: bool = False


class TrainingSkillTreeResponse(BaseModel):
    summary: TrainingSkillTreeSummary
    tracks: list[TrainingSkillTreeTrack]


class AdminTrainingProgressionGraphEdge(BaseModel):
    edge_id: UUID
    from_exercise_id: str
    to_exercise_id: str
    from_reps_required: int
    to_reps_target: int
    review_status: str
    video_id: str
    video_title: str
    review_note: str | None = None


class AdminTrainingProgressionGraphNode(BaseModel):
    exercise_id: str
    name_ja: str
    required_equipment: list[str] = Field(default_factory=list)
    review_count: int = 0


class AdminTrainingProgressionGraphTrack(BaseModel):
    track_id: str
    title: str
    nodes: list[AdminTrainingProgressionGraphNode]
    edges: list[AdminTrainingProgressionGraphEdge]


class AdminTrainingProgressionUnmappedEdge(BaseModel):
    edge_id: UUID
    from_label_raw: str
    to_label_raw: str
    from_reps: int
    to_reps: int
    review_status: str
    video_id: str
    video_title: str


class AdminTrainingProgressionGraphSummary(BaseModel):
    status: str
    goal_type: str
    edge_count: int = 0
    track_count: int = 0
    unmapped_edge_count: int = 0


class AdminTrainingProgressionGraphResponse(BaseModel):
    summary: AdminTrainingProgressionGraphSummary
    tracks: list[AdminTrainingProgressionGraphTrack]
    unmapped_edges: list[AdminTrainingProgressionUnmappedEdge] = Field(default_factory=list)
