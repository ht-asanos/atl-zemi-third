"""recipes テーブル操作"""

import logging
import random
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.models.food import NutritionStatus
from app.models.nutrition import PFCBudget
from app.models.recipe import Recipe, RecipeIngredient, RecipeStep
from app.services.recipe_diversity import DiversityFilter
from app.services.shopping_normalizer import normalize_ingredient_candidates
from app.utils.text_normalize import contains_normalized, is_accompaniment_for_staple
from postgrest.exceptions import APIError

from supabase import AsyncClient

logger = logging.getLogger(__name__)

# 選定時セーフティネット: 高精度キーワードのみ（誤除外を避けるため保守的）
_NON_MEAL_TITLE_EXACT = ["つけ汁", "つけだれ", "かえし"]


def _resolve_recipe_source(recipe_source: str | None, recipe_url: str | None) -> str:
    source = (recipe_source or "").strip().lower()
    if source in {"rakuten", "youtube"}:
        return source

    url = (recipe_url or "").lower()
    if "youtu.be" in url or "youtube.com" in url:
        return "youtube"
    return "rakuten"


def _is_likely_non_meal(title: str) -> bool:
    """高精度タイトルキーワードで明らかな非食事レシピを除外。

    Gemini 主判定の補助。誤除外を避けるため保守的なリストのみ。
    """
    return any(contains_normalized(title, kw) for kw in _NON_MEAL_TITLE_EXACT)


@dataclass
class DinnerSelectionResult:
    recipes: list[Recipe] = field(default_factory=list)
    staple_match_count: int = 0
    total_count: int = 0
    staple_fallback_used: bool = False


def _row_to_recipe(row: dict[str, Any], ingredients: list[dict] | None = None) -> Recipe:
    ings = []
    if ingredients:
        for i in ingredients:
            candidates = normalize_ingredient_candidates(i.get("ingredient_name", ""))
            # "or" などのノイズ行は候補が空になるため、レスポンスから除外する。
            if not candidates:
                continue

            ings.append(
                RecipeIngredient(
                    id=i.get("id"),
                    recipe_id=i.get("recipe_id"),
                    ingredient_name=i["ingredient_name"],
                    display_ingredient_name=candidates[0],
                    alternative_ingredient_names=(candidates[1:] if len(candidates) > 1 else []),
                    amount_text=i.get("amount_text"),
                    amount_g=i.get("amount_g"),
                    mext_food_id=i.get("mext_food_id"),
                    match_confidence=i.get("match_confidence"),
                    manual_review_needed=i.get("manual_review_needed", False),
                    kcal=i.get("kcal"),
                    protein_g=i.get("protein_g"),
                    fat_g=i.get("fat_g"),
                    carbs_g=i.get("carbs_g"),
                    matched_food_name=(i.get("mext_foods") or {}).get("display_name")
                    or (i.get("mext_foods") or {}).get("name"),
                    nutrition_match_status=(
                        "matched"
                        if i.get("mext_food_id")
                        else (
                            "estimated"
                            if any(i.get(k) is not None for k in ("kcal", "protein_g", "fat_g", "carbs_g"))
                            else "unmatched"
                        )
                    ),
                    nutrition_source=(
                        "mext"
                        if i.get("mext_food_id")
                        else (
                            "fallback"
                            if any(i.get(k) is not None for k in ("kcal", "protein_g", "fat_g", "carbs_g"))
                            else "none"
                        )
                    ),
                )
            )
    step_rows = row.get("generated_steps") or []
    steps = [
        RecipeStep(
            step_no=int(s.get("step_no", idx + 1)),
            text=str(s.get("text", "")).strip(),
            est_minutes=s.get("est_minutes"),
        )
        for idx, s in enumerate(step_rows)
        if isinstance(s, dict) and str(s.get("text", "")).strip()
    ]

    total = len(ings)
    matched = sum(1 for i in ings if i.nutrition_match_status in {"matched", "estimated"})
    coverage = {
        "matched_count": matched,
        "total_count": total,
        "coverage_rate": round((matched / total) if total else 0.0, 3),
    }

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
        generated_steps=steps,
        steps_status=row.get("steps_status") or ("generated" if steps else "pending"),
        youtube_video_id=row.get("youtube_video_id"),
        recipe_source=_resolve_recipe_source(row.get("recipe_source"), row.get("recipe_url")),
        ingredient_nutrition_coverage=coverage,
    )


# --- Search ---


async def search_recipes(supabase: AsyncClient, query: str, limit: int = 20) -> list[Recipe]:
    """レシピをタイトルで検索する。"""
    response = await supabase.table("recipes").select("*").ilike("title", f"%{query}%").limit(limit).execute()
    rows: list[dict[str, Any]] = response.data or []
    return [_row_to_recipe(r) for r in rows]


# --- Detail ---


async def get_recipe_by_id(supabase: AsyncClient, recipe_id: UUID) -> Recipe | None:
    """レシピ詳細を食材情報付きで取得する。"""
    resp = await supabase.table("recipes").select("*").eq("id", str(recipe_id)).limit(1).execute()
    rows: list[dict[str, Any]] = resp.data or []
    if not rows:
        return None

    ing_resp = (
        await supabase.table("recipe_ingredients")
        .select("*, mext_foods(name, display_name)")
        .eq("recipe_id", str(recipe_id))
        .execute()
    )
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
    recipe_data.pop("ingredients", None)
    original_record = {k: v for k, v in recipe_data.items() if k != "id"}
    if original_record.get("servings") is None:
        original_record["servings"] = 2
    record = dict(original_record)

    try:
        if recipe_data.get("rakuten_recipe_id"):
            response = await supabase.table("recipes").upsert(record, on_conflict="rakuten_recipe_id").execute()
        elif recipe_data.get("youtube_video_id"):
            response = await supabase.table("recipes").upsert(record, on_conflict="youtube_video_id").execute()
        else:
            response = await supabase.table("recipes").insert(record).execute()
    except APIError as e:
        err = str(getattr(e, "message", "") or "")
        # マイグレーション未適用環境向けフォールバック:
        # youtube_video_id / recipe_source 列がない場合は当該項目を落として insert する。
        if recipe_data.get("youtube_video_id") and ("youtube_video_id" in err or "recipe_source" in err):
            fallback_record = dict(original_record)
            fallback_record.pop("youtube_video_id", None)
            fallback_record.pop("recipe_source", None)
            response = await supabase.table("recipes").insert(fallback_record).execute()
        else:
            raise

    row = response.data[0]
    recipe_id = row["id"]

    return recipe_id


# --- Ingredient Review ---


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


# --- Dinner Selection ---

FAVORITE_BONUS = 1000.0
RATING_LIKE_BONUS = 500.0
RATING_DISLIKE_PENALTY = 300.0
MAX_DISLIKE_SORT_KEY = 500.0
TAG_MATCH_BONUS = 500.0
DEFAULT_DINNER_CANDIDATE_LIMIT = 200
STAPLE_FILTER_CANDIDATE_LIMIT = 1000


def _matches_staple_filter(
    recipe: Recipe,
    staple_tags: list[str] | None,
    staple_keywords: list[str] | None,
    staple_short_name: str | None = None,
) -> bool:
    """レシピが主食タグまたはタイトルキーワードにマッチするか判定する。

    タグ比較は正規化後の双方向部分一致:
      recipe.tag が staple_tag を含む OR staple_tag が recipe.tag を含む
    キーワード比較は正規化後のタイトル部分一致。
    主食短縮名が指定されている場合、付け合わせレシピは除外する。
    """
    matched = False
    if staple_tags:
        recipe_tags = recipe.tags or []
        for r_tag in recipe_tags:
            for s_tag in staple_tags:
                if contains_normalized(r_tag, s_tag) or contains_normalized(s_tag, r_tag):
                    matched = True
                    break
            if matched:
                break
    if not matched and staple_keywords:
        title = recipe.title or ""
        for kw in staple_keywords:
            if contains_normalized(title, kw):
                matched = True
                break
    if not matched:
        return False
    # 付け合わせ除外: 主食短縮名が指定されている場合のみ適用
    if staple_short_name and is_accompaniment_for_staple(recipe.title or "", staple_short_name):
        return False
    return True


async def get_recipes_for_dinner(
    supabase: AsyncClient,
    dinner_budget: PFCBudget,
    count: int = 7,
    exclude_ids: list[UUID] | None = None,
    favorite_ids: set[UUID] | None = None,
    liked_ids: set[UUID] | None = None,
    disliked_ids: set[UUID] | None = None,
    staple_tags: list[str] | None = None,
    staple_keywords: list[str] | None = None,
    staple_short_name: str | None = None,
    allowed_sources: list[str] | None = None,
    prefer_favorites: bool = True,
    exclude_disliked: bool = False,
    prefer_variety: bool = True,
    randomize: bool = False,
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
    if randomize:
        random.shuffle(rows)
    exclude_set = set(exclude_ids) if exclude_ids else set()
    fav_set = favorite_ids or set()
    liked_set = liked_ids or set()
    disliked_set = disliked_ids or set()
    has_staple_filter = bool(staple_tags or staple_keywords)
    allowed_source_set = {s.strip().lower() for s in (allowed_sources or ["rakuten", "youtube"]) if s.strip()}

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
        if _is_likely_non_meal(recipe.title or ""):
            logger.warning("Selection safety net filtered: %s (id=%s)", recipe.title, recipe.id)
            continue
        if allowed_source_set and recipe.recipe_source not in allowed_source_set:
            continue
        if exclude_disliked and recipe.id in disliked_set:
            continue
        nut = recipe.nutrition_per_serving or {}
        protein = nut.get("protein_g", 0)
        fav_bonus = FAVORITE_BONUS if prefer_favorites and recipe.id in fav_set else 0
        like_bonus = RATING_LIKE_BONUS if recipe.id in liked_set else 0
        dislike_penalty = RATING_DISLIKE_PENALTY if recipe.id in disliked_set else 0
        raw_key = abs(protein - target) - fav_bonus - like_bonus + dislike_penalty
        sort_key = min(raw_key, MAX_DISLIKE_SORT_KEY) if recipe.id in disliked_set else raw_key

        staple_matched = has_staple_filter and _matches_staple_filter(
            recipe, staple_tags, staple_keywords, staple_short_name
        )
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

    def _select_with_diversity(
        candidates: list[tuple[float, Recipe]],
        selected: list[Recipe],
        selected_ids: set,
        diversity_filter: DiversityFilter,
        target_count: int,
    ) -> None:
        """candidates からカテゴリ制約付きで selected に追加"""
        for _, r in candidates:
            if len(selected) >= target_count:
                break
            if r.id in selected_ids:
                continue
            if diversity_filter.can_add(r.title):
                selected.append(r)
                selected_ids.add(r.id)
                diversity_filter.mark_added(r.title)

    # 全 Stage 共通で使う多様性フィルタ
    diversity = DiversityFilter(max_same=1)

    selected: list[Recipe] = []
    selected_ids: set = set()

    # Stage 1: PFC + 主食一致（max_same=1）
    pfc_staple.sort(key=lambda x: x[0])
    if prefer_variety:
        _select_with_diversity(pfc_staple, selected, selected_ids, diversity, count)
    else:
        for _, r in pfc_staple:
            if len(selected) >= count:
                break
            if r.id in selected_ids:
                continue
            selected.append(r)
            selected_ids.add(r.id)
    staple_match_count = len(selected)

    # Stage 2: PFC のみ一致（max_same=1 継続）
    if len(selected) < count:
        pfc_only.sort(key=lambda x: x[0])
        if prefer_variety:
            _select_with_diversity(pfc_only, selected, selected_ids, diversity, count)
        else:
            for _, r in pfc_only:
                if len(selected) >= count:
                    break
                if r.id in selected_ids:
                    continue
                selected.append(r)
                selected_ids.add(r.id)

    # Stage 3: PFC 範囲外（max_same=1 継続）
    if len(selected) < count:
        remaining = out_of_range_staple + out_of_range_non_staple
        remaining.sort(key=lambda x: x[0])
        if prefer_variety:
            _select_with_diversity(remaining, selected, selected_ids, diversity, count)
        else:
            for _, r in remaining:
                if len(selected) >= count:
                    break
                if r.id in selected_ids:
                    continue
                selected.append(r)
                selected_ids.add(r.id)

    # 段階緩和: まだ足りなければ max_same=2 で全候補を再スキャン
    if prefer_variety and len(selected) < count:
        diversity = diversity.relax()
        all_candidates = pfc_staple + pfc_only + out_of_range_staple + out_of_range_non_staple
        all_candidates.sort(key=lambda x: x[0])
        _select_with_diversity(all_candidates, selected, selected_ids, diversity, count)

    # 最終フォールバック: 制約なし（プラン生成失敗回避）
    if len(selected) < count:
        all_candidates = pfc_staple + pfc_only + out_of_range_staple + out_of_range_non_staple
        all_candidates.sort(key=lambda x: x[0])
        for _, r in all_candidates:
            if len(selected) >= count:
                break
            if r.id not in selected_ids:
                selected.append(r)
                selected_ids.add(r.id)

    # 主食指定があるのに一致0件の場合、最良の主食一致候補を1件差し替える。
    if has_staple_filter and selected:
        staple_match_count = sum(
            1 for r in selected if _matches_staple_filter(r, staple_tags, staple_keywords, staple_short_name)
        )
        if staple_match_count == 0:
            staple_candidates = sorted(pfc_staple + out_of_range_staple, key=lambda x: x[0])
            for _, candidate in staple_candidates:
                if candidate.id in {r.id for r in selected}:
                    continue
                selected[-1] = candidate
                staple_match_count = 1
                break

    return DinnerSelectionResult(
        recipes=selected,
        staple_match_count=staple_match_count,
        total_count=len(selected),
        staple_fallback_used=staple_match_count < len(selected) if has_staple_filter else False,
    )
