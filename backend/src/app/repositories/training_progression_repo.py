from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.schemas.training_progression import (
    TrainingProgressionEdgeResponse,
    TrainingProgressionReviewItem,
    TrainingProgressionSourceResponse,
)

from supabase import AsyncClient


def _row_to_source(row: dict[str, Any]) -> TrainingProgressionSourceResponse:
    return TrainingProgressionSourceResponse(
        id=UUID(row["id"]),
        platform=row["platform"],
        channel_handle=row["channel_handle"],
        channel_id=row.get("channel_id"),
        video_id=row["video_id"],
        video_title=row["video_title"],
        video_url=row["video_url"],
        published_at=row.get("published_at"),
        title_query=row.get("title_query"),
        transcript_language=row.get("transcript_language"),
        transcript_quality_json=row.get("transcript_quality_json") or {},
        ingest_status=row["ingest_status"],
        raw_extraction_json=row.get("raw_extraction_json"),
        created_at=row["created_at"],
    )


def _row_to_edge(row: dict[str, Any]) -> TrainingProgressionEdgeResponse:
    return TrainingProgressionEdgeResponse(
        id=UUID(row["id"]),
        source_id=UUID(row["source_id"]),
        from_label_raw=row["from_label_raw"],
        from_exercise_id=row.get("from_exercise_id"),
        from_reps=row["from_reps"],
        to_label_raw=row["to_label_raw"],
        to_exercise_id=row.get("to_exercise_id"),
        to_reps=row["to_reps"],
        relation_type=row["relation_type"],
        goal_scope=row.get("goal_scope") or [],
        evidence_text=row.get("evidence_text"),
        confidence=float(row.get("confidence") or 0.0),
        review_status=row["review_status"],
        review_note=row.get("review_note"),
        reviewed_by=UUID(row["reviewed_by"]) if row.get("reviewed_by") else None,
        reviewed_at=row.get("reviewed_at"),
        created_at=row["created_at"],
    )


async def get_source_by_video_id(supabase: AsyncClient, video_id: str) -> TrainingProgressionSourceResponse | None:
    response = (
        await supabase.table("training_progression_sources").select("*").eq("video_id", video_id).limit(1).execute()
    )
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    if not rows:
        return None
    return _row_to_source(rows[0])


async def create_progression_source(
    supabase: AsyncClient,
    *,
    channel_handle: str,
    channel_id: str | None,
    video_id: str,
    video_title: str,
    video_url: str,
    published_at: str | None,
    title_query: str | None,
    transcript_text: str | None,
    transcript_language: str | None,
    transcript_quality_json: dict[str, Any] | None,
    ingest_status: str,
    raw_extraction_json: Any | None,
) -> TrainingProgressionSourceResponse:
    response = await (
        supabase.table("training_progression_sources")
        .insert(
            {
                "channel_handle": channel_handle,
                "channel_id": channel_id,
                "video_id": video_id,
                "video_title": video_title,
                "video_url": video_url,
                "published_at": published_at,
                "title_query": title_query,
                "transcript_text": transcript_text,
                "transcript_language": transcript_language,
                "transcript_quality_json": transcript_quality_json or {},
                "ingest_status": ingest_status,
                "raw_extraction_json": raw_extraction_json,
            }
        )
        .execute()
    )
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    return _row_to_source(rows[0])


async def update_progression_source(
    supabase: AsyncClient,
    *,
    source_id: UUID,
    ingest_status: str,
    transcript_text: str | None = None,
    transcript_language: str | None = None,
    transcript_quality_json: dict[str, Any] | None = None,
    raw_extraction_json: Any | None = None,
) -> None:
    payload: dict[str, Any] = {"ingest_status": ingest_status}
    if transcript_text is not None:
        payload["transcript_text"] = transcript_text
    if transcript_language is not None:
        payload["transcript_language"] = transcript_language
    if transcript_quality_json is not None:
        payload["transcript_quality_json"] = transcript_quality_json
    if raw_extraction_json is not None:
        payload["raw_extraction_json"] = raw_extraction_json

    await supabase.table("training_progression_sources").update(payload).eq("id", str(source_id)).execute()


async def create_progression_edges(
    supabase: AsyncClient,
    *,
    source_id: UUID,
    edges: list[dict[str, Any]],
) -> list[TrainingProgressionEdgeResponse]:
    if not edges:
        return []
    response = await (
        supabase.table("training_progression_edges")
        .insert(
            [
                {
                    "source_id": str(source_id),
                    "from_label_raw": edge["from_label_raw"],
                    "from_exercise_id": edge.get("from_exercise_id"),
                    "from_reps": edge["from_reps"],
                    "to_label_raw": edge["to_label_raw"],
                    "to_exercise_id": edge.get("to_exercise_id"),
                    "to_reps": edge["to_reps"],
                    "relation_type": edge.get("relation_type", "unlock_if_can_do"),
                    "goal_scope": edge.get("goal_scope") or ["bouldering", "strength"],
                    "evidence_text": edge.get("evidence_text"),
                    "confidence": edge.get("confidence", 0.0),
                    "review_status": edge.get("review_status", "pending"),
                }
                for edge in edges
            ]
        )
        .execute()
    )
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    return [_row_to_edge(row) for row in rows]


async def list_progression_sources(
    supabase: AsyncClient,
    *,
    limit: int = 50,
) -> list[TrainingProgressionSourceResponse]:
    response = (
        await supabase.table("training_progression_sources")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    return [_row_to_source(row) for row in rows]


async def list_review_items(
    supabase: AsyncClient,
    *,
    review_status: str = "pending",
    limit: int = 100,
) -> list[TrainingProgressionReviewItem]:
    edge_resp = (
        await supabase.table("training_progression_edges")
        .select("*")
        .eq("review_status", review_status)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    edge_rows: list[dict[str, Any]] = edge_resp.data  # type: ignore[assignment]
    if not edge_rows:
        return []
    source_ids = list({row["source_id"] for row in edge_rows})
    source_resp = await supabase.table("training_progression_sources").select("*").in_("id", source_ids).execute()
    source_rows: list[dict[str, Any]] = source_resp.data  # type: ignore[assignment]
    sources = {row["id"]: _row_to_source(row) for row in source_rows}
    return [
        TrainingProgressionReviewItem(
            edge=_row_to_edge(edge_row),
            source=sources[edge_row["source_id"]],
        )
        for edge_row in edge_rows
        if edge_row["source_id"] in sources
    ]


async def update_progression_edge_review(
    supabase: AsyncClient,
    *,
    edge_id: UUID,
    reviewed_by: UUID,
    review_status: str,
    from_exercise_id: str | None = None,
    from_reps: int | None = None,
    to_exercise_id: str | None = None,
    to_reps: int | None = None,
    goal_scope: list[str] | None = None,
    review_note: str | None = None,
) -> TrainingProgressionEdgeResponse:
    payload: dict[str, Any] = {
        "review_status": review_status,
        "reviewed_by": str(reviewed_by),
        "reviewed_at": datetime.now(UTC).isoformat(),
        "review_note": review_note,
    }
    if from_exercise_id is not None:
        payload["from_exercise_id"] = from_exercise_id
    if from_reps is not None:
        payload["from_reps"] = from_reps
    if to_exercise_id is not None:
        payload["to_exercise_id"] = to_exercise_id
    if to_reps is not None:
        payload["to_reps"] = to_reps
    if goal_scope is not None:
        payload["goal_scope"] = goal_scope

    response = await supabase.table("training_progression_edges").update(payload).eq("id", str(edge_id)).execute()
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    return _row_to_edge(rows[0])


async def upsert_aliases(
    supabase: AsyncClient,
    *,
    aliases: list[dict[str, Any]],
) -> None:
    if not aliases:
        return
    await (
        supabase.table("training_exercise_aliases")
        .upsert(
            aliases,
            on_conflict="normalized_alias,exercise_id",
        )
        .execute()
    )


async def list_active_aliases(supabase: AsyncClient) -> list[dict[str, Any]]:
    response = await supabase.table("training_exercise_aliases").select("*").eq("is_active", True).execute()
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    return rows


async def list_approved_edges(
    supabase: AsyncClient,
    *,
    goal_type: str | None = None,
) -> list[TrainingProgressionEdgeResponse]:
    response = (
        await supabase.table("training_progression_edges")
        .select("*")
        .eq("review_status", "approved")
        .order("confidence", desc=True)
        .execute()
    )
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    edges = [_row_to_edge(row) for row in rows]
    if goal_type is None:
        return edges
    return [edge for edge in edges if not edge.goal_scope or goal_type in edge.goal_scope]
