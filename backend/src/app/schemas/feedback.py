from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CreateFeedbackRequest(BaseModel):
    plan_id: UUID
    source_text: str = Field(min_length=1, max_length=1000)
    domain: Literal["meal", "workout", "mixed"] | None = None
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"] | None = None
    exercise_id: str | None = None
    satisfaction: int | None = Field(default=None, ge=1, le=5)
    rpe: float | None = Field(default=None, ge=1, le=10)
    completed: bool | None = None


class FeedbackTagResponse(BaseModel):
    id: UUID
    tag: str
    source_text: str
    created_at: datetime


class FeedbackEventResponse(BaseModel):
    id: UUID
    plan_id: UUID | None
    domain: Literal["meal", "workout", "mixed"]
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"] | None = None
    exercise_id: str | None = None
    source_text: str
    satisfaction: int | None = None
    rpe: float | None = None
    completed: bool | None = None
    created_at: datetime


class FeedbackEventTagResponse(BaseModel):
    id: UUID
    event_id: UUID
    tag: str
    tag_source: Literal["llm", "rule"]
    created_at: datetime


class AdaptationEventResponse(BaseModel):
    id: UUID
    feedback_event_id: UUID
    plan_revision_id: UUID | None = None
    domain: Literal["meal", "workout"]
    target_type: Literal["meal_plan", "recipe_selection", "workout_plan"]
    target_ref: str | None = None
    before_snapshot: Any
    after_snapshot: Any
    change_summary_json: list[str]
    created_at: datetime


class FeedbackEventDetailResponse(FeedbackEventResponse):
    tags: list[FeedbackEventTagResponse] = Field(default_factory=list)
    adaptation_events: list[AdaptationEventResponse] = Field(default_factory=list)


class AdaptationResponse(BaseModel):
    feedback_event_id: UUID | None = None
    adaptation_event_ids: list[UUID] = Field(default_factory=list)
    tags_applied: list[str] = Field(default_factory=list)
    changes_summary: list[str] = Field(default_factory=list)
    extraction_status: Literal["success", "partial", "failed"]
    new_plan: Any | None = None
