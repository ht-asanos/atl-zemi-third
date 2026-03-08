from uuid import UUID

from app.models.nutrition import Goal
from pydantic import BaseModel


class CreateGoalRequest(BaseModel):
    goal_type: Goal


class GoalResponse(BaseModel):
    id: UUID
    goal_type: Goal
    target_kcal: float
    protein_g: float
    fat_g: float
    carbs_g: float
