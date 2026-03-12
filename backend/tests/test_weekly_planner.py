"""weekly_planner ユニットテスト（DB 不要）"""

from datetime import date
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.data.food_master import FOOD_MASTER
from app.models.food import FoodCategory, MealType
from app.models.nutrition import PFCBudget
from app.models.recipe import Recipe
from app.services.weekly_planner import generate_weekly_plan, generate_weekly_plan_v3


def _get_staple():
    return next(f for f in FOOD_MASTER if f.category == FoodCategory.STAPLE)


def _get_proteins():
    return [f for f in FOOD_MASTER if f.category == FoodCategory.PROTEIN]


def _get_bulks():
    return [f for f in FOOD_MASTER if f.category == FoodCategory.BULK]


class TestGenerateWeeklyPlan:
    def test_generates_seven_days(self) -> None:
        plans = generate_weekly_plan(
            start_date=date(2026, 3, 9),
            pfc_budget=PFCBudget(protein_g=140, fat_g=56, carbs_g=270),
            staple=_get_staple(),
            goal_type="diet",
            protein_foods=_get_proteins(),
            bulk_foods=_get_bulks(),
        )
        assert len(plans) == 7

    def test_dates_are_consecutive(self) -> None:
        plans = generate_weekly_plan(
            start_date=date(2026, 3, 9),
            pfc_budget=PFCBudget(protein_g=140, fat_g=56, carbs_g=270),
            staple=_get_staple(),
            goal_type="strength",
            protein_foods=_get_proteins(),
            bulk_foods=_get_bulks(),
        )
        for i, plan in enumerate(plans):
            assert plan.plan_date == date(2026, 3, 9 + i)

    def test_training_day_cycles_diet(self) -> None:
        """diet テンプレートは2日型 → 7日で3.5サイクル"""
        plans = generate_weekly_plan(
            start_date=date(2026, 3, 9),
            pfc_budget=PFCBudget(protein_g=140, fat_g=56, carbs_g=270),
            staple=_get_staple(),
            goal_type="diet",
            protein_foods=_get_proteins(),
            bulk_foods=_get_bulks(),
        )
        labels = [p.training_day.day_label for p in plans if p.training_day is not None]
        assert labels == ["全身A", "全身B", "全身A", "全身B", "全身A", "全身B", "全身A"]

    def test_training_day_cycles_strength(self) -> None:
        """strength テンプレートは3日型 → 7日で2.33サイクル"""
        plans = generate_weekly_plan(
            start_date=date(2026, 3, 9),
            pfc_budget=PFCBudget(protein_g=140, fat_g=56, carbs_g=270),
            staple=_get_staple(),
            goal_type="strength",
            protein_foods=_get_proteins(),
            bulk_foods=_get_bulks(),
        )
        labels = [p.training_day.day_label for p in plans if p.training_day is not None]
        assert labels == ["Push", "Pull", "Legs", "Push", "Pull", "Legs", "Push"]

    def test_all_meals_use_specified_staple(self) -> None:
        staple = _get_staple()
        plans = generate_weekly_plan(
            start_date=date(2026, 3, 9),
            pfc_budget=PFCBudget(protein_g=140, fat_g=56, carbs_g=270),
            staple=staple,
            goal_type="bouldering",
            protein_foods=_get_proteins(),
            bulk_foods=_get_bulks(),
        )
        for plan in plans:
            for meal in plan.meals:
                assert meal.staple.name == staple.name

    def test_each_day_has_three_meals(self) -> None:
        plans = generate_weekly_plan(
            start_date=date(2026, 3, 9),
            pfc_budget=PFCBudget(protein_g=140, fat_g=56, carbs_g=270),
            staple=_get_staple(),
            goal_type="diet",
            protein_foods=_get_proteins(),
            bulk_foods=_get_bulks(),
        )
        for plan in plans:
            assert len(plan.meals) == 3

    def test_bouldering_has_rest_days_in_classic_generation(self) -> None:
        plans = generate_weekly_plan(
            start_date=date(2026, 3, 9),
            pfc_budget=PFCBudget(protein_g=140, fat_g=56, carbs_g=270),
            staple=_get_staple(),
            goal_type="bouldering",
            protein_foods=_get_proteins(),
            bulk_foods=_get_bulks(),
        )
        assert plans[0].training_day is not None
        assert plans[1].training_day is None
        assert plans[2].training_day is not None
        assert plans[3].training_day is None
        assert plans[4].training_day is not None
        assert plans[5].training_day is None
        assert plans[6].training_day is not None


class TestGenerateWeeklyPlanV3:
    def _make_mock_recipes(self, count: int = 7) -> list[Recipe]:
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

    @pytest.mark.asyncio
    async def test_generates_seven_days(self) -> None:
        mock_recipes = self._make_mock_recipes(7)
        with patch("app.services.weekly_planner.recipe_repo") as mock_repo:
            mock_repo.get_recipes_for_dinner = AsyncMock(return_value=mock_recipes)
            plans = await generate_weekly_plan_v3(
                start_date=date(2026, 3, 9),
                pfc_budget=PFCBudget(protein_g=140, fat_g=56, carbs_g=270),
                goal_type="diet",
                supabase=AsyncMock(),
            )
        assert len(plans) == 7

    @pytest.mark.asyncio
    async def test_each_day_has_three_meals(self) -> None:
        mock_recipes = self._make_mock_recipes(7)
        with patch("app.services.weekly_planner.recipe_repo") as mock_repo:
            mock_repo.get_recipes_for_dinner = AsyncMock(return_value=mock_recipes)
            plans = await generate_weekly_plan_v3(
                start_date=date(2026, 3, 9),
                pfc_budget=PFCBudget(protein_g=140, fat_g=56, carbs_g=270),
                goal_type="diet",
                supabase=AsyncMock(),
            )
        for plan in plans:
            assert len(plan.meals) == 3

    @pytest.mark.asyncio
    async def test_meal_types_are_correct(self) -> None:
        mock_recipes = self._make_mock_recipes(7)
        with patch("app.services.weekly_planner.recipe_repo") as mock_repo:
            mock_repo.get_recipes_for_dinner = AsyncMock(return_value=mock_recipes)
            plans = await generate_weekly_plan_v3(
                start_date=date(2026, 3, 9),
                pfc_budget=PFCBudget(protein_g=140, fat_g=56, carbs_g=270),
                goal_type="diet",
                supabase=AsyncMock(),
            )
        for plan in plans:
            assert plan.meals[0].meal_type == MealType.BREAKFAST
            assert plan.meals[1].meal_type == MealType.LUNCH
            assert plan.meals[2].meal_type == MealType.DINNER

    @pytest.mark.asyncio
    async def test_dinner_recipes_are_unique(self) -> None:
        mock_recipes = self._make_mock_recipes(7)
        with patch("app.services.weekly_planner.recipe_repo") as mock_repo:
            mock_repo.get_recipes_for_dinner = AsyncMock(return_value=mock_recipes)
            plans = await generate_weekly_plan_v3(
                start_date=date(2026, 3, 9),
                pfc_budget=PFCBudget(protein_g=140, fat_g=56, carbs_g=270),
                goal_type="diet",
                supabase=AsyncMock(),
            )
        dinner_titles = [p.meals[2].recipe["title"] for p in plans]
        assert len(set(dinner_titles)) == 7

    @pytest.mark.asyncio
    async def test_dates_are_consecutive(self) -> None:
        mock_recipes = self._make_mock_recipes(7)
        with patch("app.services.weekly_planner.recipe_repo") as mock_repo:
            mock_repo.get_recipes_for_dinner = AsyncMock(return_value=mock_recipes)
            plans = await generate_weekly_plan_v3(
                start_date=date(2026, 3, 9),
                pfc_budget=PFCBudget(protein_g=140, fat_g=56, carbs_g=270),
                goal_type="diet",
                supabase=AsyncMock(),
            )
        for i, plan in enumerate(plans):
            assert plan.plan_date == date(2026, 3, 9 + i)

    @pytest.mark.asyncio
    async def test_fallback_when_few_recipes(self) -> None:
        """レシピが7件未満でもフォールバックで7日分生成される"""
        mock_recipes = self._make_mock_recipes(3)
        with patch("app.services.weekly_planner.recipe_repo") as mock_repo:
            mock_repo.get_recipes_for_dinner = AsyncMock(return_value=mock_recipes)
            plans = await generate_weekly_plan_v3(
                start_date=date(2026, 3, 9),
                pfc_budget=PFCBudget(protein_g=140, fat_g=56, carbs_g=270),
                goal_type="diet",
                supabase=AsyncMock(),
            )
        assert len(plans) == 7
        # 最初の3日はレシピあり、残り4日はフォールバック
        for i in range(3):
            assert plans[i].meals[2].recipe is not None
        for i in range(3, 7):
            assert plans[i].meals[2].recipe is None

    @pytest.mark.asyncio
    async def test_bouldering_has_rest_days(self) -> None:
        mock_recipes = self._make_mock_recipes(7)
        with patch("app.services.weekly_planner.recipe_repo") as mock_repo:
            mock_repo.get_recipes_for_dinner = AsyncMock(return_value=mock_recipes)
            plans = await generate_weekly_plan_v3(
                start_date=date(2026, 3, 9),
                pfc_budget=PFCBudget(protein_g=140, fat_g=56, carbs_g=270),
                goal_type="bouldering",
                supabase=AsyncMock(),
            )

        assert plans[0].training_day is not None
        assert plans[1].training_day is None
        assert plans[2].training_day is not None
        assert plans[3].training_day is None
        assert plans[4].training_day is not None
        assert plans[5].training_day is None
        assert plans[6].training_day is not None

    @pytest.mark.asyncio
    async def test_bouldering_adjustment_scale_and_forearm_protection(self) -> None:
        mock_recipes = self._make_mock_recipes(7)
        with patch("app.services.weekly_planner.recipe_repo") as mock_repo:
            mock_repo.get_recipes_for_dinner = AsyncMock(return_value=mock_recipes)
            plans = await generate_weekly_plan_v3(
                start_date=date(2026, 3, 9),
                pfc_budget=PFCBudget(protein_g=140, fat_g=56, carbs_g=270),
                goal_type="bouldering",
                supabase=AsyncMock(),
                training_scale=0.9,
                protect_forearms=True,
            )

        training_days = [p.training_day for p in plans if p.training_day is not None]
        assert training_days, "at least one training day should exist"
        for day in training_days:
            for ex in day.exercises:
                assert ex.sets >= 1
                assert ex.muscle_group.value != "forearms"
