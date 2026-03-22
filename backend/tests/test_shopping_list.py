"""買い物リストサービスのテスト。"""

from datetime import date
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from app.schemas.plan import DailyPlanResponse
from app.services.shopping_list import _make_group_id, generate_shopping_list

RECIPE_ID_1 = uuid4()
RECIPE_ID_2 = uuid4()
MEXT_FOOD_ID_CHICKEN = uuid4()


def _make_plan(plan_date: str, recipe_id: UUID | None = None) -> DailyPlanResponse:
    recipe = None
    if recipe_id:
        recipe = {
            "id": str(recipe_id),
            "title": f"レシピ_{recipe_id}",
            "recipe_url": "https://example.com",
        }
    return DailyPlanResponse(
        id=uuid4(),
        plan_date=plan_date,
        meal_plan=[
            {"meal_type": "breakfast", "staple": {}, "protein_sources": [], "bulk_items": []},
            {"meal_type": "lunch", "staple": {}, "protein_sources": [], "bulk_items": []},
            {"meal_type": "dinner", "staple": {}, "protein_sources": [], "bulk_items": [], "recipe": recipe},
        ],
        workout_plan={},
    )


@pytest.mark.asyncio
async def test_same_mext_food_id_aggregated():
    """2 レシピで同一 mext_food_id の食材が合算されること。"""
    supabase = AsyncMock()
    user_id = uuid4()
    plans = [
        _make_plan("2026-03-09", RECIPE_ID_1),
        _make_plan("2026-03-10", RECIPE_ID_2),
    ]
    ingredients = [
        {
            "ingredient_name": "鶏もも肉",
            "mext_food_id": str(MEXT_FOOD_ID_CHICKEN),
            "amount_g": 200.0,
            "amount_text": "200g",
            "recipe_id": str(RECIPE_ID_1),
            "recipe_title": "レシピA",
            "mext_foods": {"name": "鶏肉", "category_name": "肉類"},
        },
        {
            "ingredient_name": "鶏肉",
            "mext_food_id": str(MEXT_FOOD_ID_CHICKEN),
            "amount_g": 150.0,
            "amount_text": "150g",
            "recipe_id": str(RECIPE_ID_2),
            "recipe_title": "レシピB",
            "mext_foods": {"name": "鶏肉", "category_name": "肉類"},
        },
    ]

    with (
        patch("app.services.shopping_list.plan_repo.get_weekly_plans", return_value=plans),
        patch("app.services.shopping_list.recipe_repo.get_ingredients_for_recipes", return_value=ingredients),
    ):
        result = await generate_shopping_list(supabase, user_id, date(2026, 3, 9))

    assert len(result.items) == 1
    item = result.items[0]
    assert item.ingredient_name == "鶏肉"
    assert item.amount_g == 350.0
    assert set(item.recipe_titles) == {"レシピA", "レシピB"}
    assert result.recipe_count == 2


@pytest.mark.asyncio
async def test_null_mext_food_id_falls_back_to_ingredient_name():
    """mext_food_id が None の場合は ingredient_name で集約されること。"""
    supabase = AsyncMock()
    user_id = uuid4()
    plans = [_make_plan("2026-03-09", RECIPE_ID_1), _make_plan("2026-03-10", RECIPE_ID_2)]
    ingredients = [
        {
            "ingredient_name": "塩",
            "mext_food_id": None,
            "amount_g": 5.0,
            "amount_text": "少々",
            "recipe_id": str(RECIPE_ID_1),
            "recipe_title": "レシピA",
            "mext_foods": None,
        },
        {
            "ingredient_name": "塩",
            "mext_food_id": None,
            "amount_g": 3.0,
            "amount_text": "少々",
            "recipe_id": str(RECIPE_ID_2),
            "recipe_title": "レシピB",
            "mext_foods": None,
        },
    ]

    with (
        patch("app.services.shopping_list.plan_repo.get_weekly_plans", return_value=plans),
        patch("app.services.shopping_list.recipe_repo.get_ingredients_for_recipes", return_value=ingredients),
    ):
        result = await generate_shopping_list(supabase, user_id, date(2026, 3, 9))

    assert len(result.items) == 1
    assert result.items[0].ingredient_name == "塩"
    assert result.items[0].amount_g == 8.0


@pytest.mark.asyncio
async def test_recipe_id_none_skipped():
    """recipe.id が None のプランはスキップされること。"""
    supabase = AsyncMock()
    user_id = uuid4()
    plans = [_make_plan("2026-03-09", None)]  # recipe_id なし

    with (
        patch("app.services.shopping_list.plan_repo.get_weekly_plans", return_value=plans),
        patch("app.services.shopping_list.recipe_repo.get_ingredients_for_recipes") as mock_get_ing,
    ):
        result = await generate_shopping_list(supabase, user_id, date(2026, 3, 9))

    assert result.items == []
    assert result.recipe_count == 0
    mock_get_ing.assert_not_called()


@pytest.mark.asyncio
async def test_synonym_ingredients_aggregated():
    """同義語食材（料理酒 → 酒）が1行に集約されること。"""
    supabase = AsyncMock()
    user_id = uuid4()
    plans = [_make_plan("2026-03-09", RECIPE_ID_1), _make_plan("2026-03-10", RECIPE_ID_2)]
    ingredients = [
        {
            "ingredient_name": "料理酒",
            "mext_food_id": None,
            "amount_g": 15.0,
            "amount_text": "大さじ1",
            "recipe_id": str(RECIPE_ID_1),
            "recipe_title": "レシピA",
            "mext_foods": None,
        },
        {
            "ingredient_name": "日本酒",
            "mext_food_id": None,
            "amount_g": 15.0,
            "amount_text": "大さじ1",
            "recipe_id": str(RECIPE_ID_2),
            "recipe_title": "レシピB",
            "mext_foods": None,
        },
    ]

    with (
        patch("app.services.shopping_list.plan_repo.get_weekly_plans", return_value=plans),
        patch("app.services.shopping_list.recipe_repo.get_ingredients_for_recipes", return_value=ingredients),
    ):
        result = await generate_shopping_list(supabase, user_id, date(2026, 3, 9))

    assert len(result.items) == 1
    assert result.items[0].ingredient_name == "酒"
    assert result.items[0].amount_g == 30.0


@pytest.mark.asyncio
async def test_non_purchasable_flagged():
    """非購買品目が is_purchasable=False になること。"""
    supabase = AsyncMock()
    user_id = uuid4()
    plans = [_make_plan("2026-03-09", RECIPE_ID_1)]
    ingredients = [
        {
            "ingredient_name": "水",
            "mext_food_id": None,
            "amount_g": 200.0,
            "amount_text": "1カップ",
            "recipe_id": str(RECIPE_ID_1),
            "recipe_title": "レシピA",
            "mext_foods": None,
        },
        {
            "ingredient_name": "鶏もも肉",
            "mext_food_id": None,
            "amount_g": 200.0,
            "amount_text": "200g",
            "recipe_id": str(RECIPE_ID_1),
            "recipe_title": "レシピA",
            "mext_foods": None,
        },
    ]

    with (
        patch("app.services.shopping_list.plan_repo.get_weekly_plans", return_value=plans),
        patch("app.services.shopping_list.recipe_repo.get_ingredients_for_recipes", return_value=ingredients),
    ):
        result = await generate_shopping_list(supabase, user_id, date(2026, 3, 9))

    water_items = [i for i in result.items if i.ingredient_name == "水"]
    chicken_items = [i for i in result.items if i.ingredient_name == "鶏もも肉"]
    assert len(water_items) == 1
    assert water_items[0].is_purchasable is False
    assert len(chicken_items) == 1
    assert chicken_items[0].is_purchasable is True


@pytest.mark.asyncio
async def test_classic_mode_returns_empty():
    """classic モード（recipe なし）で空リストが返ること。"""
    supabase = AsyncMock()
    user_id = uuid4()
    # classic モード: meal_type がない
    plans = [
        DailyPlanResponse(
            id=uuid4(),
            plan_date="2026-03-09",
            meal_plan=[
                {"staple": {"name": "白米"}, "protein_sources": [], "bulk_items": []},
            ],
            workout_plan={},
        )
    ]

    with (
        patch("app.services.shopping_list.plan_repo.get_weekly_plans", return_value=plans),
    ):
        result = await generate_shopping_list(supabase, user_id, date(2026, 3, 9))

    assert result.items == []
    assert result.recipe_count == 0


@pytest.mark.asyncio
async def test_alternative_candidates_share_group_id():
    """代替候補は展開され、同一 group_id を持つこと。"""
    supabase = AsyncMock()
    user_id = uuid4()
    plans = [_make_plan("2026-03-09", RECIPE_ID_1)]
    ingredients = [
        {
            "ingredient_name": "〇醤油 / みりん / 酒",
            "mext_food_id": None,
            "amount_g": 10.0,
            "amount_text": "各大さじ2",
            "recipe_id": str(RECIPE_ID_1),
            "recipe_title": "レシピA",
            "mext_foods": None,
        }
    ]

    with (
        patch("app.services.shopping_list.plan_repo.get_weekly_plans", return_value=plans),
        patch("app.services.shopping_list.recipe_repo.get_ingredients_for_recipes", return_value=ingredients),
    ):
        result = await generate_shopping_list(supabase, user_id, date(2026, 3, 9))

    assert {i.ingredient_name for i in result.items} == {"しょうゆ", "みりん", "酒"}
    group_ids = {i.group_id for i in result.items}
    assert len(group_ids) == 1


@pytest.mark.asyncio
async def test_checked_group_is_marked_checked():
    """チェック済みグループは非表示にせず checked=True で返す。"""
    supabase = AsyncMock()
    user_id = uuid4()
    plans = [_make_plan("2026-03-09", RECIPE_ID_1)]
    ingredients = [
        {
            "ingredient_name": "醤油 / みりん / 酒",
            "mext_food_id": None,
            "amount_g": 10.0,
            "amount_text": "各大さじ2",
            "recipe_id": str(RECIPE_ID_1),
            "recipe_title": "レシピA",
            "mext_foods": None,
        }
    ]
    checked_group_id = _make_group_id(["しょうゆ", "みりん", "酒"])

    with (
        patch("app.services.shopping_list.plan_repo.get_weekly_plans", return_value=plans),
        patch("app.services.shopping_list.recipe_repo.get_ingredients_for_recipes", return_value=ingredients),
    ):
        result = await generate_shopping_list(
            supabase,
            user_id,
            date(2026, 3, 9),
            checked_group_ids={checked_group_id},
        )

    assert len(result.items) == 3
    assert all(item.checked is True for item in result.items)


@pytest.mark.asyncio
async def test_noise_token_ingredient_is_ignored():
    """材料ではないノイズトークン（or など）は除外されること。"""
    supabase = AsyncMock()
    user_id = uuid4()
    plans = [_make_plan("2026-03-09", RECIPE_ID_1)]
    ingredients = [
        {
            "ingredient_name": "or",
            "mext_food_id": None,
            "amount_g": None,
            "amount_text": None,
            "recipe_id": str(RECIPE_ID_1),
            "recipe_title": "レシピA",
            "mext_foods": None,
        }
    ]

    with (
        patch("app.services.shopping_list.plan_repo.get_weekly_plans", return_value=plans),
        patch("app.services.shopping_list.recipe_repo.get_ingredients_for_recipes", return_value=ingredients),
    ):
        result = await generate_shopping_list(supabase, user_id, date(2026, 3, 9))

    assert result.items == []
