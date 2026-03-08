from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MextFoodResponse(BaseModel):
    id: UUID
    mext_food_id: str
    name: str
    category_code: str
    category_name: str
    kcal_per_100g: float
    protein_g_per_100g: float
    fat_g_per_100g: float
    carbs_g_per_100g: float


class RecipeIngredientResponse(BaseModel):
    ingredient_name: str
    amount_text: str | None = None
    amount_g: float | None = None
    match_confidence: float | None = None


class RecipeResponse(BaseModel):
    id: UUID
    title: str
    description: str | None = None
    image_url: str | None = None
    recipe_url: str
    nutrition_per_serving: dict | None = None
    servings: int = 1
    cooking_minutes: int | None = None
    cost_estimate: str | None = None
    tags: list[str] = []
    is_nutrition_calculated: bool = False
    ingredients: list[RecipeIngredientResponse] = []


class RecipeSearchResponse(BaseModel):
    recipes: list[RecipeResponse]


class RefreshResult(BaseModel):
    categories_checked: int
    categories_refreshed: int
    recipes_updated: int
    errors: list[str]


class BackfillResult(BaseModel):
    unmatched_before: int
    scraped_foods: int
    matched_after: int
    still_unmatched: int
    errors: list[str]


class FavoriteResponse(BaseModel):
    recipe_id: UUID
    created_at: datetime
