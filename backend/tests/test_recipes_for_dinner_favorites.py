"""get_recipes_for_dinner のお気に入り優遇・主食フィルタテスト。"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.models.nutrition import PFCBudget
from app.repositories.recipe_repo import FAVORITE_BONUS, get_recipes_for_dinner

FAV_RECIPE_ID = uuid4()
NON_FAV_RECIPE_ID = uuid4()
OUT_OF_RANGE_FAV_ID = uuid4()


def _make_recipe_row(recipe_id, protein_g=30.0):
    return {
        "id": str(recipe_id),
        "title": f"レシピ_{recipe_id}",
        "recipe_url": "https://example.com",
        "nutrition_per_serving": {"protein_g": protein_g, "fat_g": 10, "carbs_g": 20, "kcal": 300},
        "is_nutrition_calculated": True,
        "servings": 1,
        "tags": [],
    }


def _make_supabase_with_rows(rows):
    supabase = MagicMock()
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    chain.execute = AsyncMock(return_value=MagicMock(data=rows))
    supabase.table.return_value = chain
    return supabase


@pytest.mark.asyncio
async def test_favorite_recipe_prioritized():
    """お気に入りレシピが非お気に入りより先に選ばれること。"""
    budget = PFCBudget(protein_g=30.0, fat_g=20.0, carbs_g=50.0)

    rows = [
        _make_recipe_row(NON_FAV_RECIPE_ID, protein_g=30.0),
        _make_recipe_row(FAV_RECIPE_ID, protein_g=32.0),
    ]

    supabase = _make_supabase_with_rows(rows)

    result = await get_recipes_for_dinner(supabase, budget, count=2, favorite_ids={FAV_RECIPE_ID})

    assert len(result.recipes) == 2
    assert result.recipes[0].id == FAV_RECIPE_ID


@pytest.mark.asyncio
async def test_favorite_bonus_score_calculation():
    """FAVORITE_BONUS 定数を使ったスコア計算の検証。"""
    budget = PFCBudget(protein_g=30.0, fat_g=20.0, carbs_g=50.0)
    target = budget.protein_g

    fav_protein = 32.0
    non_fav_protein = 30.0

    fav_score = abs(fav_protein - target) - FAVORITE_BONUS
    non_fav_score = abs(non_fav_protein - target)

    assert fav_score < non_fav_score, "Favorite score should be lower (higher priority)"
    assert fav_score == 2.0 - FAVORITE_BONUS


@pytest.mark.asyncio
async def test_favorite_outside_pfc_range_not_selected():
    """お気に入りが PFC フィルタ外なら PFC 内が先に選ばれること。"""
    budget = PFCBudget(protein_g=30.0, fat_g=20.0, carbs_g=50.0)

    rows = [
        _make_recipe_row(OUT_OF_RANGE_FAV_ID, protein_g=100.0),
        _make_recipe_row(NON_FAV_RECIPE_ID, protein_g=30.0),
    ]

    supabase = _make_supabase_with_rows(rows)

    result = await get_recipes_for_dinner(supabase, budget, count=1, favorite_ids={OUT_OF_RANGE_FAV_ID})

    assert len(result.recipes) == 1
    assert result.recipes[0].id == NON_FAV_RECIPE_ID


TAGGED_RECIPE_ID = uuid4()
KEYWORD_RECIPE_ID = uuid4()
UNMATCHED_RECIPE_ID = uuid4()


def _make_recipe_row_with_tags(recipe_id, protein_g=30.0, tags=None, title="レシピ"):
    return {
        "id": str(recipe_id),
        "title": title,
        "recipe_url": "https://example.com",
        "nutrition_per_serving": {"protein_g": protein_g, "fat_g": 10, "carbs_g": 20, "kcal": 300},
        "is_nutrition_calculated": True,
        "servings": 1,
        "tags": tags or [],
    }


@pytest.mark.asyncio
async def test_staple_tags_prioritize_matching_recipes():
    """staple_tags 指定時にタグマッチするレシピが優先されること。"""
    budget = PFCBudget(protein_g=30.0, fat_g=20.0, carbs_g=50.0)

    rows = [
        _make_recipe_row_with_tags(UNMATCHED_RECIPE_ID, protein_g=30.0, tags=["カレー"], title="カレー"),
        _make_recipe_row_with_tags(TAGGED_RECIPE_ID, protein_g=31.0, tags=["うどん"], title="焼きうどん"),
    ]

    supabase = _make_supabase_with_rows(rows)

    result = await get_recipes_for_dinner(supabase, budget, count=2, staple_tags=["うどん", "焼きうどん"])

    assert len(result.recipes) == 2
    assert result.recipes[0].id == TAGGED_RECIPE_ID


@pytest.mark.asyncio
async def test_staple_keywords_prioritize_title_match():
    """staple_keywords 指定時にタイトル部分一致レシピが優先されること。"""
    budget = PFCBudget(protein_g=30.0, fat_g=20.0, carbs_g=50.0)

    rows = [
        _make_recipe_row_with_tags(UNMATCHED_RECIPE_ID, protein_g=30.0, title="鶏肉の照り焼き"),
        _make_recipe_row_with_tags(KEYWORD_RECIPE_ID, protein_g=31.0, title="肉うどん"),
    ]

    supabase = _make_supabase_with_rows(rows)

    result = await get_recipes_for_dinner(supabase, budget, count=2, staple_keywords=["うどん"])

    assert len(result.recipes) == 2
    assert result.recipes[0].id == KEYWORD_RECIPE_ID


@pytest.mark.asyncio
async def test_staple_filter_fallback_when_insufficient():
    """主食指定時は不足しても主食一致のみで埋めること。"""
    budget = PFCBudget(protein_g=30.0, fat_g=20.0, carbs_g=50.0)

    fallback_id = uuid4()
    rows = [
        _make_recipe_row_with_tags(TAGGED_RECIPE_ID, protein_g=30.0, tags=["うどん"], title="うどん"),
        _make_recipe_row_with_tags(fallback_id, protein_g=100.0, title="高タンパクレシピ"),
    ]

    supabase = _make_supabase_with_rows(rows)

    result = await get_recipes_for_dinner(supabase, budget, count=2, staple_tags=["うどん"], staple_keywords=["うどん"])

    assert len(result.recipes) == 2
    assert all(any(t in (r.tags or []) for t in ["うどん"]) or "うどん" in (r.title or "") for r in result.recipes)
    assert result.staple_match_count == 2
    assert result.staple_fallback_used is False


# --- 後方互換テスト ---


@pytest.mark.asyncio
async def test_no_staple_filter_backward_compatible():
    """staple_tags=None, staple_keywords=None で旧ロジック互換（PFC 順）。"""
    budget = PFCBudget(protein_g=30.0, fat_g=20.0, carbs_g=50.0)

    id1 = uuid4()
    id2 = uuid4()
    rows = [
        _make_recipe_row_with_tags(id1, protein_g=30.0, title="レシピA"),
        _make_recipe_row_with_tags(id2, protein_g=32.0, title="レシピB"),
    ]

    supabase = _make_supabase_with_rows(rows)

    result = await get_recipes_for_dinner(supabase, budget, count=2)

    assert len(result.recipes) == 2
    # PFC差が小さい id1 が先
    assert result.recipes[0].id == id1
    assert result.staple_match_count == 0
    assert result.staple_fallback_used is False


# --- Stage 1 優先テスト ---


@pytest.mark.asyncio
async def test_stage1_staple_pfc_prioritized_over_pfc_only():
    """主食+PFC 一致が PFC only より先に選ばれること。"""
    budget = PFCBudget(protein_g=30.0, fat_g=20.0, carbs_g=50.0)

    staple_id = uuid4()
    non_staple_id = uuid4()
    rows = [
        # PFC一致 + protein差=0 だが主食不一致
        _make_recipe_row_with_tags(non_staple_id, protein_g=30.0, title="鶏肉炒め"),
        # PFC一致 + protein差=2 だが主食一致
        _make_recipe_row_with_tags(staple_id, protein_g=32.0, tags=["うどん"], title="焼きうどん"),
    ]

    supabase = _make_supabase_with_rows(rows)

    result = await get_recipes_for_dinner(supabase, budget, count=1, staple_tags=["うどん"], staple_keywords=["うどん"])

    assert result.recipes[0].id == staple_id
    assert result.staple_match_count == 1


# --- 正規化タグマッチテスト ---


@pytest.mark.asyncio
async def test_normalized_tag_match():
    """recipe.tags=["焼うどん"] + staple_tags=["うどん"] → マッチ（正規化部分一致）。"""
    budget = PFCBudget(protein_g=30.0, fat_g=20.0, carbs_g=50.0)

    match_id = uuid4()
    rows = [
        _make_recipe_row_with_tags(match_id, protein_g=30.0, tags=["焼うどん"], title="焼うどん"),
    ]

    supabase = _make_supabase_with_rows(rows)

    result = await get_recipes_for_dinner(supabase, budget, count=1, staple_tags=["うどん"])

    assert result.staple_match_count == 1
    assert result.recipes[0].id == match_id


# --- metadata 検証 ---


@pytest.mark.asyncio
async def test_metadata_values():
    """DinnerSelectionResult の staple_match_count, staple_fallback_used の値確認。"""
    budget = PFCBudget(protein_g=30.0, fat_g=20.0, carbs_g=50.0)

    id1 = uuid4()
    id2 = uuid4()
    id3 = uuid4()
    rows = [
        _make_recipe_row_with_tags(id1, protein_g=30.0, tags=["うどん"], title="うどん"),
        _make_recipe_row_with_tags(id2, protein_g=31.0, tags=["カレー"], title="カレー"),
        _make_recipe_row_with_tags(id3, protein_g=29.0, title="鶏肉ソテー"),
    ]

    supabase = _make_supabase_with_rows(rows)

    result = await get_recipes_for_dinner(supabase, budget, count=3, staple_tags=["うどん"])

    assert result.staple_match_count == 3
    assert result.total_count == 3
    assert result.staple_fallback_used is False


@pytest.mark.asyncio
async def test_staple_filter_guarantees_one_match_when_available():
    """主食一致が1件でも存在すれば、全件主食一致で返ること（重複許容）。"""
    budget = PFCBudget(protein_g=30.0, fat_g=20.0, carbs_g=50.0)

    matched_out_of_range_id = uuid4()
    pfc_non_match_1 = uuid4()
    pfc_non_match_2 = uuid4()

    rows = [
        # 主食一致だが PFC 範囲外
        _make_recipe_row_with_tags(matched_out_of_range_id, protein_g=100.0, tags=["うどん"], title="鍋焼きうどん"),
        # PFC 一致だが主食不一致
        _make_recipe_row_with_tags(pfc_non_match_1, protein_g=30.0, title="鶏の照り焼き"),
        _make_recipe_row_with_tags(pfc_non_match_2, protein_g=29.0, title="豚の生姜焼き"),
    ]

    supabase = _make_supabase_with_rows(rows)

    result = await get_recipes_for_dinner(
        supabase,
        budget,
        count=2,
        staple_tags=["うどん"],
        staple_keywords=["うどん"],
    )

    assert len(result.recipes) == 2
    assert all(r.id == matched_out_of_range_id for r in result.recipes)
    assert result.staple_match_count == 2


@pytest.mark.asyncio
async def test_staple_filter_returns_only_matching_recipes_even_with_non_matching_pfc_candidates():
    """主食指定時はPFC一致の非主食候補があっても採用しないこと。"""
    budget = PFCBudget(protein_g=30.0, fat_g=20.0, carbs_g=50.0)

    matched_pfc_id = uuid4()
    non_match_pfc_id = uuid4()
    rows = [
        _make_recipe_row_with_tags(matched_pfc_id, protein_g=31.0, tags=["うどん"], title="きつねうどん"),
        _make_recipe_row_with_tags(non_match_pfc_id, protein_g=30.0, tags=["カレー"], title="カレー"),
    ]

    supabase = _make_supabase_with_rows(rows)
    result = await get_recipes_for_dinner(supabase, budget, count=2, staple_tags=["うどん"], staple_keywords=["うどん"])

    assert len(result.recipes) == 2
    assert all(r.id == matched_pfc_id for r in result.recipes)
    assert result.staple_match_count == 2
