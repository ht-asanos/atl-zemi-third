"""レシピ更新・backfill 共通サービス

CLI (data_loader.py) と API (routers/recipes.py) の両方から呼び出す。
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from app.models.food import NutritionStatus
from app.repositories import mext_food_repo, recipe_repo
from app.schemas.recipe import BackfillResult, RefreshResult
from app.services.ingredient_matcher import (
    NEGLIGIBLE_INGREDIENTS,
    _normalize_for_mext,
    calculate_recipe_nutrition,
    match_ingredient,
    match_recipe_ingredients,
    parse_ingredient_text,
)
from app.services.mext_scraper import search_foods_by_name
from app.services.nutrition_fallback import get_fallback_nutrition
from app.services.rakuten_recipe import fetch_multiple_categories
from app.services.recipe_quality_gate import filter_meal_like_recipes
from app.services.shopping_normalizer import normalize_ingredient_candidates

from supabase import AsyncClient

logger = logging.getLogger(__name__)


async def _upsert_and_match_recipes(
    supabase: AsyncClient,
    recipes: list[dict],
) -> tuple[int, list[str]]:
    """レシピ upsert + 食材マッチング + 栄養計算。(更新件数, エラーリスト) を返す。"""
    updated = 0
    errors: list[str] = []
    for r in recipes:
        try:
            rid = await recipe_repo.upsert_recipe(supabase, r)
            ingredients = r.get("ingredients", [])
            if ingredients:
                await match_recipe_ingredients(supabase, rid, ingredients)
                result = await calculate_recipe_nutrition(supabase, rid)
                if result.status == NutritionStatus.FAILED:
                    recipe_obj = await recipe_repo.get_recipe_by_id(supabase, rid)
                    if recipe_obj:
                        fallback = get_fallback_nutrition(recipe_obj)
                        await (
                            supabase.table("recipes")
                            .update(
                                {
                                    "nutrition_per_serving": fallback,
                                    "nutrition_status": NutritionStatus.ESTIMATED.value,
                                }
                            )
                            .eq("id", str(rid))
                            .execute()
                        )
            updated += 1
        except Exception as e:
            errors.append(f"{r.get('title', '?')}: {e}")
    return updated, errors


async def refresh_stale_recipes(
    supabase: AsyncClient,
    http_client: httpx.AsyncClient,
    rakuten_app_id: str,
    rakuten_access_key: str,
    max_age_days: int = 7,
) -> RefreshResult:
    """stale カテゴリのレシピを楽天 API から再取得する。"""
    threshold = (datetime.now(tz=UTC) - timedelta(days=max_age_days)).isoformat()

    resp = await supabase.table("recipes").select("rakuten_category_id").lt("fetched_at", threshold).execute()
    rows: list[dict[str, Any]] = resp.data or []
    old_categories = list({r["rakuten_category_id"] for r in rows if r.get("rakuten_category_id")})

    if not old_categories:
        return RefreshResult(
            categories_checked=0,
            categories_refreshed=0,
            recipes_updated=0,
            errors=[],
        )

    fetched_recipes = await fetch_multiple_categories(http_client, rakuten_app_id, rakuten_access_key, old_categories)
    gate = await filter_meal_like_recipes(fetched_recipes)
    recipes = gate.accepted
    # 主食指定なし取込のため is_accompaniment_for_staple() は不適用（Gemini ゲートでカバー）
    logger.info(
        "refresh_stale_recipes quality gate: fetched=%d accepted=%d rejected=%d",
        len(fetched_recipes),
        len(recipes),
        len(gate.rejected),
    )
    updated, errors = await _upsert_and_match_recipes(supabase, recipes)

    return RefreshResult(
        categories_checked=len(old_categories),
        categories_refreshed=len(old_categories),
        recipes_updated=updated,
        errors=errors,
    )


async def backfill_unmatched_ingredients(
    supabase: AsyncClient,
    http_client: httpx.AsyncClient,
) -> BackfillResult:
    """未マッチ食材を MEXT スクレイピングで補完し、再マッチングする。"""
    # 未マッチ食材を取得
    resp = await (
        supabase.table("recipe_ingredients")
        .select("id, recipe_id, ingredient_name, amount_text")
        .is_("mext_food_id", "null")
        .execute()
    )
    rows: list[dict[str, Any]] = resp.data or []
    if not rows:
        return BackfillResult(
            unmatched_before=0,
            scraped_foods=0,
            matched_after=0,
            still_unmatched=0,
            errors=[],
        )

    unmatched_before = len(rows)
    unique_names = list({r["ingredient_name"] for r in rows})

    # MEXT スクレイピング補完
    scraped_foods = 0
    errors: list[str] = []
    for name in unique_names:
        search_name, _ = _normalize_for_mext(name)
        try:
            foods = await search_foods_by_name(http_client, search_name, max_results=3)
            if foods:
                for f in foods:
                    f.raw_data = {**(f.raw_data or {}), "source": "scrape_fallback"}
                count = await mext_food_repo.upsert_foods(supabase, foods)
                scraped_foods += count
        except Exception as e:
            errors.append(f"{name}({search_name}): {e}")

    # 再マッチング
    matched_after = 0
    for row in rows:
        name = row["ingredient_name"]
        amount_text = row.get("amount_text")
        parsed_name, amount_g = parse_ingredient_text(f"{name} {amount_text}" if amount_text else name)
        is_negligible = parsed_name in NEGLIGIBLE_INGREDIENTS
        mext_food_id, confidence = await match_ingredient(supabase, parsed_name)
        update_data: dict[str, Any] = {
            "amount_g": amount_g,
            "is_negligible": is_negligible,
            "manual_review_needed": False if is_negligible else 0.3 <= confidence < 0.6,
        }
        if mext_food_id:
            update_data.update(
                {
                    "mext_food_id": str(mext_food_id),
                    "match_confidence": confidence,
                }
            )
            matched_after += 1
        else:
            update_data["match_confidence"] = confidence
        await supabase.table("recipe_ingredients").update(update_data).eq("id", row["id"]).execute()

    # 栄養再計算
    recipe_ids = list({r["recipe_id"] for r in rows})
    for rid in recipe_ids:
        result = await calculate_recipe_nutrition(supabase, rid)
        if result.status == NutritionStatus.FAILED:
            recipe_obj = await recipe_repo.get_recipe_by_id(supabase, rid)
            if recipe_obj:
                fallback = get_fallback_nutrition(recipe_obj)
                await (
                    supabase.table("recipes")
                    .update(
                        {
                            "nutrition_per_serving": fallback,
                            "nutrition_status": NutritionStatus.ESTIMATED.value,
                        }
                    )
                    .eq("id", str(rid))
                    .execute()
                )

    still_unmatched = unmatched_before - matched_after
    return BackfillResult(
        unmatched_before=unmatched_before,
        scraped_foods=scraped_foods,
        matched_after=matched_after,
        still_unmatched=still_unmatched,
        errors=errors,
    )


async def backfill_missing_normalized_ingredients(
    supabase: AsyncClient,
    http_client: httpx.AsyncClient,
    max_results: int = 3,
) -> dict[str, int | list[str]]:
    """recipe_ingredients 由来の正規化名が mext_foods に存在しない場合、MEXT から補完する。"""
    resp = await supabase.table("recipe_ingredients").select("ingredient_name").execute()
    rows: list[dict[str, Any]] = resp.data or []
    if not rows:
        return {"normalized_names": 0, "added_foods": 0, "missing_names": [], "errors": []}

    normalized_names: set[str] = set()
    for row in rows:
        for candidate in normalize_ingredient_candidates(row.get("ingredient_name", "")):
            if candidate:
                normalized_names.add(candidate)

    added_foods = 0
    missing_names: list[str] = []
    errors: list[str] = []

    for name in sorted(normalized_names):
        existing = await mext_food_repo.search_by_name(supabase, name, limit=1)
        if existing:
            continue
        try:
            foods = await search_foods_by_name(http_client, name, max_results=max_results)
            if not foods:
                missing_names.append(name)
                continue
            for f in foods:
                f.raw_data = {**(f.raw_data or {}), "source": "scrape_fallback"}
            added_foods += await mext_food_repo.upsert_foods(supabase, foods)
        except Exception as e:
            errors.append(f"{name}: {e}")

    return {
        "normalized_names": len(normalized_names),
        "added_foods": added_foods,
        "missing_names": missing_names,
        "errors": errors,
    }
