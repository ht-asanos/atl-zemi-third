"""recipes テーブル操作"""

import random
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.models.food import NutritionStatus
from app.models.nutrition import PFCBudget
from app.models.recipe import Recipe, RecipeIngredient
from app.utils.text_normalize import contains_normalized

from supabase import AsyncClient


@dataclass
class DinnerSelectionResult:
    recipes: list[Recipe] = field(default_factory=list)
    staple_match_count: int = 0
    total_count: int = 0
    staple_fallback_used: bool = False


def _row_to_recipe(row: dict[str, Any], ingredients: list[dict] | None = None) -> Recipe:
    ings = []
    if ingredients:
        ings = [
            RecipeIngredient(
                id=i.get("id"),
                recipe_id=i.get("recipe_id"),
                ingredient_name=i["ingredient_name"],
                amount_text=i.get("amount_text"),
                amount_g=i.get("amount_g"),
                mext_food_id=i.get("mext_food_id"),
                match_confidence=i.get("match_confidence"),
                manual_review_needed=i.get("manual_review_needed", False),
                kcal=i.get("kcal"),
                protein_g=i.get("protein_g"),
                fat_g=i.get("fat_g"),
                carbs_g=i.get("carbs_g"),
            )
            for i in ingredients
        ]

    return Recipe(
        id=row["id"],
        rakuten_recipe_id=row.get("rakuten_recipe_id"),
        title=row["title"],
        description=row.get("description"),
        image_url=row.get("image_url"),
        recipe_url=row["recipe_url"],
        ingredients=ings,
        nutrition_per_serving=row.get("nutrition_per_serving"),
        servings=row.get("servings", 1),
        cooking_minutes=row.get("cooking_minutes"),
        cost_estimate=row.get("cost_estimate"),
        tags=row.get("tags", []),
        is_nutrition_calculated=row.get("is_nutrition_calculated", False),
        nutrition_status=(
            NutritionStatus(row["nutrition_status"]) if row.get("nutrition_status") else NutritionStatus.CALCULATED
        ),
    )


async def search_recipes(supabase: AsyncClient, query: str, limit: int = 20) -> list[Recipe]:
    """レシピをタイトルで検索する。"""
    response = await supabase.table("recipes").select("*").ilike("title", f"%{query}%").limit(limit).execute()
    rows: list[dict[str, Any]] = response.data or []
    return [_row_to_recipe(r) for r in rows]


async def get_recipe_by_id(supabase: AsyncClient, recipe_id: UUID) -> Recipe | None:
    """レシピ詳細を食材情報付きで取得する。"""
    resp = await supabase.table("recipes").select("*").eq("id", str(recipe_id)).limit(1).execute()
    rows: list[dict[str, Any]] = resp.data or []
    if not rows:
        return None

    ing_resp = await supabase.table("recipe_ingredients").select("*").eq("recipe_id", str(recipe_id)).execute()
    ingredients: list[dict[str, Any]] = ing_resp.data or []
    return _row_to_recipe(rows[0], ingredients)


async def get_recipes_with_nutrition(
    supabase: AsyncClient,
    limit: int = 50,
) -> list[Recipe]:
    """栄養計算済みのレシピ一覧を取得する。"""
    response = await supabase.table("recipes").select("*").eq("is_nutrition_calculated", True).limit(limit).execute()
    rows: list[dict[str, Any]] = response.data or []
    return [_row_to_recipe(r) for r in rows]


async def upsert_recipe(supabase: AsyncClient, recipe_data: dict) -> UUID:
    """レシピを upsert して ID を返す。ingredients は別途処理。"""
    ingredients = recipe_data.pop("ingredients", [])
    record = {k: v for k, v in recipe_data.items() if k != "id"}

    if recipe_data.get("rakuten_recipe_id"):
        response = await supabase.table("recipes").upsert(record, on_conflict="rakuten_recipe_id").execute()
    else:
        response = await supabase.table("recipes").insert(record).execute()

    row = response.data[0]
    recipe_id = row["id"]

    # 既存の食材データを削除して再挿入
    if ingredients:
        await supabase.table("recipe_ingredients").delete().eq("recipe_id", str(recipe_id)).execute()
        ing_records = [
            {
                "recipe_id": str(recipe_id),
                "ingredient_name": ing["ingredient_name"],
                "amount_text": ing.get("amount_text"),
            }
            for ing in ingredients
        ]
        await supabase.table("recipe_ingredients").insert(ing_records).execute()

    return recipe_id


async def get_ingredients_for_review(
    supabase: AsyncClient,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    """レビュー対象食材を取得する（ページネーション付き）。"""
    start = (page - 1) * per_page
    end = start + per_page - 1

    # 件数取得
    count_resp = await (
        supabase.table("recipe_ingredients")
        .select("id", count="exact")
        .or_("manual_review_needed.eq.true,mext_food_id.is.null")
        .execute()
    )
    total = count_resp.count or 0

    # データ取得
    resp = await (
        supabase.table("recipe_ingredients")
        .select("*, recipes(title, is_nutrition_calculated), mext_foods(name, display_name)")
        .or_("manual_review_needed.eq.true,mext_food_id.is.null")
        .range(start, end)
        .execute()
    )
    return resp.data or [], total


async def update_ingredient_match(
    supabase: AsyncClient,
    ingredient_id: UUID,
    mext_food_id: UUID | None,
    confidence: float,
    review_needed: bool,
) -> UUID | None:
    """食材マッチを更新し、recipe_id を返す。存在しなければ None。"""
    update_data: dict[str, Any] = {
        "mext_food_id": str(mext_food_id) if mext_food_id else None,
        "match_confidence": confidence,
        "manual_review_needed": review_needed,
    }
    resp = await (
        supabase.table("recipe_ingredients")
        .update(update_data)
        .eq("id", str(ingredient_id))
        .select("recipe_id")
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return None
    return rows[0]["recipe_id"]


async def get_ingredients_for_recipes(supabase: AsyncClient, recipe_ids: list[UUID]) -> list[dict[str, Any]]:
    """複数レシピの食材を mext_foods JOIN で取得する。"""
    if not recipe_ids:
        return []
    id_strings = [str(rid) for rid in recipe_ids]
    response = await (
        supabase.table("recipe_ingredients")
        .select("*, mext_foods(name, display_name, category_name)")
        .in_("recipe_id", id_strings)
        .execute()
    )
    rows: list[dict[str, Any]] = response.data or []
    # recipe_id ごとにレシピタイトルが必要なので、recipes テーブルからタイトルも取得
    title_resp = await supabase.table("recipes").select("id, title").in_("id", id_strings).execute()
    title_map: dict[str, str] = {r["id"]: r["title"] for r in (title_resp.data or [])}

    for row in rows:
        row["recipe_title"] = title_map.get(row["recipe_id"], "")
    return rows


FAVORITE_BONUS = 1000.0
TAG_MATCH_BONUS = 500.0
DEFAULT_DINNER_CANDIDATE_LIMIT = 200
STAPLE_FILTER_CANDIDATE_LIMIT = 1000


def _matches_staple_filter(
    recipe: Recipe,
    staple_tags: list[str] | None,
    staple_keywords: list[str] | None,
) -> bool:
    """レシピが主食タグまたはタイトルキーワードにマッチするか判定する。

    タグ比較は正規化後の双方向部分一致:
      recipe.tag が staple_tag を含む OR staple_tag が recipe.tag を含む
    キーワード比較は正規化後のタイトル部分一致。
    """
    if staple_tags:
        recipe_tags = recipe.tags or []
        for r_tag in recipe_tags:
            for s_tag in staple_tags:
                if contains_normalized(r_tag, s_tag) or contains_normalized(s_tag, r_tag):
                    return True
    if staple_keywords:
        title = recipe.title or ""
        for kw in staple_keywords:
            if contains_normalized(title, kw):
                return True
    return False


async def get_recipes_for_dinner(
    supabase: AsyncClient,
    dinner_budget: PFCBudget,
    count: int = 7,
    exclude_ids: list[UUID] | None = None,
    favorite_ids: set[UUID] | None = None,
    staple_tags: list[str] | None = None,
    staple_keywords: list[str] | None = None,
) -> DinnerSelectionResult:
    """3段階選定で夕食レシピを取得する。

    Stage 1: PFC一致 AND 主食一致 → スコア順で count 件まで
    Stage 2: PFC一致 AND 主食不一致 → Stage 1 の不足分を補充
    Stage 3: PFC範囲外 → さらに不足があれば主食一致優先で補充

    staple_tags=None AND staple_keywords=None → Stage 1 空 → 全て Stage 2 → 従来互換。
    """
    candidate_limit = (
        STAPLE_FILTER_CANDIDATE_LIMIT if (staple_tags or staple_keywords) else DEFAULT_DINNER_CANDIDATE_LIMIT
    )
    response = await supabase.table("recipes").select("*").limit(candidate_limit).execute()
    rows = response.data or []
    exclude_set = set(exclude_ids) if exclude_ids else set()
    fav_set = favorite_ids or set()
    has_staple_filter = bool(staple_tags or staple_keywords)

    # 分類: PFC一致+主食一致 / PFC一致+主食不一致 / PFC範囲外(主食一致/不一致)
    pfc_staple: list[tuple[float, Recipe]] = []  # Stage 1
    pfc_only: list[tuple[float, Recipe]] = []  # Stage 2
    out_of_range_staple: list[tuple[float, Recipe]] = []  # Stage 3 (主食一致)
    out_of_range_non_staple: list[tuple[float, Recipe]] = []  # Stage 3 (主食不一致)

    target = dinner_budget.protein_g

    for r in rows:
        recipe = _row_to_recipe(r)
        if recipe.id in exclude_set:
            continue
        nut = recipe.nutrition_per_serving or {}
        protein = nut.get("protein_g", 0)
        fav_bonus = FAVORITE_BONUS if recipe.id in fav_set else 0
        sort_key = abs(protein - target) - fav_bonus

        staple_matched = has_staple_filter and _matches_staple_filter(recipe, staple_tags, staple_keywords)
        if target * 0.8 <= protein <= target * 1.2:
            if staple_matched:
                pfc_staple.append((sort_key, recipe))
            else:
                pfc_only.append((sort_key, recipe))
        else:
            if staple_matched:
                out_of_range_staple.append((sort_key, recipe))
            else:
                out_of_range_non_staple.append((sort_key, recipe))

    # Stage 1: PFC + 主食一致
    pfc_staple.sort(key=lambda x: x[0])
    selected = [r for _, r in pfc_staple[:count]]
    staple_match_count = len(selected)

    # 主食指定時: 一致候補が存在するなら「一致レシピのみ」で count 件を満たす
    # （不足時は一致候補の重複を許容）
    if has_staple_filter:
        out_of_range_staple.sort(key=lambda x: x[0])
        staple_pool = [r for _, r in pfc_staple] + [r for _, r in out_of_range_staple]
        if staple_pool:
            selected = staple_pool[:count]
            i = 0
            while len(selected) < count:
                selected.append(staple_pool[i % len(staple_pool)])
                i += 1
            staple_match_count = len(selected)
            return DinnerSelectionResult(
                recipes=selected,
                staple_match_count=staple_match_count,
                total_count=len(selected),
                staple_fallback_used=False,
            )

    # Stage 2: PFC のみ一致
    if len(selected) < count:
        selected_ids = {s.id for s in selected}
        pfc_only.sort(key=lambda x: x[0])
        selected.extend(r for _, r in pfc_only if r.id not in selected_ids)
        selected = selected[:count]

    # Stage 3: PFC 範囲外（主食一致を先頭に）
    if len(selected) < count:
        selected_ids = {s.id for s in selected}
        out_of_range_staple.sort(key=lambda x: x[0])
        out_of_range_non_staple.sort(key=lambda x: x[0])
        remaining = [r for _, r in out_of_range_staple if r.id not in selected_ids] + [
            r for _, r in out_of_range_non_staple if r.id not in selected_ids
        ]
        # 同スコア帯の偏りを避けるため軽くシャッフル
        if len(remaining) > 1:
            random.shuffle(remaining)
        selected.extend(remaining[: count - len(selected)])

    return DinnerSelectionResult(
        recipes=selected,
        staple_match_count=staple_match_count,
        total_count=len(selected),
        staple_fallback_used=staple_match_count < len(selected) if has_staple_filter else False,
    )
