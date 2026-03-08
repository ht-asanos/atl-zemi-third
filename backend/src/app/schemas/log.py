from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CreateMealLogRequest(BaseModel):
    plan_id: UUID
    log_date: date
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"]
    completed: bool
    satisfaction: int | None = Field(default=None, ge=1, le=5)


class MealLogResponse(BaseModel):
    id: UUID
    plan_id: UUID
    log_date: date
    meal_type: str
    completed: bool
    satisfaction: int | None
    created_at: datetime


class CreateWorkoutLogRequest(BaseModel):
    plan_id: UUID
    log_date: date
    exercise_id: str
    sets: int = Field(ge=0)
    reps: int = Field(ge=0)
    rpe: float | None = Field(default=None, ge=1, le=10)
    completed: bool


class WorkoutLogResponse(BaseModel):
    id: UUID
    plan_id: UUID
    log_date: date
    exercise_id: str
    sets: int
    reps: int
    rpe: float | None
    completed: bool
    created_at: datetime
