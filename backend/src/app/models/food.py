from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class FoodCategory(StrEnum):
    STAPLE = "staple"
    PROTEIN = "protein"
    BULK = "bulk"


class MealType(StrEnum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"


class NutritionStatus(StrEnum):
    CALCULATED = "calculated"
    ESTIMATED = "estimated"
    FAILED = "failed"


class FoodItem(BaseModel):
    name: str
    category: FoodCategory
    kcal_per_serving: float
    protein_g: float
    fat_g: float
    carbs_g: float
    serving_unit: str
    price_yen: int = 0
    cooking_minutes: int = 0


class MextFood(BaseModel):
    id: UUID | None = None
    mext_food_id: str
    name: str
    display_name: str | None = None
    category_code: str
    category_name: str
    kcal_per_100g: float
    protein_g_per_100g: float
    fat_g_per_100g: float
    carbs_g_per_100g: float
    fiber_g_per_100g: float | None = None
    sodium_mg_per_100g: float | None = None
    calcium_mg_per_100g: float | None = None
    iron_mg_per_100g: float | None = None
    raw_data: dict = {}


class MealSuggestion(BaseModel):
    meal_type: MealType | None = None
    staple: FoodItem
    protein_sources: list[FoodItem]
    bulk_items: list[FoodItem]
    total_kcal: float
    total_protein_g: float
    total_fat_g: float
    total_carbs_g: float
    total_price_yen: int
    total_cooking_minutes: int
    recipe: Any | None = None
    nutrition_status: NutritionStatus = NutritionStatus.CALCULATED
    nutrition_warning: str | None = None
