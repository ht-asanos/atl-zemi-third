from datetime import date
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel


class ShoppingListItem(BaseModel):
    ingredient_name: str
    mext_food_id: UUID | None = None
    amount_text: str | None = None
    amount_g: float | None = None
    category_name: str | None = None
    recipe_titles: list[str]


class ShoppingListResponse(BaseModel):
    start_date: date
    items: list[ShoppingListItem]
    recipe_count: int


class WeeklyPlanRequest(BaseModel):
    start_date: date
    staple_name: str | None = None
    mode: Literal["classic", "recipe"] = "recipe"


class PatchMealRequest(BaseModel):
    staple_name: str


class PlanMeta(BaseModel):
    mode: str | None = None
    staple_name: str | None = None


class DailyPlanResponse(BaseModel):
    id: UUID
    plan_date: date
    meal_plan: Any
    workout_plan: Any
    plan_meta: PlanMeta | None = None


class WeeklyPlanResponse(BaseModel):
    plans: list[DailyPlanResponse]
