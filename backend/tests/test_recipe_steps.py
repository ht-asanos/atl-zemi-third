from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.models.food import NutritionStatus
from app.models.recipe import Recipe, RecipeIngredient, RecipeStep
from app.services.recipe_steps import ensure_generated_steps


def _sample_recipe() -> Recipe:
    return Recipe(
        id=uuid4(),
        title="卵うどん",
        description="簡単なうどん",
        image_url=None,
        recipe_url="https://example.com",
        ingredients=[
            RecipeIngredient(ingredient_name="冷凍うどん", amount_text="1玉"),
            RecipeIngredient(ingredient_name="卵", amount_text="1個"),
        ],
        servings=1,
        cooking_minutes=10,
        tags=["うどん"],
        nutrition_status=NutritionStatus.CALCULATED,
    )


@pytest.mark.asyncio
async def test_ensure_generated_steps_success():
    recipe = _sample_recipe()
    supabase = MagicMock()
    query = MagicMock()
    query.update.return_value = query
    query.eq.return_value = query
    query.execute = AsyncMock(return_value=None)
    supabase.table.return_value = query
    with (
        patch("app.services.recipe_steps.settings.google_api_key", "test-key"),
        patch(
            "app.services.recipe_steps.generate_steps_for_recipe",
            new=AsyncMock(
                return_value=[
                    RecipeStep(step_no=1, text="鍋に湯を沸かし、うどんを入れる", est_minutes=3),
                ]
            ),
        ),
    ):
        updated = await ensure_generated_steps(supabase, recipe)
    assert updated.steps_status == "generated"
    assert len(updated.generated_steps) == 1
    supabase.table.assert_called_once_with("recipes")


@pytest.mark.asyncio
async def test_ensure_generated_steps_without_key_keeps_pending():
    recipe = _sample_recipe()
    supabase = MagicMock()
    with patch("app.services.recipe_steps.settings.google_api_key", ""):
        updated = await ensure_generated_steps(supabase, recipe)
    assert updated.steps_status == "pending"
    supabase.table.assert_not_called()
