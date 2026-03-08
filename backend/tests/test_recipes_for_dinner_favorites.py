"""get_recipes_for_dinner のお気に入り優遇テスト。"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.models.nutrition import PFCBudget
from app.repositories.recipe_repo import FAVORITE_BONUS, TAG_MATCH_BONUS, get_recipes_for_dinner

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

    # 非お気に入り: protein_g=30 (diff=0), お気に入り: protein_g=32 (diff=2)
    # FAVORITE_BONUS があるのでお気に入りが先
    rows = [
        _make_recipe_row(NON_FAV_RECIPE_ID, protein_g=30.0),
        _make_recipe_row(FAV_RECIPE_ID, protein_g=32.0),
    ]

    supabase = _make_supabase_with_rows(rows)

    result = await get_recipes_for_dinner(supabase, budget, count=2, favorite_ids={FAV_RECIPE_ID})

    assert len(result) == 2
    assert result[0].id == FAV_RECIPE_ID


@pytest.mark.asyncio
async def test_favorite_bonus_score_calculation():
    """FAVORITE_BONUS 定数を使ったスコア計算の検証。"""
    budget = PFCBudget(protein_g=30.0, fat_g=20.0, carbs_g=50.0)
    target = budget.protein_g

    # お気に入り: protein=32, diff=2, score = 2 - 1000 = -998
    # 非お気に入り: protein=30, diff=0, score = 0
    fav_protein = 32.0
    non_fav_protein = 30.0

    fav_score = abs(fav_protein - target) - FAVORITE_BONUS
    non_fav_score = abs(non_fav_protein - target)

    assert fav_score < non_fav_score, "Favorite score should be lower (higher priority)"
    assert fav_score == 2.0 - FAVORITE_BONUS


@pytest.mark.asyncio
async def test_favorite_outside_pfc_range_not_selected():
    """お気に入りが PFC フィルタ外なら選ばれないこと。"""
    budget = PFCBudget(protein_g=30.0, fat_g=20.0, carbs_g=50.0)

    # PFC 範囲: 24-36g protein. お気に入りの protein=100 は範囲外
    rows = [
        _make_recipe_row(OUT_OF_RANGE_FAV_ID, protein_g=100.0),
        _make_recipe_row(NON_FAV_RECIPE_ID, protein_g=30.0),
    ]

    supabase = _make_supabase_with_rows(rows)

    result = await get_recipes_for_dinner(supabase, budget, count=1, favorite_ids={OUT_OF_RANGE_FAV_ID})

    assert len(result) == 1
    assert result[0].id == NON_FAV_RECIPE_ID


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

    assert len(result) == 2
    assert result[0].id == TAGGED_RECIPE_ID


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

    assert len(result) == 2
    assert result[0].id == KEYWORD_RECIPE_ID


@pytest.mark.asyncio
async def test_staple_filter_fallback_when_insufficient():
    """タグ + キーワード候補が不足時にフォールバックで補充されること。"""
    budget = PFCBudget(protein_g=30.0, fat_g=20.0, carbs_g=50.0)

    # PFC範囲外のレシピをフォールバック用に用意
    fallback_id = uuid4()
    rows = [
        _make_recipe_row_with_tags(TAGGED_RECIPE_ID, protein_g=30.0, tags=["うどん"], title="うどん"),
        _make_recipe_row_with_tags(fallback_id, protein_g=100.0, title="高タンパクレシピ"),
    ]

    supabase = _make_supabase_with_rows(rows)

    result = await get_recipes_for_dinner(supabase, budget, count=2, staple_tags=["うどん"], staple_keywords=["うどん"])

    # PFC範囲内1件 + フォールバック1件 = 2件
    assert len(result) == 2
    assert result[0].id == TAGGED_RECIPE_ID


@pytest.mark.asyncio
async def test_tag_match_bonus_value():
    """TAG_MATCH_BONUS 定数の値を検証。"""
    assert TAG_MATCH_BONUS == 500.0
