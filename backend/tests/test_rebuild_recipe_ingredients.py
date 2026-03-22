from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_cmd_rebuild_recipe_ingredients_dedupes_before_rematch():
    supabase = MagicMock()
    recipe_id = "11111111-1111-1111-1111-111111111111"

    recipes_resp = MagicMock(data=[{"id": recipe_id, "title": "テストレシピ"}])
    ingredients_resp = MagicMock(
        data=[
            {"ingredient_name": "うどん", "amount_text": "2玉"},
            {"ingredient_name": "うどん", "amount_text": "2玉"},
            {"ingredient_name": "醤油", "amount_text": "大さじ1"},
        ]
    )

    recipes_table = MagicMock()
    recipes_table.select.return_value.execute = AsyncMock(return_value=recipes_resp)

    ingredients_table = MagicMock()
    ingredients_table.select.return_value.eq.return_value.execute = AsyncMock(return_value=ingredients_resp)

    def table_side_effect(name: str):
        if name == "recipes":
            return recipes_table
        if name == "recipe_ingredients":
            return ingredients_table
        raise AssertionError(name)

    supabase.table.side_effect = table_side_effect

    with (
        patch("app.services.cli.recipe_commands._get_service_client", new=AsyncMock(return_value=supabase)),
        patch(
            "app.services.cli.recipe_commands.match_recipe_ingredients", new=AsyncMock(return_value=[{}])
        ) as mock_match,
        patch("app.services.cli.recipe_commands.calculate_recipe_nutrition", new=AsyncMock()) as mock_nutrition,
    ):
        mock_nutrition.return_value.matched_count = 2
        mock_nutrition.return_value.total_count = 2
        mock_nutrition.return_value.status.value = "estimated"

        from app.services.cli.recipe_commands import cmd_rebuild_recipe_ingredients

        await cmd_rebuild_recipe_ingredients()

    passed_ingredients = mock_match.await_args.args[2]
    assert passed_ingredients == [
        {"ingredient_name": "うどん", "amount_text": "2玉"},
        {"ingredient_name": "醤油", "amount_text": "大さじ1"},
    ]
