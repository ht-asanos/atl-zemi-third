"""レシピ重複排除ロジックのユニットテスト。"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from app.models.nutrition import PFCBudget
from app.models.recipe import Recipe
from app.repositories import plan_repo
from app.repositories.recipe_repo import DinnerSelectionResult
from app.services.weekly_planner import generate_weekly_plan_v3_validated


def _make_mock_response(rows: list[dict]) -> MagicMock:
    """Supabase レスポンスのモックを作成する。"""
    mock = MagicMock()
    mock.data = rows
    return mock


def _make_table_supabase_mock(rows: list[dict]) -> MagicMock:
    """supabase.table(...).select(...).eq(...).execute() チェーンのモック。

    table() は同期（ビルダーを返す）、execute() が非同期。
    """
    mock = MagicMock()
    chain = MagicMock()
    mock.table.return_value = chain
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.gte.return_value = chain
    chain.lte.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.execute = AsyncMock(return_value=_make_mock_response(rows))
    return mock


class TestGetPastRecipeIds:
    @pytest.mark.asyncio
    async def test_extracts_recipe_ids_from_dinner(self) -> None:
        """夕食レシピの ID を正しく抽出できること。"""
        recipe_id_1 = str(uuid4())
        recipe_id_2 = str(uuid4())
        rows = [
            {
                "meal_plan": [
                    {"meal_type": "breakfast", "recipe": None},
                    {"meal_type": "lunch", "recipe": None},
                    {"meal_type": "dinner", "recipe": {"id": recipe_id_1, "title": "テスト1"}},
                ]
            },
            {
                "meal_plan": [
                    {"meal_type": "breakfast", "recipe": None},
                    {"meal_type": "lunch", "recipe": None},
                    {"meal_type": "dinner", "recipe": {"id": recipe_id_2, "title": "テスト2"}},
                ]
            },
        ]

        mock_supabase = _make_table_supabase_mock(rows)
        result = await plan_repo.get_past_recipe_ids(mock_supabase, uuid4(), weeks=4)

        assert len(result) == 2
        assert UUID(recipe_id_1) in result
        assert UUID(recipe_id_2) in result

    @pytest.mark.asyncio
    async def test_returns_unique_ids(self) -> None:
        """同じレシピIDが重複して含まれないこと。"""
        recipe_id = str(uuid4())
        rows = [
            {"meal_plan": [{"meal_type": "dinner", "recipe": {"id": recipe_id}}]},
            {"meal_plan": [{"meal_type": "dinner", "recipe": {"id": recipe_id}}]},
            {"meal_plan": [{"meal_type": "dinner", "recipe": {"id": recipe_id}}]},
        ]

        mock_supabase = _make_table_supabase_mock(rows)
        result = await plan_repo.get_past_recipe_ids(mock_supabase, uuid4(), weeks=4)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_skips_non_dinner_meals(self) -> None:
        """夕食以外の食事は無視されること。"""
        rows = [
            {
                "meal_plan": [
                    {"meal_type": "breakfast", "recipe": {"id": str(uuid4())}},
                    {"meal_type": "lunch", "recipe": {"id": str(uuid4())}},
                    {"meal_type": "dinner", "recipe": None},
                ]
            },
        ]

        mock_supabase = _make_table_supabase_mock(rows)
        result = await plan_repo.get_past_recipe_ids(mock_supabase, uuid4(), weeks=4)

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_handles_empty_data(self) -> None:
        """プランが無い場合は空リストを返すこと。"""
        mock_supabase = _make_table_supabase_mock([])
        result = await plan_repo.get_past_recipe_ids(mock_supabase, uuid4(), weeks=4)

        assert result == []

    @pytest.mark.asyncio
    async def test_handles_invalid_meal_plan_format(self) -> None:
        """meal_plan がリストでない場合はスキップすること。"""
        rows = [
            {"meal_plan": "invalid"},
            {"meal_plan": None},
            {"meal_plan": 42},
        ]

        mock_supabase = _make_table_supabase_mock(rows)
        result = await plan_repo.get_past_recipe_ids(mock_supabase, uuid4(), weeks=4)

        assert result == []


def _make_recipes(count: int) -> list[Recipe]:
    """テスト用レシピリストを作成する。"""
    return [
        Recipe(
            id=uuid4(),
            title=f"テストレシピ{i + 1}",
            recipe_url=f"https://example.com/recipe/{i + 1}",
            nutrition_per_serving={"kcal": 300 + i * 10, "protein_g": 25.0, "fat_g": 10.0, "carbs_g": 30.0},
            cooking_minutes=20,
        )
        for i in range(count)
    ]


def _make_selection_result(recipes: list[Recipe], staple_match_count: int = 0) -> DinnerSelectionResult:
    return DinnerSelectionResult(
        recipes=recipes,
        staple_match_count=staple_match_count,
        total_count=len(recipes),
        staple_fallback_used=staple_match_count < len(recipes) if staple_match_count > 0 else False,
    )


class TestDeduplicationFallback:
    @pytest.mark.asyncio
    async def test_exclude_ids_passed_to_v3(self) -> None:
        """exclude_recipe_ids が generate_weekly_plan_v3 に渡されること。"""
        mock_recipes = _make_recipes(7)
        exclude_ids = [uuid4(), uuid4()]

        with patch("app.services.weekly_planner.recipe_repo") as mock_repo:
            mock_repo.get_recipes_for_dinner = AsyncMock(return_value=_make_selection_result(mock_recipes))
            await generate_weekly_plan_v3_validated(
                start_date=date(2026, 3, 9),
                pfc_budget=PFCBudget(protein_g=140, fat_g=56, carbs_g=270),
                goal_type="diet",
                supabase=AsyncMock(),
                exclude_recipe_ids=exclude_ids,
            )

            # get_recipes_for_dinner が呼ばれた際の exclude_ids を検証
            call_kwargs = mock_repo.get_recipes_for_dinner.call_args
            passed_exclude = call_kwargs.kwargs.get("exclude_ids") or call_kwargs[1].get("exclude_ids")
            assert passed_exclude is not None
            for eid in exclude_ids:
                assert eid in passed_exclude

    @pytest.mark.asyncio
    async def test_fallback_reduces_exclude_ids_on_insufficient_candidates(self) -> None:
        """候補不足時に exclude_ids を縮小してリトライすること。"""
        mock_recipes_few = _make_recipes(3)
        mock_recipes_enough = _make_recipes(7)
        exclude_ids = [uuid4() for _ in range(10)]

        call_count = 0

        async def mock_get_recipes(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                # 最初は候補不足
                return _make_selection_result(mock_recipes_few)
            else:
                # 2回目以降は十分な候補
                return _make_selection_result(mock_recipes_enough)

        with patch("app.services.weekly_planner.recipe_repo") as mock_repo:
            mock_repo.get_recipes_for_dinner = AsyncMock(side_effect=mock_get_recipes)
            plans, validation = await generate_weekly_plan_v3_validated(
                start_date=date(2026, 3, 9),
                pfc_budget=PFCBudget(protein_g=140, fat_g=56, carbs_g=270),
                goal_type="diet",
                supabase=AsyncMock(),
                exclude_recipe_ids=exclude_ids,
            )

            # 複数回呼ばれていること（リトライ発生）
            assert call_count >= 2
            assert len(plans) == 7

    @pytest.mark.asyncio
    async def test_no_exclude_ids_generates_normally(self) -> None:
        """exclude_ids なしでも正常に生成されること。"""
        mock_recipes = _make_recipes(7)

        with patch("app.services.weekly_planner.recipe_repo") as mock_repo:
            mock_repo.get_recipes_for_dinner = AsyncMock(return_value=_make_selection_result(mock_recipes))
            plans, validation = await generate_weekly_plan_v3_validated(
                start_date=date(2026, 3, 9),
                pfc_budget=PFCBudget(protein_g=140, fat_g=56, carbs_g=270),
                goal_type="diet",
                supabase=AsyncMock(),
            )

        assert len(plans) == 7
