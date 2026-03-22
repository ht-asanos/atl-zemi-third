"""レシピ評価スキーマ"""

from uuid import UUID

from pydantic import BaseModel, Field


class RateRecipeRequest(BaseModel):
    recipe_id: UUID
    rating: int = Field(ge=-1, le=1)  # -1=👎, 0=リセット(DELETE), 1=👍


class RecipeRatingResponse(BaseModel):
    recipe_id: UUID
    rating: int


class UserRatingsResponse(BaseModel):
    ratings: list[RecipeRatingResponse]
