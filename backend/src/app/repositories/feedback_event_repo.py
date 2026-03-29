from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from app.schemas.feedback import (
    AdaptationEventResponse,
    FeedbackEventDetailResponse,
    FeedbackEventResponse,
    FeedbackEventTagResponse,
)

from supabase import AsyncClient


def _row_to_feedback_event(row: dict[str, Any]) -> FeedbackEventResponse:
    return FeedbackEventResponse(
        id=UUID(row["id"]),
        plan_id=UUID(row["plan_id"]) if row.get("plan_id") else None,
        domain=row["domain"],
        meal_type=row.get("meal_type"),
        exercise_id=row.get("exercise_id"),
        source_text=row["source_text"],
        satisfaction=row.get("satisfaction"),
        rpe=row.get("rpe"),
        completed=row.get("completed"),
        created_at=row["created_at"],
    )


def _row_to_feedback_event_tag(row: dict[str, Any]) -> FeedbackEventTagResponse:
    return FeedbackEventTagResponse(
        id=UUID(row["id"]),
        event_id=UUID(row["event_id"]),
        tag=row["tag"],
        tag_source=row["tag_source"],
        created_at=row["created_at"],
    )


def _row_to_adaptation_event(row: dict[str, Any]) -> AdaptationEventResponse:
    return AdaptationEventResponse(
        id=UUID(row["id"]),
        feedback_event_id=UUID(row["feedback_event_id"]),
        plan_revision_id=UUID(row["plan_revision_id"]) if row.get("plan_revision_id") else None,
        domain=row["domain"],
        target_type=row["target_type"],
        target_ref=row.get("target_ref"),
        before_snapshot=row.get("before_snapshot"),
        after_snapshot=row.get("after_snapshot"),
        change_summary_json=row.get("change_summary_json") or [],
        created_at=row["created_at"],
    )


async def create_feedback_event(
    supabase: AsyncClient,
    *,
    user_id: UUID,
    plan_id: UUID,
    domain: str,
    source_text: str,
    meal_type: str | None = None,
    exercise_id: str | None = None,
    satisfaction: int | None = None,
    rpe: float | None = None,
    completed: bool | None = None,
) -> UUID:
    response = await (
        supabase.table("feedback_events")
        .insert(
            {
                "user_id": str(user_id),
                "plan_id": str(plan_id),
                "domain": domain,
                "meal_type": meal_type,
                "exercise_id": exercise_id,
                "source_text": source_text,
                "satisfaction": satisfaction,
                "rpe": rpe,
                "completed": completed,
            }
        )
        .execute()
    )
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    return UUID(rows[0]["id"])


async def create_feedback_event_tags(
    supabase: AsyncClient,
    *,
    event_id: UUID,
    tags: list[str],
    tag_source: str = "llm",
) -> list[UUID]:
    if not tags:
        return []
    response = await (
        supabase.table("feedback_event_tags")
        .insert([{"event_id": str(event_id), "tag": tag, "tag_source": tag_source} for tag in tags])
        .execute()
    )
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    return [UUID(row["id"]) for row in rows]


async def create_adaptation_events(
    supabase: AsyncClient,
    *,
    feedback_event_id: UUID,
    plan_revision_id: UUID | None,
    events: list[dict[str, Any]],
) -> list[UUID]:
    if not events:
        return []
    rows = [
        {
            "feedback_event_id": str(feedback_event_id),
            "plan_revision_id": str(plan_revision_id) if plan_revision_id else None,
            "domain": event["domain"],
            "target_type": event["target_type"],
            "target_ref": event.get("target_ref"),
            "before_snapshot": event["before_snapshot"],
            "after_snapshot": event["after_snapshot"],
            "change_summary_json": event.get("change_summary_json") or [],
        }
        for event in events
    ]
    response = await supabase.table("adaptation_events").insert(rows).execute()
    inserted: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    return [UUID(row["id"]) for row in inserted]


async def get_feedback_history(
    supabase: AsyncClient,
    *,
    user_id: UUID,
    limit: int = 20,
) -> list[FeedbackEventDetailResponse]:
    response = (
        await supabase.table("feedback_events")
        .select("*")
        .eq("user_id", str(user_id))
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    events = [_row_to_feedback_event(row) for row in rows]
    return await _hydrate_feedback_history(supabase, events)


async def get_feedback_events_in_range(
    supabase: AsyncClient,
    *,
    user_id: UUID,
    start_date: date,
    end_date: date,
    domain: str | None = None,
) -> list[FeedbackEventDetailResponse]:
    query = (
        supabase.table("feedback_events")
        .select("*")
        .eq("user_id", str(user_id))
        .gte("created_at", f"{start_date.isoformat()}T00:00:00")
        .lt("created_at", f"{end_date.isoformat()}T00:00:00")
        .order("created_at", desc=True)
    )
    if domain is not None:
        query = query.eq("domain", domain)
    response = await query.execute()
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    events = [_row_to_feedback_event(row) for row in rows]
    return await _hydrate_feedback_history(supabase, events)


async def get_feedback_event_detail(
    supabase: AsyncClient,
    *,
    user_id: UUID,
    event_id: UUID,
) -> FeedbackEventDetailResponse | None:
    response = (
        await supabase.table("feedback_events")
        .select("*")
        .eq("id", str(event_id))
        .eq("user_id", str(user_id))
        .limit(1)
        .execute()
    )
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    if not rows:
        return None
    event = _row_to_feedback_event(rows[0])
    hydrated = await _hydrate_feedback_history(supabase, [event])
    return hydrated[0]


async def _hydrate_feedback_history(
    supabase: AsyncClient,
    events: list[FeedbackEventResponse],
) -> list[FeedbackEventDetailResponse]:
    if not events:
        return []
    event_ids = [str(event.id) for event in events]

    tags_resp = await supabase.table("feedback_event_tags").select("*").in_("event_id", event_ids).execute()
    tags_rows: list[dict[str, Any]] = tags_resp.data  # type: ignore[assignment]
    adaptation_resp = (
        await supabase.table("adaptation_events").select("*").in_("feedback_event_id", event_ids).execute()
    )
    adaptation_rows: list[dict[str, Any]] = adaptation_resp.data  # type: ignore[assignment]

    tags_by_event: dict[str, list[FeedbackEventTagResponse]] = {}
    for row in tags_rows:
        tag = _row_to_feedback_event_tag(row)
        tags_by_event.setdefault(str(tag.event_id), []).append(tag)

    adaptations_by_event: dict[str, list[AdaptationEventResponse]] = {}
    for row in adaptation_rows:
        event = _row_to_adaptation_event(row)
        adaptations_by_event.setdefault(str(event.feedback_event_id), []).append(event)

    return [
        FeedbackEventDetailResponse(
            **event.model_dump(),
            tags=tags_by_event.get(str(event.id), []),
            adaptation_events=adaptations_by_event.get(str(event.id), []),
        )
        for event in events
    ]
