"""栄養フォールバック推定のテスト。"""

from uuid import uuid4

from app.models.recipe import Recipe
from app.services.nutrition_fallback import CATEGORY_AVERAGES, get_fallback_nutrition


def _make_recipe(title: str = "テストレシピ", tags: list[str] | None = None) -> Recipe:
    return Recipe(
        id=uuid4(),
        title=title,
        recipe_url="https://example.com",
        tags=tags or [],
    )


class TestGetFallbackNutrition:
    def test_meat_by_title(self):
        recipe = _make_recipe(title="鶏もも肉の照り焼き")
        result = get_fallback_nutrition(recipe)
        assert result == CATEGORY_AVERAGES["肉"]

    def test_meat_by_keyword(self):
        recipe = _make_recipe(title="簡単ハンバーグ")
        result = get_fallback_nutrition(recipe)
        assert result == CATEGORY_AVERAGES["肉"]

    def test_fish_by_title(self):
        recipe = _make_recipe(title="鮭のムニエル")
        result = get_fallback_nutrition(recipe)
        assert result == CATEGORY_AVERAGES["魚"]

    def test_fish_by_tag(self):
        recipe = _make_recipe(title="おかず", tags=["海鮮"])
        result = get_fallback_nutrition(recipe)
        assert result == CATEGORY_AVERAGES["魚"]

    def test_vegetable_by_title(self):
        recipe = _make_recipe(title="野菜たっぷりスープ")
        result = get_fallback_nutrition(recipe)
        assert result == CATEGORY_AVERAGES["野菜"]

    def test_default_fallback(self):
        recipe = _make_recipe(title="おいしいもの")
        result = get_fallback_nutrition(recipe)
        assert result == CATEGORY_AVERAGES["default"]

    def test_always_returns_positive_values(self):
        recipe = _make_recipe(title="不明なレシピ")
        result = get_fallback_nutrition(recipe)
        assert result is not None
        assert result["kcal"] > 0
        assert result["protein_g"] > 0
        assert result["fat_g"] > 0
        assert result["carbs_g"] > 0

    def test_returns_new_dict(self):
        """返値が元辞書の参照でないことを確認。"""
        recipe = _make_recipe(title="鶏肉料理")
        result = get_fallback_nutrition(recipe)
        result["kcal"] = 0
        assert CATEGORY_AVERAGES["肉"]["kcal"] != 0
