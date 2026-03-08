"""管理者用エンドポイント（食材マッチングレビュー）"""

from uuid import UUID

from app.dependencies.auth import get_admin_user_id
from app.dependencies.supabase_client import get_service_supabase
from app.repositories import mext_food_repo, recipe_repo
from app.schemas.admin import (
    MextFoodSearchItem,
    MextFoodSearchResponse,
    ReviewIngredientItem,
    ReviewListResponse,
    ReviewUpdateRequest,
)
from app.services.ingredient_matcher import calculate_recipe_nutrition
from fastapi import APIRouter, Depends, HTTPException, Query, status

from supabase import AsyncClient

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/review/ingredients", response_model=ReviewListResponse)
async def list_review_ingredients(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user_id=Depends(get_admin_user_id),
    supabase: AsyncClient = Depends(get_service_supabase),
) -> ReviewListResponse:
    """レビュー対象の食材一覧を取得する。"""
    rows, total = await recipe_repo.get_ingredients_for_review(supabase, page, per_page)

    items = []
    for row in rows:
        recipe_data = row.get("recipes") or {}
        mext_data = row.get("mext_foods") or {}
        items.append(
            ReviewIngredientItem(
                id=row["id"],
                recipe_id=row["recipe_id"],
                recipe_title=recipe_data.get("title", ""),
                ingredient_name=row["ingredient_name"],
                amount_text=row.get("amount_text"),
                current_mext_food_id=row.get("mext_food_id"),
                current_mext_food_name=mext_data.get("name"),
                match_confidence=row.get("match_confidence"),
                manual_review_needed=row.get("manual_review_needed", False),
                is_nutrition_calculated=recipe_data.get("is_nutrition_calculated", False),
            )
        )

    return ReviewListResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/mext-foods/search", response_model=MextFoodSearchResponse)
async def search_mext_foods(
    q: str = Query(..., min_length=1),
    user_id=Depends(get_admin_user_id),
    supabase: AsyncClient = Depends(get_service_supabase),
) -> MextFoodSearchResponse:
    """MEXT 食品をキーワード検索する。"""
    foods = await mext_food_repo.search_by_name(supabase, q)
    items = [
        MextFoodSearchItem(
            id=f.id,
            mext_food_id=f.mext_food_id,
            name=f.name,
            category_name=f.category_name,
            kcal_per_100g=f.kcal_per_100g,
            protein_g_per_100g=f.protein_g_per_100g,
        )
        for f in foods
        if f.id is not None
    ]
    return MextFoodSearchResponse(items=items)


@router.patch("/review/ingredients/{ingredient_id}")
async def update_review_ingredient(
    ingredient_id: UUID,
    body: ReviewUpdateRequest,
    user_id=Depends(get_admin_user_id),
    supabase: AsyncClient = Depends(get_service_supabase),
) -> dict:
    """食材マッチを更新・承認・却下する。"""
    if body.approved:
        mext_food_id = body.mext_food_id
        confidence = 1.0
        review_needed = False
    else:
        mext_food_id = None
        confidence = 0.0
        review_needed = False

    recipe_id = await recipe_repo.update_ingredient_match(
        supabase, ingredient_id, mext_food_id, confidence, review_needed
    )
    if recipe_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingredient not found",
        )

    # 栄養再計算
    await calculate_recipe_nutrition(supabase, recipe_id)

    return {"ok": True, "recipe_id": str(recipe_id)}
