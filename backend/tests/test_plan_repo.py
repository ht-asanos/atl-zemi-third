"""plan_repo ユニットテスト — RPC パラメータが正しい型で渡されることを検証"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


def _make_supabase_mock() -> MagicMock:
    """supabase.rpc(...).execute() をモックする AsyncClient。

    rpc() は同期（ビルダーを返す）、execute() が非同期。
    """
    mock = MagicMock()
    rpc_return = MagicMock()
    rpc_return.execute = AsyncMock(return_value=MagicMock())
    mock.rpc.return_value = rpc_return
    return mock


class TestUpsertWeeklyPlans:
    @pytest.mark.asyncio
    async def test_passes_list_not_json_string(self) -> None:
        from app.repositories.plan_repo import upsert_weekly_plans

        supabase = _make_supabase_mock()
        plans = [{"user_id": str(uuid4()), "plan_date": "2026-03-09", "meal_plan": [], "workout_plan": {}}]

        await upsert_weekly_plans(supabase, plans)

        supabase.rpc.assert_called_once()
        call_kwargs = supabase.rpc.call_args[0]
        p_plans = call_kwargs[1]["p_plans"]
        assert isinstance(p_plans, list), f"Expected list, got {type(p_plans)}"


class TestUpdateMealPlan:
    @pytest.mark.asyncio
    async def test_passes_list_not_json_string(self) -> None:
        from app.repositories.plan_repo import update_meal_plan

        supabase = _make_supabase_mock()
        plan_id = uuid4()
        new_meal_plan = [{"name": "test", "amount_g": 100}]

        await update_meal_plan(supabase, plan_id, new_meal_plan)

        supabase.rpc.assert_called_once()
        call_kwargs = supabase.rpc.call_args[0]
        p_new_meal_plan = call_kwargs[1]["p_new_meal_plan"]
        assert isinstance(p_new_meal_plan, list), f"Expected list, got {type(p_new_meal_plan)}"


class TestUpdateDailyPlan:
    @pytest.mark.asyncio
    async def test_passes_dicts_not_json_strings(self) -> None:
        from app.repositories.plan_repo import update_daily_plan

        supabase = _make_supabase_mock()
        plan_id = uuid4()
        meal_plan = [{"name": "test"}]
        workout_plan = {"day_label": "Day1"}
        expected_updated_at = "2026-03-09T12:00:00+00:00"

        await update_daily_plan(supabase, plan_id, meal_plan, workout_plan, expected_updated_at)

        supabase.rpc.assert_called_once()
        call_kwargs = supabase.rpc.call_args[0]
        params = call_kwargs[1]
        assert isinstance(params["p_meal_plan"], list), f"Expected list, got {type(params['p_meal_plan'])}"
        assert isinstance(params["p_workout_plan"], dict), f"Expected dict, got {type(params['p_workout_plan'])}"
