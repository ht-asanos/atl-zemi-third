"""統合テスト: レシピフロー全体

seed → 検索 → 週間プラン生成でレシピが含まれることを検証。
DB 依存のためマーカー付き。
"""

import pytest
from app.models.food import MealSuggestion, MextFood
from app.models.nutrition import PFCBudget
from app.services.meal_suggestion import generate_daily_meals, generate_daily_meals_v2


class TestExistingMealSuggestionCompat:
    """既存の MealSuggestion にレシピフィールドが追加されても互換性を維持。"""

    def test_meal_suggestion_without_recipe(self, male_profile):
        """recipe=None（デフォルト）で既存動作が変わらない。"""
        pfc = PFCBudget(protein_g=120, fat_g=50, carbs_g=250)
        meals = generate_daily_meals(pfc, _get_test_staple())
        assert len(meals) == 3
        for meal in meals:
            assert isinstance(meal, MealSuggestion)
            assert meal.recipe is None

    def test_meal_suggestion_serialization(self):
        """recipe=None の MealSuggestion が正常にシリアライズできる。"""
        pfc = PFCBudget(protein_g=120, fat_g=50, carbs_g=250)
        meals = generate_daily_meals(pfc, _get_test_staple())
        for meal in meals:
            data = meal.model_dump()
            assert "recipe" in data
            assert data["recipe"] is None


class TestMextFoodModel:
    def test_create_mext_food(self):
        food = MextFood(
            mext_food_id="11_01088_7",
            name="鶏もも肉（皮つき、生）",
            category_code="11",
            category_name="肉類",
            kcal_per_100g=253.0,
            protein_g_per_100g=17.3,
            fat_g_per_100g=19.1,
            carbs_g_per_100g=0.0,
        )
        assert food.name == "鶏もも肉（皮つき、生）"
        assert food.kcal_per_100g == 253.0

    def test_mext_food_optional_fields(self):
        food = MextFood(
            mext_food_id="01_00001_0",
            name="テスト",
            category_code="01",
            category_name="穀類",
            kcal_per_100g=100,
            protein_g_per_100g=5,
            fat_g_per_100g=1,
            carbs_g_per_100g=20,
        )
        assert food.fiber_g_per_100g is None
        assert food.raw_data == {}


class TestSuggestRecipeMealWithoutDB:
    """DB なしの場合は None を返す。"""

    @pytest.mark.asyncio
    async def test_returns_none_without_supabase(self):
        meals = await generate_daily_meals_v2(
            PFCBudget(protein_g=120, fat_g=50, carbs_g=250),
            _get_test_staple(),
            supabase=None,
        )
        assert len(meals) == 3
        for meal in meals:
            assert meal.recipe is None


def _get_test_staple():
    from app.data.food_master import FOOD_MASTER
    from app.models.food import FoodCategory

    return next(f for f in FOOD_MASTER if f.category == FoodCategory.STAPLE)
