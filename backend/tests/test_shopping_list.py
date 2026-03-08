"""買い物リストサービスのテスト。"""

from datetime import date
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from app.schemas.plan import DailyPlanResponse
from app.services.shopping_list import generate_shopping_list

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
