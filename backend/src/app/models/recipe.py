from uuid import UUID

from app.models.food import NutritionStatus
from pydantic import BaseModel


class RecipeIngredient(BaseModel):
    id: UUID | None = None
    recipe_id: UUID | None = None
    ingredient_name: str
    amount_text: str | None = None
    amount_g: float | None = None
    mext_food_id: UUID | None = None
    match_confidence: float | None = None
    manual_review_needed: bool = False
    kcal: float | None = None
    protein_g: float | None = None
    fat_g: float | None = None
    carbs_g: float | None = None
    matched_food_name: str | None = None
    nutrition_match_status: str = "unmatched"
    nutrition_source: str = "none"
    display_ingredient_name: str | None = None
    alternative_ingredient_names: list[str] = []


class RecipeStep(BaseModel):
    step_no: int
    text: str
    est_minutes: int | None = None


class Recipe(BaseModel):
    id: UUID
    rakuten_recipe_id: int | None = None
    title: str
    description: str | None = None
    image_url: str | None = None
    recipe_url: str
    ingredients: list[RecipeIngredient] = []
    nutrition_per_serving: dict | None = None
    servings: int = 1
    cooking_minutes: int | None = None
    cost_estimate: str | None = None
    tags: list[str] = []
    is_nutrition_calculated: bool = False
    nutrition_status: NutritionStatus = NutritionStatus.CALCULATED
    generated_steps: list[RecipeStep] = []
    steps_status: str = "pending"
    youtube_video_id: str | None = None
    recipe_source: str = "rakuten"
    ingredient_nutrition_coverage: dict[str, float | int] | None = None
