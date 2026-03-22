from datetime import date
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class RecipeFilters(BaseModel):
    allowed_sources: list[Literal["rakuten", "youtube"]] = Field(default_factory=lambda: ["rakuten", "youtube"])
    prefer_favorites: bool = True
    exclude_disliked: bool = True
    prefer_variety: bool = True


class ShoppingListItem(BaseModel):
    ingredient_name: str
    group_id: str | None = None
    checked: bool = False
    mext_food_id: UUID | None = None
    amount_text: str | None = None
    amount_g: float | None = None
    category_name: str | None = None
    recipe_titles: list[str]
    is_purchasable: bool = True


class ShoppingListResponse(BaseModel):
    start_date: date
    items: list[ShoppingListItem]
    recipe_count: int


class ShoppingListChecksResponse(BaseModel):
    start_date: date
    checked_group_ids: list[str]


class SetShoppingListCheckRequest(BaseModel):
    start_date: date
    group_id: str
    checked: bool


class WeeklyPlanRequest(BaseModel):
    start_date: date
    staple_name: str | None = None
    mode: Literal["classic", "recipe"] = "recipe"
    recipe_filters: RecipeFilters | None = None


class PatchMealRequest(BaseModel):
    staple_name: str


class PatchRecipeRequest(BaseModel):
    recipe_filters: RecipeFilters | None = None


class PlanMeta(BaseModel):
    mode: str | None = None
    staple_name: str | None = None
    recipe_filters: RecipeFilters | None = None
    validation: dict | None = None
    validation_issues: list[str] | None = None
    duplicate_count: int | None = None
    candidate_pool_size: int | None = None


class DailyPlanResponse(BaseModel):
    id: UUID
    plan_date: date
    meal_plan: Any
    workout_plan: Any
    plan_meta: PlanMeta | None = None


class WeeklyPlanResponse(BaseModel):
    plans: list[DailyPlanResponse]
