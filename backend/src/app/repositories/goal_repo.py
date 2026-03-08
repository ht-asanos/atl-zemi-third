from typing import Any
from uuid import UUID

from app.schemas.goal import GoalResponse

from supabase import AsyncClient


def _row_to_goal(row: dict[str, Any]) -> GoalResponse:
    return GoalResponse(
        id=UUID(row["id"]),
        goal_type=row["goal_type"],
        target_kcal=row["target_kcal"],
        protein_g=row["protein_g"],
        fat_g=row["fat_g"],
        carbs_g=row["carbs_g"],
    )


async def upsert_goal(
    supabase: AsyncClient,
    user_id: UUID,
    goal_type: str,
    target_kcal: float,
    protein_g: float,
    fat_g: float,
    carbs_g: float,
) -> GoalResponse:
    response = (
        await supabase.table("goals")
        .upsert(
            {
                "user_id": str(user_id),
                "goal_type": goal_type,
                "target_kcal": target_kcal,
                "protein_g": protein_g,
                "fat_g": fat_g,
                "carbs_g": carbs_g,
            },
            on_conflict="user_id,goal_type",
        )
        .execute()
    )
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    return _row_to_goal(rows[0])


async def get_latest_goal(supabase: AsyncClient, user_id: UUID) -> GoalResponse | None:
    response = (
        await supabase.table("goals")
        .select("*")
        .eq("user_id", str(user_id))
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    if not rows:
        return None
    return _row_to_goal(rows[0])
