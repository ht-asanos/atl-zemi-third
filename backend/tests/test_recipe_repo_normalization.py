from uuid import uuid4

from app.repositories.recipe_repo import _row_to_recipe


def test_row_to_recipe_filters_noise_ingredients():
    recipe_id = uuid4()
    row = {
        "id": recipe_id,
        "title": "test recipe",
        "recipe_url": "https://example.com/r",
        "servings": 1,
        "tags": [],
    }
    ingredients = [
        {
            "ingredient_name": "or",
            "amount_text": None,
            "amount_g": None,
        },
        {
            "ingredient_name": "〇醤油 / みりん / 酒",
            "amount_text": "各大さじ2",
            "amount_g": None,
        },
    ]

    recipe = _row_to_recipe(row, ingredients)

    assert len(recipe.ingredients) == 1
    assert recipe.ingredients[0].display_ingredient_name == "しょうゆ"
    assert recipe.ingredients[0].alternative_ingredient_names == ["みりん", "酒"]
