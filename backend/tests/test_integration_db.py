"""DB 統合テスト — Supabase ローカル必須

実行条件: supabase start 済み
実行方法: uv run pytest -v -m integration
"""

import os

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def supabase_url():
    url = os.environ.get("SUPABASE_URL", "http://127.0.0.1:54321")
    return url


@pytest.fixture(scope="module")
def supabase_service_key():
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        pytest.skip("SUPABASE_SERVICE_ROLE_KEY not set — skipping DB integration tests")
    return key


@pytest.fixture(scope="module")
def anon_key():
    key = os.environ.get("SUPABASE_ANON_KEY")
    if not key:
        pytest.skip("SUPABASE_ANON_KEY not set — skipping DB integration tests")
    return key


class TestFoodMasterRead:
    """food_master テーブルにシードデータが存在することを確認"""

    @pytest.mark.asyncio
    async def test_food_master_has_data(self, supabase_url, anon_key) -> None:
        from supabase import acreate_client

        client = await acreate_client(supabase_url, anon_key)
        response = await client.table("food_master").select("*").execute()
        assert len(response.data) >= 12


class TestRPCFunctions:
    """RPC 関数の存在確認（実データ操作は認証が必要）"""

    @pytest.mark.asyncio
    async def test_upsert_weekly_plans_rpc_exists(self, supabase_url, anon_key) -> None:
        from supabase import acreate_client

        client = await acreate_client(supabase_url, anon_key)
        # 空配列で呼び出し — 関数が存在することを確認
        try:
            await client.rpc("upsert_weekly_plans", {"p_plans": []}).execute()
        except Exception as e:
            # RLS でブロックされる可能性があるが、関数自体は存在する
            assert "function" not in str(e).lower() or "does not exist" not in str(e).lower()


class TestWeeklyPlanRPC:
    """実 RPC で upsert_weekly_plans → 取得 → 削除"""

    @pytest.mark.asyncio
    async def test_upsert_and_retrieve_weekly_plans(self, supabase_url, supabase_service_key) -> None:
        from datetime import date, timedelta
        from uuid import uuid4

        from supabase import acreate_client

        client = await acreate_client(supabase_url, supabase_service_key)

        # テスト用ユーザーを auth.users に作成
        test_email = f"test-plan-{uuid4().hex[:8]}@example.com"
        user_resp = await client.auth.admin.create_user(
            {
                "email": test_email,
                "password": "testpassword123",
                "email_confirm": True,
            }
        )
        user_id = user_resp.user.id
        start = date(2099, 1, 1)  # 未来日でテストデータ衝突回避

        try:
            # profiles, goals を seed
            await (
                client.table("profiles")
                .insert(
                    {
                        "id": str(user_id),
                        "age": 25,
                        "gender": "male",
                        "height_cm": 170,
                        "weight_kg": 70,
                        "activity_level": "moderate",
                    }
                )
                .execute()
            )
            await (
                client.table("goals")
                .insert(
                    {
                        "user_id": str(user_id),
                        "goal_type": "diet",
                        "target_kcal": 2000,
                        "protein_g": 120,
                        "fat_g": 50,
                        "carbs_g": 250,
                    }
                )
                .execute()
            )

            # upsert_weekly_plans に list[dict] を渡す（json.dumps なし）
            plans = [
                {
                    "user_id": str(user_id),
                    "plan_date": (start + timedelta(days=i)).isoformat(),
                    "meal_plan": [{"meal": f"day{i}"}],
                    "workout_plan": {"day_label": f"Day{i}"},
                }
                for i in range(7)
            ]
            await client.rpc("upsert_weekly_plans", {"p_plans": plans}).execute()

            # 取得して 7 件であることを確認
            resp = await (
                client.table("daily_plans")
                .select("*")
                .eq("user_id", str(user_id))
                .gte("plan_date", start.isoformat())
                .order("plan_date")
                .execute()
            )
            assert len(resp.data) == 7
            assert resp.data[0]["meal_plan"] == [{"meal": "day0"}]

        finally:
            # クリーンアップ
            await client.table("daily_plans").delete().eq("user_id", str(user_id)).execute()
            await client.table("goals").delete().eq("user_id", str(user_id)).execute()
            await client.table("profiles").delete().eq("id", str(user_id)).execute()
            await client.auth.admin.delete_user(user_id)
