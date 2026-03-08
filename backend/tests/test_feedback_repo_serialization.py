"""feedback_repo の create_plan_revision が dict をそのまま渡すことを確認する。"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.repositories.feedback_repo import create_plan_revision


@pytest.fixture
def mock_supabase():
    supabase = MagicMock()
    table_mock = MagicMock()
    insert_mock = MagicMock()
    insert_mock.execute = AsyncMock(return_value=MagicMock(data=[{"id": str(uuid4())}]))
    table_mock.insert.return_value = insert_mock
    supabase.table.return_value = table_mock
    return supabase


@pytest.mark.asyncio
async def test_create_plan_revision_passes_dict_not_json_string(mock_supabase):
    plan_id = uuid4()
    user_id = uuid4()
    previous_plan = {"breakfast": "ヨーグルト", "dinner": "鶏むね肉"}
    new_plan = {"breakfast": "納豆", "dinner": "豚肉"}

    await create_plan_revision(mock_supabase, plan_id, user_id, previous_plan, new_plan, "test reason")

    mock_supabase.table.assert_called_once_with("plan_revisions")
    insert_call = mock_supabase.table.return_value.insert.call_args[0][0]

    # dict がそのまま渡される（json.dumps 文字列ではない）
    assert isinstance(insert_call["previous_plan"], dict)
    assert isinstance(insert_call["new_plan"], dict)
    assert insert_call["previous_plan"] == previous_plan
    assert insert_call["new_plan"] == new_plan
