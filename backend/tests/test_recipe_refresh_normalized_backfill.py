from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.models.food import MextFood
from app.services.recipe_refresh import backfill_missing_normalized_ingredients


@pytest.mark.asyncio
async def test_backfill_missing_normalized_ingredients_adds_missing_foods():
    supabase = Mock()
    query = Mock()
    supabase.table.return_value = query
    query.select.return_value = query
    query.execute = AsyncMock(
        return_value=SimpleNamespace(
            data=[
                {"ingredient_name": "醤油 / みりん / 酒"},
                {"ingredient_name": "生きしめん(うどんでも)"},
            ]
        )
    )

    mext = MextFood(
        mext_food_id="dummy_1",
        name="みりん",
        category_code="17",
        category_name="調味料及び香辛料類",
        kcal_per_100g=240.0,
        protein_g_per_100g=0.3,
        fat_g_per_100g=0.0,
        carbs_g_per_100g=43.2,
    )

    async def _search_existing(_supabase, name: str, limit: int = 1):
        if name == "しょうゆ":
            return [mext]
        return []

    with (
        patch("app.services.recipe_refresh.mext_food_repo.search_by_name", side_effect=_search_existing),
        patch("app.services.recipe_refresh.search_foods_by_name", new=AsyncMock(return_value=[mext])),
        patch("app.services.recipe_refresh.mext_food_repo.upsert_foods", new=AsyncMock(return_value=1)),
    ):
        result = await backfill_missing_normalized_ingredients(supabase, AsyncMock())

    assert result["normalized_names"] == 4  # しょうゆ, みりん, 酒, 生きしめん
    assert result["added_foods"] == 3
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_backfill_missing_normalized_ingredients_collects_missing_names():
    supabase = Mock()
    query = Mock()
    supabase.table.return_value = query
    query.select.return_value = query
    query.execute = AsyncMock(
        return_value=SimpleNamespace(
            data=[
                {"ingredient_name": "未知の調味料"},
            ]
        )
    )

    with (
        patch("app.services.recipe_refresh.mext_food_repo.search_by_name", new=AsyncMock(return_value=[])),
        patch("app.services.recipe_refresh.search_foods_by_name", new=AsyncMock(return_value=[])),
    ):
        result = await backfill_missing_normalized_ingredients(supabase, AsyncMock())

    assert result["normalized_names"] == 1
    assert result["added_foods"] == 0
    assert result["missing_names"] == ["未知の調味料"]
