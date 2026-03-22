import logging
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from app.schemas.plan import DailyPlanResponse

from supabase import AsyncClient

logger = logging.getLogger(__name__)


def _row_to_plan(row: dict[str, Any]) -> DailyPlanResponse:
    plan_meta = row.get("plan_meta")
    return DailyPlanResponse(
        id=UUID(row["id"]),
        plan_date=row["plan_date"],
        meal_plan=row["meal_plan"],
        workout_plan=row["workout_plan"],
        plan_meta=plan_meta,
    )


async def get_past_recipe_ids(supabase: AsyncClient, user_id: UUID, weeks: int = 4) -> list[UUID]:
    """過去N週分のプランから使用レシピIDを抽出する。

    daily_plans テーブルから過去 weeks 週分のプランを取得し、
    夕食の recipe.id を収集してユニークなリストとして返す。
    """
    end_date = date.today()
    start_date = end_date - timedelta(weeks=weeks)
    response = (
        await supabase.table("daily_plans")
        .select("meal_plan")
        .eq("user_id", str(user_id))
        .gte("plan_date", start_date.isoformat())
        .lte("plan_date", end_date.isoformat())
        .execute()
    )
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]

    seen: set[UUID] = set()
    for row in rows:
        meal_plan = row.get("meal_plan")
        if not isinstance(meal_plan, list):
            continue
        for meal in meal_plan:
            if meal.get("meal_type") != "dinner":
                continue
            recipe_data = meal.get("recipe")
            if recipe_data and isinstance(recipe_data, dict):
                rid = recipe_data.get("id")
                if rid:
                    try:
                        seen.add(UUID(rid))
                    except (ValueError, AttributeError):
                        logger.warning("過去レシピIDのパースに失敗: %s", rid)
    return list(seen)


async def upsert_weekly_plans(supabase: AsyncClient, plans: list[dict[str, Any]]) -> None:
    await supabase.rpc("upsert_weekly_plans", {"p_plans": plans}).execute()


async def get_weekly_plans(supabase: AsyncClient, user_id: UUID, start_date: date) -> list[DailyPlanResponse]:
    end_date = start_date + timedelta(days=6)
    response = (
        await supabase.table("daily_plans")
        .select("*")
        .eq("user_id", str(user_id))
        .gte("plan_date", start_date.isoformat())
        .lte("plan_date", end_date.isoformat())
        .order("plan_date")
        .execute()
    )
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    return [_row_to_plan(row) for row in rows]


async def get_daily_plan(supabase: AsyncClient, plan_id: UUID) -> DailyPlanResponse | None:
    response = await supabase.table("daily_plans").select("*").eq("id", str(plan_id)).limit(1).execute()
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    if not rows:
        return None
    return _row_to_plan(rows[0])


async def get_daily_plan_by_user(supabase: AsyncClient, plan_id: UUID, user_id: UUID) -> DailyPlanResponse | None:
    response = (
        await supabase.table("daily_plans")
        .select("*")
        .eq("id", str(plan_id))
        .eq("user_id", str(user_id))
        .limit(1)
        .execute()
    )
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    if not rows:
        return None
    return _row_to_plan(rows[0])


async def get_daily_plan_row_by_user(supabase: AsyncClient, plan_id: UUID, user_id: UUID) -> dict[str, Any] | None:
    """Raw row including updated_at for optimistic locking."""
    response = (
        await supabase.table("daily_plans")
        .select("*")
        .eq("id", str(plan_id))
        .eq("user_id", str(user_id))
        .limit(1)
        .execute()
    )
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    if not rows:
        return None
    return rows[0]


async def update_meal_plan(supabase: AsyncClient, plan_id: UUID, new_meal_plan: Any) -> None:
    await supabase.rpc(
        "update_meal_plan",
        {"p_plan_id": str(plan_id), "p_new_meal_plan": new_meal_plan},
    ).execute()


async def update_daily_plan(
    supabase: AsyncClient,
    plan_id: UUID,
    meal_plan: Any,
    workout_plan: Any,
    expected_updated_at: str,
) -> None:
    """楽観ロック付き daily_plan 更新。

    expected_updated_at: UTC タイムゾーン付き ISO 8601 文字列
                         (例: "2026-03-09T12:00:00+00:00")
    """
    await supabase.rpc(
        "update_daily_plan",
        {
            "p_plan_id": str(plan_id),
            "p_meal_plan": meal_plan,
            "p_workout_plan": workout_plan,
            "p_expected_updated_at": expected_updated_at,
        },
    ).execute()


async def update_week_plan_meta(
    supabase: AsyncClient,
    user_id: UUID,
    start_date: date,
    plan_meta: dict[str, Any],
) -> None:
    end_date = start_date + timedelta(days=6)
    await (
        supabase.table("daily_plans")
        .update({"plan_meta": plan_meta})
        .eq("user_id", str(user_id))
        .gte("plan_date", start_date.isoformat())
        .lte("plan_date", end_date.isoformat())
        .execute()
    )
