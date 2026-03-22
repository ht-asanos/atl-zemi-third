from datetime import UTC
from uuid import UUID

import httpx
from app.config import settings
from app.dependencies.auth import get_admin_user_id, get_current_user_id
from app.dependencies.supabase_client import get_authenticated_supabase, get_service_supabase
from app.exceptions import AppException, ErrorCode
from app.repositories import favorite_repo, rating_repo, recipe_repo
from app.schemas.recipe import BackfillResult, FavoriteResponse, RecipeResponse, RecipeSearchResponse, RefreshResult
from app.schemas.recipe_rating import RateRecipeRequest, RecipeRatingResponse, UserRatingsResponse
from app.services.recipe_refresh import backfill_unmatched_ingredients, refresh_stale_recipes
from app.services.recipe_steps import ensure_generated_steps
from fastapi import APIRouter, Depends, HTTPException, Query, status

from supabase import AsyncClient

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.get("/search", response_model=RecipeSearchResponse)
async def search_recipes(
    q: str = Query(..., min_length=1),
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> RecipeSearchResponse:
    """DB キャッシュからレシピを検索する。"""
    recipes = await recipe_repo.search_recipes(supabase, q)
    return RecipeSearchResponse(recipes=[RecipeResponse(**r.model_dump()) for r in recipes])


@router.get("/favorites", response_model=list[FavoriteResponse])
async def get_favorites(
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> list[FavoriteResponse]:
    """お気に入りレシピ一覧を取得する。"""
    rows = await favorite_repo.get_favorites_with_created_at(supabase, user_id)
    return [FavoriteResponse(recipe_id=r["recipe_id"], created_at=r["created_at"]) for r in rows]


@router.get("/{recipe_id}", response_model=RecipeResponse)
async def get_recipe(
    recipe_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> RecipeResponse:
    """レシピ詳細（栄養情報 + 食材付き）を取得する。"""
    recipe = await recipe_repo.get_recipe_by_id(supabase, recipe_id)
    if recipe is None:
        raise AppException(ErrorCode.RECIPE_NOT_FOUND, 404, "Recipe not found")
    recipe = await ensure_generated_steps(supabase, recipe)
    return RecipeResponse(**recipe.model_dump())


@router.post("/refresh", response_model=RefreshResult)
async def refresh_recipes(
    user_id: UUID = Depends(get_admin_user_id),
    supabase: AsyncClient = Depends(get_service_supabase),
) -> RefreshResult:
    """stale レシピを楽天 API から再取得する（管理者限定）。"""
    if not settings.rakuten_app_id or not settings.rakuten_access_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rakuten API keys not configured",
        )
    async with httpx.AsyncClient(timeout=30.0, verify=settings.mext_http_verify_ssl) as http_client:
        return await refresh_stale_recipes(
            supabase,
            http_client,
            settings.rakuten_app_id,
            settings.rakuten_access_key,
        )


@router.post("/{recipe_id}/favorite", status_code=status.HTTP_201_CREATED, response_model=FavoriteResponse)
async def add_favorite(
    recipe_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> FavoriteResponse:
    """レシピをお気に入りに追加する。"""
    recipe = await recipe_repo.get_recipe_by_id(supabase, recipe_id)
    if recipe is None:
        raise AppException(ErrorCode.RECIPE_NOT_FOUND, 404, "Recipe not found")
    await favorite_repo.add_favorite(supabase, user_id, recipe_id)
    rows = await favorite_repo.get_favorites_with_created_at(supabase, user_id)
    for r in rows:
        if str(r["recipe_id"]) == str(recipe_id):
            return FavoriteResponse(recipe_id=r["recipe_id"], created_at=r["created_at"])
    # fallback
    from datetime import datetime

    return FavoriteResponse(recipe_id=recipe_id, created_at=datetime.now(UTC))


@router.delete("/{recipe_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    recipe_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> None:
    """レシピのお気に入りを解除する。"""
    removed = await favorite_repo.remove_favorite(supabase, user_id, recipe_id)
    if not removed:
        raise AppException(ErrorCode.RECIPE_NOT_FOUND, 404, "Favorite not found")


@router.post("/rate", response_model=RecipeRatingResponse)
async def rate_recipe(
    body: RateRecipeRequest,
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> RecipeRatingResponse:
    """レシピを評価する（👍=1, 👎=-1, リセット=0）。"""
    await rating_repo.upsert_rating(supabase, user_id, body.recipe_id, body.rating)
    return RecipeRatingResponse(recipe_id=body.recipe_id, rating=body.rating)


@router.get("/ratings", response_model=UserRatingsResponse)
async def get_ratings(
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> UserRatingsResponse:
    """自分の全評価を取得する。"""
    ratings = await rating_repo.get_ratings_for_user(supabase, user_id)
    return UserRatingsResponse(ratings=[RecipeRatingResponse(recipe_id=rid, rating=r) for rid, r in ratings.items()])


@router.post("/backfill", response_model=BackfillResult)
async def backfill_recipes(
    user_id: UUID = Depends(get_admin_user_id),
    supabase: AsyncClient = Depends(get_service_supabase),
) -> BackfillResult:
    """未マッチ食材を MEXT スクレイピングで補完する（管理者限定）。"""
    async with httpx.AsyncClient(timeout=30.0, verify=settings.mext_http_verify_ssl) as http_client:
        return await backfill_unmatched_ingredients(supabase, http_client)
