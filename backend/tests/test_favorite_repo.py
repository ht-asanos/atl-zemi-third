"""favorite_repo のテスト。"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.repositories.favorite_repo import add_favorite, get_favorite_recipe_ids, remove_favorite


def _make_supabase_table_chain(**execute_data):
    """supabase.table(...).method(...).method(...).execute() のチェーンモック。"""
    supabase = MagicMock()
    chain = MagicMock()
    # すべてのメソッド呼び出しが同じchainを返すようにする
    chain.insert.return_value = chain
    chain.delete.return_value = chain
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.execute = AsyncMock(return_value=MagicMock(**execute_data))
    supabase.table.return_value = chain
    return supabase, chain


@pytest.mark.asyncio
async def test_add_favorite():
    user_id = uuid4()
    recipe_id = uuid4()
    fav_id = uuid4()

    supabase, chain = _make_supabase_table_chain(data=[{"id": str(fav_id)}])

    result = await add_favorite(supabase, user_id, recipe_id)
    assert result == fav_id
    chain.insert.assert_called_once_with({"user_id": str(user_id), "recipe_id": str(recipe_id)})


@pytest.mark.asyncio
async def test_remove_favorite():
    user_id = uuid4()
    recipe_id = uuid4()

    supabase, _ = _make_supabase_table_chain(data=[{"id": str(uuid4())}])

    result = await remove_favorite(supabase, user_id, recipe_id)
    assert result is True


@pytest.mark.asyncio
async def test_remove_favorite_not_found():
    user_id = uuid4()
    recipe_id = uuid4()

    supabase, _ = _make_supabase_table_chain(data=[])

    result = await remove_favorite(supabase, user_id, recipe_id)
    assert result is False


@pytest.mark.asyncio
async def test_get_favorite_recipe_ids():
    user_id = uuid4()
    r1 = uuid4()
    r2 = uuid4()

    supabase, _ = _make_supabase_table_chain(
        data=[
            {"recipe_id": str(r1)},
            {"recipe_id": str(r2)},
        ]
    )

    result = await get_favorite_recipe_ids(supabase, user_id)
    assert result == {r1, r2}
