from uuid import UUID

from app.models.nutrition import ActivityLevel, Gender
from pydantic import BaseModel, Field


class CreateProfileRequest(BaseModel):
    age: int = Field(ge=10, le=120)
    gender: Gender
    height_cm: float = Field(gt=0)
    weight_kg: float = Field(gt=0)
    activity_level: ActivityLevel


class UpdateProfileRequest(BaseModel):
    age: int = Field(ge=10, le=120)
    gender: Gender
    height_cm: float = Field(gt=0)
    weight_kg: float = Field(gt=0)
    activity_level: ActivityLevel


class ProfileResponse(BaseModel):
    id: UUID
    age: int
    gender: Gender
    height_cm: float
    weight_kg: float
    activity_level: ActivityLevel


class UpdateProfileResponse(BaseModel):
    profile: ProfileResponse
    goal_recalculation_needed: bool
