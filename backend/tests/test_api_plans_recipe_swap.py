"""PATCH /plans/{plan_id}/recipe のテスト。"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.models.recipe import Recipe
from app.repositories.recipe_repo import DinnerSelectionResult
from app.schemas.plan import DailyPlanResponse
from postgrest.exceptions import APIError

RECIPE_ID_OLD = uuid4()
RECIPE_ID_NEW = uuid4()


def _make_selection_result(recipes, staple_match_count=0):
    return DinnerSelectionResult(
        recipes=recipes,
        staple_match_count=staple_match_count,
        total_count=len(recipes),
        staple_fallback_used=staple_match_count < len(recipes) if staple_match_count > 0 else False,
    )


def _make_row(recipe_id=RECIPE_ID_OLD, has_recipe=True, plan_meta=None):
    recipe = None
    if has_recipe:
        recipe = {
            "id": str(recipe_id),
            "title": "旧レシピ",
            "recipe_url": "https://example.com/old",
            "cooking_minutes": 15,
        }
    return {
        "id": str(uuid4()),
        "plan_date": "2026-03-09",
        "meal_plan": [
            {
                "meal_type": "breakfast",
                "staple": {
                    "name": "ヨーグルト",
                    "category": "protein",
                    "kcal_per_serving": 62,
                    "protein_g": 3.6,
                    "fat_g": 3.0,
                    "carbs_g": 4.9,
                    "serving_unit": "1個",
                    "price_yen": 30,
                    "cooking_minutes": 0,
                },
                "protein_sources": [],
                "bulk_items": [],
                "total_kcal": 62,
                "total_protein_g": 3.6,
                "total_fat_g": 3.0,
                "total_carbs_g": 4.9,
                "total_price_yen": 30,
                "total_cooking_minutes": 0,
            },
            {
                "meal_type": "lunch",
                "staple": {
                    "name": "おにぎり",
                    "category": "staple",
                    "kcal_per_serving": 180,
                    "protein_g": 2.7,
                    "fat_g": 0.3,
                    "carbs_g": 39.4,
                    "serving_unit": "1個",
                    "price_yen": 120,
                    "cooking_minutes": 0,
                },
                "protein_sources": [],
                "bulk_items": [],
                "total_kcal": 180,
                "total_protein_g": 2.7,
                "total_fat_g": 0.3,
                "total_carbs_g": 39.4,
                "total_price_yen": 120,
                "total_cooking_minutes": 0,
            },
            {
                "meal_type": "dinner",
                "staple": {
                    "name": "旧レシピ",
                    "category": "staple",
                    "kcal_per_serving": 300,
                    "protein_g": 25,
                    "fat_g": 10,
                    "carbs_g": 20,
                    "serving_unit": "1人前",
                    "price_yen": 0,
                    "cooking_minutes": 15,
                },
                "protein_sources": [],
                "bulk_items": [],
                "total_kcal": 300,
                "total_protein_g": 25,
                "total_fat_g": 10,
                "total_carbs_g": 20,
                "total_price_yen": 0,
                "total_cooking_minutes": 15,
                "recipe": recipe,
            },
        ],
        "workout_plan": {},
        "updated_at": "2026-03-09T12:00:00+00:00",
        "plan_meta": plan_meta,
    }


def _make_recipe(recipe_id=RECIPE_ID_NEW):
    return Recipe(
        id=recipe_id,
        title="新レシピ",
        recipe_url="https://example.com/new",
        nutrition_per_serving={"kcal": 350, "protein_g": 30, "fat_g": 12, "carbs_g": 25},
        cooking_minutes=20,
    )


def _make_goal_mock():
    goal = MagicMock()
    goal.protein_g = 120.0
    goal.fat_g = 60.0
    goal.carbs_g = 300.0
    goal.goal_type = "muscle_gain"
    return goal


@pytest.mark.asyncio
async def test_patch_recipe_success():
    """レシピ差し替え成功。"""
    row = _make_row()
    plan_id = row["id"]
    user_id = uuid4()

    with (
        patch("app.routers.plans.plan_repo.get_daily_plan_row_by_user", return_value=row),
        patch("app.routers.plans.goal_repo.get_latest_goal", return_value=_make_goal_mock()),
        patch(
            "app.routers.plans.recipe_repo.get_recipes_for_dinner",
            return_value=_make_selection_result([_make_recipe()]),
        ),
        patch("app.routers.plans.plan_repo.update_daily_plan", return_value=None),
        patch(
            "app.routers.plans.plan_repo.get_daily_plan",
            return_value=DailyPlanResponse(
                id=plan_id, plan_date="2026-03-09", meal_plan=row["meal_plan"], workout_plan={}
            ),
        ),
    ):
        from app.routers.plans import patch_recipe

        result = await patch_recipe(
            plan_id=plan_id,
            user_id=user_id,
            supabase=AsyncMock(),
        )
        assert result is not None


@pytest.mark.asyncio
async def test_patch_recipe_plan_not_found():
    """プラン未発見 → 404。"""
    from fastapi import HTTPException

    with patch("app.routers.plans.plan_repo.get_daily_plan_row_by_user", return_value=None):
        from app.routers.plans import patch_recipe

        with pytest.raises(HTTPException) as exc_info:
            await patch_recipe(plan_id=uuid4(), user_id=uuid4(), supabase=AsyncMock())
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_patch_recipe_classic_mode():
    """classic モード → 422。"""
    from fastapi import HTTPException

    row = _make_row(has_recipe=False)

    with patch("app.routers.plans.plan_repo.get_daily_plan_row_by_user", return_value=row):
        from app.routers.plans import patch_recipe

        with pytest.raises(HTTPException) as exc_info:
            await patch_recipe(plan_id=uuid4(), user_id=uuid4(), supabase=AsyncMock())
        assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_patch_recipe_no_alternative():
    """代替レシピなし → 404。"""
    from fastapi import HTTPException

    row = _make_row()

    with (
        patch("app.routers.plans.plan_repo.get_daily_plan_row_by_user", return_value=row),
        patch("app.routers.plans.goal_repo.get_latest_goal", return_value=_make_goal_mock()),
        patch(
            "app.routers.plans.recipe_repo.get_recipes_for_dinner",
            return_value=_make_selection_result([]),
        ),
    ):
        from app.routers.plans import patch_recipe

        with pytest.raises(HTTPException) as exc_info:
            await patch_recipe(plan_id=uuid4(), user_id=uuid4(), supabase=AsyncMock())
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_patch_recipe_with_staple_no_match_returns_422():
    """主食指定ありで一致候補ゼロなら422。"""
    from fastapi import HTTPException

    row = _make_row(plan_meta={"mode": "recipe", "staple_name": "冷凍うどん"})
    with (
        patch("app.routers.plans.plan_repo.get_daily_plan_row_by_user", return_value=row),
        patch("app.routers.plans.goal_repo.get_latest_goal", return_value=_make_goal_mock()),
        patch(
            "app.routers.plans.recipe_repo.get_recipes_for_dinner",
            return_value=_make_selection_result([], staple_match_count=0),
        ),
    ):
        from app.routers.plans import patch_recipe

        with pytest.raises(HTTPException) as exc_info:
            await patch_recipe(plan_id=uuid4(), user_id=uuid4(), supabase=AsyncMock())
        assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_patch_recipe_optimistic_lock_conflict():
    """楽観ロック衝突（APIError 40001）→ 409。"""
    from fastapi import HTTPException

    row = _make_row()

    api_error = APIError({"message": "conflict", "code": "40001", "details": "", "hint": ""})

    with (
        patch("app.routers.plans.plan_repo.get_daily_plan_row_by_user", return_value=row),
        patch("app.routers.plans.goal_repo.get_latest_goal", return_value=_make_goal_mock()),
        patch(
            "app.routers.plans.recipe_repo.get_recipes_for_dinner",
            return_value=_make_selection_result([_make_recipe()]),
        ),
        patch("app.routers.plans.plan_repo.update_daily_plan", side_effect=api_error),
    ):
        from app.routers.plans import patch_recipe

        with pytest.raises(HTTPException) as exc_info:
            await patch_recipe(plan_id=uuid4(), user_id=uuid4(), supabase=AsyncMock())
        assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_patch_recipe_preserves_staple():
    """plan_meta.staple_name がある場合、get_recipes_for_dinner に staple_tags/keywords が渡されること。"""
    row = _make_row(plan_meta={"mode": "recipe", "staple_name": "白米"})
    plan_id = row["id"]
    user_id = uuid4()

    mock_get_dinner = AsyncMock(return_value=_make_selection_result([_make_recipe()], staple_match_count=1))

    with (
        patch("app.routers.plans.plan_repo.get_daily_plan_row_by_user", return_value=row),
        patch("app.routers.plans.goal_repo.get_latest_goal", return_value=_make_goal_mock()),
        patch("app.routers.plans.recipe_repo.get_recipes_for_dinner", mock_get_dinner),
        patch("app.routers.plans.plan_repo.update_daily_plan", return_value=None),
        patch(
            "app.routers.plans.plan_repo.get_daily_plan",
            return_value=DailyPlanResponse(
                id=plan_id, plan_date="2026-03-09", meal_plan=row["meal_plan"], workout_plan={}
            ),
        ),
    ):
        from app.routers.plans import patch_recipe

        await patch_recipe(plan_id=plan_id, user_id=user_id, supabase=AsyncMock())

    # staple_tags と staple_keywords が渡されていることを検証
    call_kwargs = mock_get_dinner.call_args
    assert call_kwargs.kwargs.get("staple_tags") is not None
    assert call_kwargs.kwargs.get("staple_keywords") is not None
    assert "白米" not in call_kwargs.kwargs["staple_tags"]  # タグはマップ値
    assert "丼" in call_kwargs.kwargs["staple_tags"]  # 白米のタグに "丼" がある
