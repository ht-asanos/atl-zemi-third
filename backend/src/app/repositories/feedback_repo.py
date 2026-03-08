from typing import Any
from uuid import UUID

from app.schemas.feedback import FeedbackTagResponse

from supabase import AsyncClient


def _row_to_tag(row: dict[str, Any]) -> FeedbackTagResponse:
    return FeedbackTagResponse(
        id=UUID(row["id"]),
        tag=row["tag"],
        source_text=row["source_text"],
        created_at=row["created_at"],
    )


async def create_feedback_tags(
    supabase: AsyncClient,
    user_id: UUID,
    plan_id: UUID,
    tags: list[str],
    source_text: str,
) -> list[FeedbackTagResponse]:
    rows = [
        {
            "user_id": str(user_id),
            "plan_id": str(plan_id),
            "tag": tag,
            "source_text": source_text,
        }
        for tag in tags
    ]
    if not rows:
        rows = [
            {
                "user_id": str(user_id),
                "plan_id": str(plan_id),
                "tag": "__no_tag__",
                "source_text": source_text,
            }
        ]
    response = await supabase.table("feedback_tags").insert(rows).execute()
    result_rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    return [_row_to_tag(r) for r in result_rows if r["tag"] != "__no_tag__"]


async def get_feedback_tags_by_plan(supabase: AsyncClient, user_id: UUID, plan_id: UUID) -> list[FeedbackTagResponse]:
    response = (
        await supabase.table("feedback_tags")
        .select("*")
        .eq("user_id", str(user_id))
        .eq("plan_id", str(plan_id))
        .neq("tag", "__no_tag__")
        .execute()
    )
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    return [_row_to_tag(row) for row in rows]


async def create_plan_revision(
    supabase: AsyncClient,
    plan_id: UUID,
    user_id: UUID,
    previous_plan: dict[str, Any],
    new_plan: dict[str, Any],
    reason: str,
) -> UUID:
    row = {
        "plan_id": str(plan_id),
        "user_id": str(user_id),
        "previous_plan": previous_plan,
        "new_plan": new_plan,
        "reason": reason,
    }
    response = await supabase.table("plan_revisions").insert(row).execute()
    result_rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    return UUID(result_rows[0]["id"])
