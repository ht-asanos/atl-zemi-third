import pytest
from app.data.food_master import FOOD_MASTER
from app.models.food import FoodCategory, MealType
from app.models.nutrition import PFCBudget
from app.models.recipe import Recipe
from app.services.meal_suggestion import (
    _make_breakfast,
    _make_dinner_from_recipe,
    _make_lunch,
    calc_dinner_budget,
    calc_remaining_budget,
    generate_daily_meals,
    generate_structured_daily_meals,
    get_bulk_foods,
    get_protein_foods,
    get_staple_foods,
    suggest_meal,
)


class TestFoodMasterData:
    def test_staple_count(self) -> None:
        assert len(get_staple_foods()) == 5

    def test_protein_count(self) -> None:
        assert len(get_protein_foods()) == 4

    def test_bulk_count(self) -> None:
        assert len(get_bulk_foods()) == 3

    def test_total_count(self) -> None:
        assert len(FOOD_MASTER) == 12

    def test_all_categories_present(self) -> None:
        categories = {f.category for f in FOOD_MASTER}
        assert categories == {FoodCategory.STAPLE, FoodCategory.PROTEIN, FoodCategory.BULK}


class TestCalcRemainingBudget:
    def test_basic(self) -> None:
        daily = PFCBudget(protein_g=140, fat_g=56, carbs_g=270)
        staple = get_staple_foods()[0]  # 冷凍うどん
        remaining = calc_remaining_budget(daily, meals_per_day=3, staple=staple)
        # protein: 140/3 - 5.2 = 41.47
        assert remaining.protein_g == pytest.approx(41.5, abs=0.1)
        assert remaining.fat_g >= 0
        assert remaining.carbs_g >= 0


class TestSuggestMeal:
    def test_within_budget(self) -> None:
        remaining = PFCBudget(protein_g=40, fat_g=15, carbs_g=50)
        staple = get_staple_foods()[0]
        meal = suggest_meal(staple, remaining)
        assert meal.total_price_yen <= 500
        assert meal.total_cooking_minutes <= 10
        assert meal.total_kcal > 0

    def test_has_protein_source(self) -> None:
        remaining = PFCBudget(protein_g=40, fat_g=15, carbs_g=50)
        staple = get_staple_foods()[0]
        meal = suggest_meal(staple, remaining)
        assert len(meal.protein_sources) > 0


class TestGenerateDailyMeals:
    def test_generates_three_meals(self) -> None:
        daily = PFCBudget(protein_g=140, fat_g=56, carbs_g=270)
        staple = get_staple_foods()[0]
        meals = generate_daily_meals(daily, staple)
        assert len(meals) == 3

    def test_all_meals_have_staple(self) -> None:
        daily = PFCBudget(protein_g=140, fat_g=56, carbs_g=270)
        staple = get_staple_foods()[0]
        meals = generate_daily_meals(daily, staple)
        for meal in meals:
            assert meal.staple.name == staple.name


# --- recipe モード用テスト ---


class TestMakeBreakfast:
    def test_returns_breakfast_meal_type(self) -> None:
        meal = _make_breakfast()
        assert meal.meal_type == MealType.BREAKFAST

    def test_staple_is_yogurt_or_natto(self) -> None:
        meal = _make_breakfast()
        assert meal.staple.name in ("ヨーグルト", "納豆")

    def test_no_protein_or_bulk(self) -> None:
        meal = _make_breakfast()
        assert meal.protein_sources == []
        assert meal.bulk_items == []

    def test_nutrition_matches_staple(self) -> None:
        meal = _make_breakfast()
        assert meal.total_kcal == meal.staple.kcal_per_serving
        assert meal.total_protein_g == meal.staple.protein_g


class TestMakeLunch:
    def test_returns_lunch_meal_type(self) -> None:
        meal = _make_lunch()
        assert meal.meal_type == MealType.LUNCH

    def test_is_onigiri(self) -> None:
        meal = _make_lunch()
        assert meal.staple.name == "おにぎり"

    def test_no_protein_or_bulk(self) -> None:
        meal = _make_lunch()
        assert meal.protein_sources == []
        assert meal.bulk_items == []


class TestMakeDinnerFromRecipe:
    def _make_recipe(self) -> Recipe:
        from uuid import uuid4

        return Recipe(
            id=uuid4(),
            title="テスト鶏肉料理",
            recipe_url="https://example.com/recipe/1",
            image_url="https://example.com/image.jpg",
            cooking_minutes=20,
            nutrition_per_serving={"kcal": 350, "protein_g": 25.0, "fat_g": 10.0, "carbs_g": 30.0},
        )

    def test_returns_dinner_meal_type(self) -> None:
        recipe = self._make_recipe()
        meal = _make_dinner_from_recipe(recipe)
        assert meal.meal_type == MealType.DINNER

    def test_recipe_field_is_set(self) -> None:
        recipe = self._make_recipe()
        meal = _make_dinner_from_recipe(recipe)
        assert meal.recipe is not None
        assert meal.recipe["title"] == "テスト鶏肉料理"
        assert meal.recipe["recipe_url"] == "https://example.com/recipe/1"
        assert meal.recipe["nutrition_per_serving"] == {
            "kcal": 350,
            "protein_g": 25.0,
            "fat_g": 10.0,
            "carbs_g": 30.0,
        }

    def test_staple_name_is_recipe_title(self) -> None:
        recipe = self._make_recipe()
        meal = _make_dinner_from_recipe(recipe)
        assert meal.staple.name == "テスト鶏肉料理"

    def test_nutrition_from_recipe(self) -> None:
        recipe = self._make_recipe()
        meal = _make_dinner_from_recipe(recipe)
        assert meal.total_kcal == 350
        assert meal.total_protein_g == 25.0
        assert meal.total_fat_g == 10.0
        assert meal.total_carbs_g == 30.0


class TestCalcDinnerBudget:
    def test_subtracts_breakfast_and_lunch(self) -> None:
        daily = PFCBudget(protein_g=140, fat_g=56, carbs_g=270)
        breakfast = _make_breakfast()
        lunch = _make_lunch()
        budget = calc_dinner_budget(daily, breakfast, lunch)
        assert budget.protein_g == pytest.approx(140 - breakfast.total_protein_g - lunch.total_protein_g, abs=0.1)
        assert budget.fat_g >= 0
        assert budget.carbs_g >= 0

    def test_never_negative(self) -> None:
        daily = PFCBudget(protein_g=0, fat_g=0, carbs_g=0)
        breakfast = _make_breakfast()
        lunch = _make_lunch()
        budget = calc_dinner_budget(daily, breakfast, lunch)
        assert budget.protein_g == 0
        assert budget.fat_g == 0
        assert budget.carbs_g == 0


class TestGenerateStructuredDailyMeals:
    def test_returns_three_meals(self) -> None:
        meals = generate_structured_daily_meals(recipe=None)
        assert len(meals) == 3

    def test_meal_types_order(self) -> None:
        meals = generate_structured_daily_meals(recipe=None)
        assert meals[0].meal_type == MealType.BREAKFAST
        assert meals[1].meal_type == MealType.LUNCH
        assert meals[2].meal_type == MealType.DINNER

    def test_with_recipe(self) -> None:
        from uuid import uuid4

        recipe = Recipe(
            id=uuid4(),
            title="テストレシピ",
            recipe_url="https://example.com/recipe/1",
            nutrition_per_serving={"kcal": 400, "protein_g": 30.0, "fat_g": 15.0, "carbs_g": 40.0},
        )
        meals = generate_structured_daily_meals(recipe=recipe)
        assert len(meals) == 3
        assert meals[2].recipe is not None
        assert meals[2].recipe["title"] == "テストレシピ"

    def test_without_recipe_uses_fallback(self) -> None:
        meals = generate_structured_daily_meals(recipe=None)
        assert meals[2].meal_type == MealType.DINNER
        assert meals[2].recipe is None
