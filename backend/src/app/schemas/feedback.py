from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CreateFeedbackRequest(BaseModel):
    plan_id: UUID
    source_text: str = Field(min_length=1, max_length=1000)


class FeedbackTagResponse(BaseModel):
    id: UUID
    tag: str
    source_text: str
    created_at: datetime


class AdaptationResponse(BaseModel):
    tags_applied: list[str]
    changes_summary: list[str]
    extraction_status: Literal["success", "partial", "failed"]
    new_plan: Any | None = None
