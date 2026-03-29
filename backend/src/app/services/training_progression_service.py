from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
from app.repositories import training_progression_repo
from app.schemas.training_progression import (
    TrainingProgressionIngestVideoResult,
    TrainingProgressionPresetReview,
    TrainingProgressionReviewItem,
)
from app.services.training_catalog import DEFAULT_ALIASES, normalize_alias
from app.services.training_progression_extractor import PROGRESSION_MODEL, extract_progression_edges_from_transcript
from app.services.youtube_api import fetch_channel_videos_by_query, resolve_channel_id
from app.services.youtube_transcript_service import (
    TRANSCRIPT_MODEL,
    fetch_transcript,
    get_transcript_naturalization_reason,
    naturalize_auto_transcript,
)

from supabase import AsyncClient

logger = logging.getLogger(__name__)

RETRYABLE_EXISTING_STATUSES = {"failed", "extracted", "no_edges"}


def _edge_payloads(extracted_edges: list[Any]) -> list[dict[str, Any]]:
    return [edge.model_dump() for edge in extracted_edges]


def _build_extraction_diagnostics(
    *,
    transcript_quality: dict[str, Any],
    transcript_original: str,
    transcript_final: str,
    naturalization_reason: str | None,
    extracted_edges: list[Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    edges_payload = _edge_payloads(extracted_edges or [])
    diagnostics = {
        "quality_score": transcript_quality.get("quality_score"),
        "naturalization_applied": naturalization_reason is not None,
        "naturalization_reason": naturalization_reason,
        "naturalizer_model": TRANSCRIPT_MODEL if naturalization_reason else None,
        "transcript_changed": transcript_original != transcript_final,
        "transcript_original_preview": transcript_original[:400],
        "transcript_naturalized_preview": transcript_final[:400],
        "extractor_model": PROGRESSION_MODEL,
        "extraction_count": len(edges_payload),
        "empty_reason_hint": None if edges_payload or error else "no_progression_pattern_detected",
    }
    payload: dict[str, Any] = {"diagnostics": diagnostics, "edges": edges_payload}
    if error:
        payload["error"] = error
    return payload


@dataclass
class TrainingProgressionIngestStats:
    videos_found: int = 0
    videos_scanned: int = 0
    videos_title_matched: int = 0
    videos_processed: int = 0
    transcripts_fetched: int = 0
    transcripts_naturalized: int = 0
    videos_with_edges: int = 0
    edges_created: int = 0


@dataclass(frozen=True)
class CuratedProgressionPreset:
    video_id: str
    from_label_raw: str
    from_reps: int
    to_label_raw: str
    to_reps: int
    from_exercise_id: str
    to_exercise_id: str
    goal_scope: tuple[str, ...]
    review_note: str
    add_aliases: tuple[str, ...] = ()


CURATED_PROGRESSIONS: tuple[CuratedProgressionPreset, ...] = (
    CuratedProgressionPreset(
        video_id="X8-rbhsd2ZY",
        from_label_raw="リバーススキャピュラープッシュアップ",
        from_reps=10,
        to_label_raw="リバースプランクレイズ",
        to_reps=1,
        from_exercise_id="reverse_scapular_push_up",
        to_exercise_id="reverse_plank_raise",
        goal_scope=("bouldering", "strength"),
        review_note="Curated preset for bridge progression",
    ),
    CuratedProgressionPreset(
        video_id="X8-rbhsd2ZY",
        from_label_raw="リバースプランクレイズ",
        from_reps=5,
        to_label_raw="ハーフブリッジリーチ",
        to_reps=1,
        from_exercise_id="reverse_plank_raise",
        to_exercise_id="half_bridge_reach",
        goal_scope=("bouldering", "strength"),
        review_note="Curated preset for bridge progression",
    ),
    CuratedProgressionPreset(
        video_id="X8-rbhsd2ZY",
        from_label_raw="ハーフブリッジリーチ",
        from_reps=3,
        to_label_raw="ウォールブリッジローテーション",
        to_reps=1,
        from_exercise_id="half_bridge_reach",
        to_exercise_id="wall_bridge_rotation",
        goal_scope=("bouldering", "strength"),
        review_note="Curated preset for bridge progression",
    ),
    CuratedProgressionPreset(
        video_id="X8-rbhsd2ZY",
        from_label_raw="ウォールブリッジローテーション",
        from_reps=2,
        to_label_raw="ブリッジ",
        to_reps=1,
        from_exercise_id="wall_bridge_rotation",
        to_exercise_id="bridge",
        goal_scope=("bouldering", "strength"),
        review_note="Curated preset for bridge progression",
    ),
    CuratedProgressionPreset(
        video_id="sNQX-X5J5nI",
        from_label_raw="ディップスバーの上でスイング",
        from_reps=5,
        to_label_raw="スイングタックプラン",
        to_reps=1,
        from_exercise_id="dip_bar_swing",
        to_exercise_id="swing_tuck_planche",
        goal_scope=("bouldering", "strength"),
        review_note="Curated preset for dip-bar planche progression",
    ),
    CuratedProgressionPreset(
        video_id="sNQX-X5J5nI",
        from_label_raw="スイングタックプラン",
        from_reps=5,
        to_label_raw="Lシットタックプラン",
        to_reps=1,
        from_exercise_id="swing_tuck_planche",
        to_exercise_id="l_sit_tuck_planche",
        goal_scope=("bouldering", "strength"),
        review_note="Curated preset for dip-bar planche progression",
    ),
    CuratedProgressionPreset(
        video_id="sNQX-X5J5nI",
        from_label_raw="Lシットタックプラン",
        from_reps=5,
        to_label_raw="タックプランプッシュアップtoLシット",
        to_reps=1,
        from_exercise_id="l_sit_tuck_planche",
        to_exercise_id="tuck_planche_pushup_to_l_sit",
        goal_scope=("bouldering", "strength"),
        review_note="Curated preset for dip-bar planche progression",
    ),
    CuratedProgressionPreset(
        video_id="sNQX-X5J5nI",
        from_label_raw="タックプランプッシュアップtoLシット",
        from_reps=3,
        to_label_raw="白プランプッシュアップ",
        to_reps=1,
        from_exercise_id="tuck_planche_pushup_to_l_sit",
        to_exercise_id="planche_pushup",
        goal_scope=("bouldering", "strength"),
        review_note="Curated preset for dip-bar planche progression",
    ),
)


async def _build_alias_map(supabase: AsyncClient) -> dict[str, str]:
    aliases = {normalize_alias(alias): exercise_id for alias, exercise_id in DEFAULT_ALIASES.items()}
    for row in await training_progression_repo.list_active_aliases(supabase):
        aliases[row["normalized_alias"]] = row["exercise_id"]
    return aliases


def _map_label_to_exercise_id(label: str, alias_map: dict[str, str]) -> str | None:
    return alias_map.get(normalize_alias(label))


def _preset_key(
    *,
    video_id: str,
    from_label_raw: str,
    from_reps: int,
    to_label_raw: str,
    to_reps: int,
) -> tuple[str, str, int, str, int]:
    return (video_id, from_label_raw, from_reps, to_label_raw, to_reps)


def _find_curated_preset(item: TrainingProgressionReviewItem) -> CuratedProgressionPreset | None:
    target_key = _preset_key(
        video_id=item.source.video_id,
        from_label_raw=item.edge.from_label_raw,
        from_reps=item.edge.from_reps,
        to_label_raw=item.edge.to_label_raw,
        to_reps=item.edge.to_reps,
    )
    for preset in CURATED_PROGRESSIONS:
        if (
            preset.video_id,
            preset.from_label_raw,
            preset.from_reps,
            preset.to_label_raw,
            preset.to_reps,
        ) == target_key:
            return preset
    return None


def _preset_to_review_action(preset: CuratedProgressionPreset) -> TrainingProgressionPresetReview:
    return TrainingProgressionPresetReview(
        from_exercise_id=preset.from_exercise_id,
        from_reps=preset.from_reps,
        to_exercise_id=preset.to_exercise_id,
        to_reps=preset.to_reps,
        goal_scope=list(preset.goal_scope),
        review_note=preset.review_note,
        add_aliases=list(preset.add_aliases),
    )


async def list_review_items_with_presets(
    supabase: AsyncClient,
    *,
    review_status: str = "pending",
    limit: int = 100,
) -> list[TrainingProgressionReviewItem]:
    items = await training_progression_repo.list_review_items(supabase, review_status=review_status, limit=limit)
    enriched: list[TrainingProgressionReviewItem] = []
    for item in items:
        preset = _find_curated_preset(item)
        enriched.append(
            item.model_copy(
                update={"preset_review": _preset_to_review_action(preset) if preset else None},
                deep=True,
            )
        )
    return enriched


async def apply_curated_progression_presets(
    supabase: AsyncClient,
    *,
    reviewed_by: UUID,
    limit: int = 200,
) -> tuple[int, int]:
    items = await list_review_items_with_presets(supabase, review_status="pending", limit=limit)
    reviewed = 0
    skipped = 0
    for item in items:
        if item.preset_review is None:
            skipped += 1
            continue
        await review_progression_edge(
            supabase,
            edge_id=item.edge.id,
            reviewed_by=reviewed_by,
            review_status="approved",
            from_exercise_id=item.preset_review.from_exercise_id,
            from_reps=item.preset_review.from_reps,
            to_exercise_id=item.preset_review.to_exercise_id,
            to_reps=item.preset_review.to_reps,
            goal_scope=item.preset_review.goal_scope,
            review_note=item.preset_review.review_note,
            add_aliases=item.preset_review.add_aliases,
        )
        reviewed += 1
    return reviewed, skipped


async def ingest_training_progressions(
    supabase: AsyncClient,
    *,
    http_client: httpx.AsyncClient,
    api_key: str,
    channel_handle: str,
    title_keyword: str,
    max_results: int,
) -> tuple[list[TrainingProgressionIngestVideoResult], TrainingProgressionIngestStats]:
    channel_id = await resolve_channel_id(http_client, api_key, channel_handle)
    if not channel_id:
        raise RuntimeError(f"channel_id を解決できません: {channel_handle}")

    videos = await fetch_channel_videos_by_query(
        http_client,
        api_key,
        channel_id,
        query=title_keyword,
        max_results=max_results,
        include_shorts=True,
    )
    filtered_videos = [video for video in videos if title_keyword in str(video.get("title", ""))]

    stats = TrainingProgressionIngestStats(
        videos_found=len(filtered_videos),
        videos_scanned=len(videos),
        videos_title_matched=len(filtered_videos),
    )
    results: list[TrainingProgressionIngestVideoResult] = []
    alias_map = await _build_alias_map(supabase)

    for video in filtered_videos:
        video_id = str(video["video_id"])
        video_title = str(video.get("title", ""))

        existing = await training_progression_repo.get_source_by_video_id(supabase, video_id)
        if existing is not None and existing.ingest_status not in RETRYABLE_EXISTING_STATUSES:
            results.append(
                TrainingProgressionIngestVideoResult(
                    video_id=video_id,
                    video_title=video_title,
                    status="skipped_existing",
                    source_id=str(existing.id),
                )
            )
            continue

        if existing is not None:
            source = existing
            await training_progression_repo.update_progression_source(
                supabase,
                source_id=source.id,
                ingest_status="fetched",
            )
        else:
            source = await training_progression_repo.create_progression_source(
                supabase,
                channel_handle=channel_handle,
                channel_id=channel_id,
                video_id=video_id,
                video_title=video_title,
                video_url=f"https://www.youtube.com/shorts/{video_id}",
                published_at=video.get("published_at"),
                title_query=title_keyword,
                transcript_text=None,
                transcript_language=None,
                transcript_quality_json=None,
                ingest_status="fetched",
                raw_extraction_json=None,
            )

        try:
            transcript = await fetch_transcript(source.video_url)
        except Exception as exc:
            await training_progression_repo.update_progression_source(
                supabase,
                source_id=source.id,
                ingest_status="no_transcript",
            )
            results.append(
                TrainingProgressionIngestVideoResult(
                    video_id=video_id,
                    video_title=video_title,
                    status="no_transcript",
                    source_id=str(source.id),
                    error=str(exc),
                )
            )
            continue

        stats.transcripts_fetched += 1

        transcript_original = str(transcript.get("text", "") or "").strip()
        transcript_text = transcript_original
        naturalization_reason = get_transcript_naturalization_reason(transcript)
        if naturalization_reason and transcript_text:
            try:
                transcript_text = await naturalize_auto_transcript(transcript_text)
                stats.transcripts_naturalized += 1
            except Exception:
                logger.warning("Training transcript naturalization failed for %s", video_id)

        try:
            extracted_edges = await extract_progression_edges_from_transcript(
                video_title=video_title,
                transcript_text=transcript_text,
            )
        except Exception as exc:
            await training_progression_repo.update_progression_source(
                supabase,
                source_id=source.id,
                ingest_status="failed",
                transcript_text=transcript_text,
                transcript_language=transcript.get("language_code"),
                transcript_quality_json=transcript.get("quality") or {},
                raw_extraction_json=_build_extraction_diagnostics(
                    transcript_quality=transcript.get("quality") or {},
                    transcript_original=transcript_original,
                    transcript_final=transcript_text,
                    naturalization_reason=naturalization_reason,
                    error=str(exc),
                ),
            )
            results.append(
                TrainingProgressionIngestVideoResult(
                    video_id=video_id,
                    video_title=video_title,
                    status="extraction_failed",
                    source_id=str(source.id),
                    error=str(exc),
                )
            )
            continue

        edge_payloads = _edge_payloads(extracted_edges)
        edge_rows = [
            {
                "from_label_raw": edge.from_label,
                "from_exercise_id": _map_label_to_exercise_id(edge.from_label, alias_map),
                "from_reps": edge.from_reps,
                "to_label_raw": edge.to_label,
                "to_exercise_id": _map_label_to_exercise_id(edge.to_label, alias_map),
                "to_reps": edge.to_reps,
                "evidence_text": edge.evidence_text,
                "confidence": edge.confidence,
                "goal_scope": ["bouldering", "strength"],
                "review_status": "pending",
            }
            for edge in extracted_edges
        ]
        created_edges = await training_progression_repo.create_progression_edges(
            supabase,
            source_id=source.id,
            edges=edge_rows,
        )
        await training_progression_repo.update_progression_source(
            supabase,
            source_id=source.id,
            ingest_status="review_pending" if created_edges else "extracted",
            transcript_text=transcript_text,
            transcript_language=transcript.get("language_code"),
            transcript_quality_json=transcript.get("quality") or {},
            raw_extraction_json=_build_extraction_diagnostics(
                transcript_quality=transcript.get("quality") or {},
                transcript_original=transcript_original,
                transcript_final=transcript_text,
                naturalization_reason=naturalization_reason,
                extracted_edges=extracted_edges,
            ),
        )
        stats.videos_processed += 1
        if edge_payloads:
            stats.videos_with_edges += 1
        stats.edges_created += len(created_edges)
        results.append(
            TrainingProgressionIngestVideoResult(
                video_id=video_id,
                video_title=video_title,
                status="review_pending" if created_edges else "no_edges",
                source_id=str(source.id),
                edges_created=len(created_edges),
            )
        )

    return results, stats


async def review_progression_edge(
    supabase: AsyncClient,
    *,
    edge_id: UUID,
    reviewed_by: UUID,
    review_status: str,
    from_exercise_id: str | None,
    from_reps: int | None,
    to_exercise_id: str | None,
    to_reps: int | None,
    goal_scope: list[str] | None,
    review_note: str | None,
    add_aliases: list[str],
) -> None:
    updated = await training_progression_repo.update_progression_edge_review(
        supabase,
        edge_id=edge_id,
        reviewed_by=reviewed_by,
        review_status=review_status,
        from_exercise_id=from_exercise_id,
        from_reps=from_reps,
        to_exercise_id=to_exercise_id,
        to_reps=to_reps,
        goal_scope=goal_scope,
        review_note=review_note,
    )
    alias_rows = []
    if review_status == "approved":
        if updated.from_exercise_id:
            alias_rows.append(
                {
                    "alias": updated.from_label_raw,
                    "normalized_alias": normalize_alias(updated.from_label_raw),
                    "exercise_id": updated.from_exercise_id,
                    "goal_scope": updated.goal_scope or ["bouldering", "strength"],
                }
            )
        if updated.to_exercise_id:
            alias_rows.append(
                {
                    "alias": updated.to_label_raw,
                    "normalized_alias": normalize_alias(updated.to_label_raw),
                    "exercise_id": updated.to_exercise_id,
                    "goal_scope": updated.goal_scope or ["bouldering", "strength"],
                }
            )
    for alias in add_aliases:
        if updated.to_exercise_id:
            alias_rows.append(
                {
                    "alias": alias,
                    "normalized_alias": normalize_alias(alias),
                    "exercise_id": updated.to_exercise_id,
                    "goal_scope": updated.goal_scope or ["bouldering", "strength"],
                }
            )
    await training_progression_repo.upsert_aliases(supabase, aliases=alias_rows)
