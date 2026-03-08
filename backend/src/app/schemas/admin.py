from uuid import UUID

from pydantic import BaseModel


class ReviewIngredientItem(BaseModel):
    id: UUID
    recipe_id: UUID
    recipe_title: str
    ingredient_name: str
    amount_text: str | None = None
    current_mext_food_id: UUID | None = None
    current_mext_food_name: str | None = None
    match_confidence: float | None = None
    manual_review_needed: bool
    is_nutrition_calculated: bool = False


class ReviewListResponse(BaseModel):
    items: list[ReviewIngredientItem]
    total: int
    page: int
    per_page: int


class ReviewUpdateRequest(BaseModel):
    mext_food_id: UUID | None = None
    approved: bool


class MextFoodSearchItem(BaseModel):
    id: UUID
    mext_food_id: str
    name: str
    category_name: str
    kcal_per_100g: float
    protein_g_per_100g: float


class MextFoodSearchResponse(BaseModel):
    items: list[MextFoodSearchItem]
