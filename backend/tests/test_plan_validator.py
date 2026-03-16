"""プラン品質検証のテスト。"""

from datetime import date

from app.models.food import (
    FoodCategory,
    FoodItem,
    MealSuggestion,
    MealType,
    NutritionStatus,
)
from app.services.plan_validator import validate_weekly_plan
from app.services.weekly_planner import DailyPlanData


def _dummy_staple() -> FoodItem:
    return FoodItem(
        name="テスト",
        category=FoodCategory.STAPLE,
        kcal_per_serving=300,
        protein_g=10,
        fat_g=5,
        carbs_g=40,
        serving_unit="1人前",
    )


def _make_dinner(
    recipe_id: str = "r1",
    kcal: float = 400,
    status: NutritionStatus = NutritionStatus.CALCULATED,
) -> MealSuggestion:
    return MealSuggestion(
        meal_type=MealType.DINNER,
        staple=_dummy_staple(),
        protein_sources=[],
        bulk_items=[],
        total_kcal=kcal,
        total_protein_g=25,
        total_fat_g=15,
        total_carbs_g=30,
        total_price_yen=0,
        total_cooking_minutes=20,
        recipe={"id": recipe_id, "title": "レシピ"},
        nutrition_status=status,
    )


def _make_plan(day_offset: int, dinner: MealSuggestion) -> DailyPlanData:
    return DailyPlanData(
        plan_date=date(2026, 3, 16) + __import__("datetime").timedelta(days=day_offset),
        meals=[dinner],
        training_day=None,
    )


class TestValidateWeeklyPlan:
    def test_valid_plan(self):
        plans = [_make_plan(i, _make_dinner(recipe_id=f"r{i}")) for i in range(7)]
        result = validate_weekly_plan(plans)
        assert result.is_valid is True
        assert result.issues == []

    def test_failed_nutrition_makes_invalid(self):
        plans = [_make_plan(0, _make_dinner(status=NutritionStatus.FAILED))]
        result = validate_weekly_plan(plans)
        assert result.is_valid is False
        assert result.metrics["failed_count"] == 1

    def test_zero_kcal_makes_invalid(self):
        plans = [_make_plan(0, _make_dinner(kcal=0))]
        result = validate_weekly_plan(plans)
        assert result.is_valid is False
        assert result.metrics["zero_kcal_count"] == 1

    def test_high_duplicate_rate_makes_invalid(self):
        # 7 days, all same recipe → dup_rate = 6/7 ≈ 0.86
        plans = [_make_plan(i, _make_dinner(recipe_id="same")) for i in range(7)]
        result = validate_weekly_plan(plans)
        assert result.is_valid is False
        assert result.metrics["dup_rate"] > 0.3

    def test_estimated_status_is_valid(self):
        plans = [_make_plan(0, _make_dinner(status=NutritionStatus.ESTIMATED))]
        result = validate_weekly_plan(plans)
        assert result.is_valid is True

    def test_metrics_accuracy(self):
        plans = [_make_plan(i, _make_dinner(recipe_id=f"r{i}")) for i in range(7)]
        result = validate_weekly_plan(plans)
        assert result.metrics["total_dinners"] == 7
        assert result.metrics["unique_recipes"] == 7
        assert result.metrics["dup_rate"] == 0.0
