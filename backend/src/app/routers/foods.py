from uuid import UUID

from app.dependencies.auth import get_current_user_id
from app.dependencies.supabase_client import get_authenticated_supabase
from app.models.food import FoodItem
from app.repositories import food_repo, mext_food_repo
from app.schemas.recipe import MextFoodResponse
from fastapi import APIRouter, Depends, Query

from supabase import AsyncClient

router = APIRouter(prefix="/foods", tags=["foods"])


@router.get("/staples", response_model=list[FoodItem])
async def get_staple_foods(
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> list[FoodItem]:
    return await food_repo.get_staple_foods(supabase)


@router.get("/mext/search", response_model=list[MextFoodResponse])
async def search_mext_foods(
    q: str = Query(..., min_length=1),
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> list[MextFoodResponse]:
    """MEXT 食品名を検索する（DB キャッシュから）。"""
    foods = await mext_food_repo.search_by_name(supabase, q)
    return [MextFoodResponse(**f.model_dump()) for f in foods]
