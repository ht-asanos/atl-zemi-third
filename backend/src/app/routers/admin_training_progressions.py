from uuid import UUID

import httpx
from app.config import settings
from app.dependencies.auth import get_admin_user_id
from app.dependencies.supabase_client import get_service_supabase
from app.exceptions import AppException, ErrorCode
from app.models.training import Exercise
from app.repositories import training_progression_repo
from app.schemas.training_progression import (
    AdminTrainingProgressionGraphResponse,
    TrainingProgressionApplyPresetsResponse,
    TrainingProgressionIngestRequest,
    TrainingProgressionIngestResponse,
    TrainingProgressionReviewActionRequest,
    TrainingProgressionReviewListResponse,
    TrainingProgressionSourceListResponse,
)
from app.services.training_catalog import get_exercise_catalog
from app.services.training_progression_service import (
    apply_curated_progression_presets,
    ingest_training_progressions,
    list_review_items_with_presets,
    review_progression_edge,
)
from app.services.training_skill_tree_service import build_admin_training_progression_graph
from fastapi import APIRouter, Depends, Query

from supabase import AsyncClient

router = APIRouter(prefix="/admin/training-progressions", tags=["admin"])


@router.get("/catalog", response_model=list[Exercise])
async def list_progression_catalog(
    user_id: UUID = Depends(get_admin_user_id),
) -> list[Exercise]:
    del user_id
    catalog = get_exercise_catalog()
    return [catalog[key] for key in sorted(catalog.keys())]


@router.post("/ingest", response_model=TrainingProgressionIngestResponse)
async def ingest_progressions(
    body: TrainingProgressionIngestRequest,
    user_id: UUID = Depends(get_admin_user_id),
    supabase: AsyncClient = Depends(get_service_supabase),
) -> TrainingProgressionIngestResponse:
    del user_id
    if not settings.youtube_api_key:
        raise AppException(ErrorCode.VALIDATION_ERROR, 422, "YOUTUBE_API_KEY が未設定です")
    if not settings.google_api_key:
        raise AppException(ErrorCode.VALIDATION_ERROR, 422, "GOOGLE_API_KEY が未設定です")

    async with httpx.AsyncClient(timeout=60.0) as http_client:
        results, stats = await ingest_training_progressions(
            supabase,
            http_client=http_client,
            api_key=settings.youtube_api_key,
            channel_handle=body.channel_handle,
            title_keyword=body.title_keyword,
            max_results=body.max_results,
        )

    return TrainingProgressionIngestResponse(
        channel_handle=body.channel_handle,
        title_keyword=body.title_keyword,
        videos_found=stats.videos_found,
        videos_scanned=stats.videos_scanned,
        videos_title_matched=stats.videos_title_matched,
        videos_processed=stats.videos_processed,
        transcripts_fetched=stats.transcripts_fetched,
        transcripts_naturalized=stats.transcripts_naturalized,
        videos_with_edges=stats.videos_with_edges,
        edges_created=stats.edges_created,
        results=results,
    )


@router.get("/sources", response_model=TrainingProgressionSourceListResponse)
async def list_progression_sources(
    limit: int = Query(50, ge=1, le=200),
    user_id: UUID = Depends(get_admin_user_id),
    supabase: AsyncClient = Depends(get_service_supabase),
) -> TrainingProgressionSourceListResponse:
    del user_id
    items = await training_progression_repo.list_progression_sources(supabase, limit=limit)
    return TrainingProgressionSourceListResponse(items=items, total=len(items))


@router.get("/review", response_model=TrainingProgressionReviewListResponse)
async def list_progression_review(
    limit: int = Query(100, ge=1, le=200),
    status: str = Query("pending"),
    user_id: UUID = Depends(get_admin_user_id),
    supabase: AsyncClient = Depends(get_service_supabase),
) -> TrainingProgressionReviewListResponse:
    del user_id
    items = await list_review_items_with_presets(supabase, review_status=status, limit=limit)
    return TrainingProgressionReviewListResponse(items=items, total=len(items))


@router.get("/graph", response_model=AdminTrainingProgressionGraphResponse)
async def get_progression_graph(
    status: str = Query("approved"),
    goal_type: str = Query("all"),
    limit: int = Query(200, ge=1, le=500),
    user_id: UUID = Depends(get_admin_user_id),
    supabase: AsyncClient = Depends(get_service_supabase),
) -> AdminTrainingProgressionGraphResponse:
    del user_id
    return await build_admin_training_progression_graph(
        supabase,
        review_status=status,
        goal_type=goal_type,
        limit=limit,
    )


@router.post("/apply-presets", response_model=TrainingProgressionApplyPresetsResponse)
async def apply_progression_presets(
    user_id: UUID = Depends(get_admin_user_id),
    supabase: AsyncClient = Depends(get_service_supabase),
) -> TrainingProgressionApplyPresetsResponse:
    reviewed, skipped = await apply_curated_progression_presets(
        supabase,
        reviewed_by=user_id,
    )
    return TrainingProgressionApplyPresetsResponse(reviewed=reviewed, skipped=skipped)


@router.post("/review/{edge_id}")
async def review_progression(
    edge_id: UUID,
    body: TrainingProgressionReviewActionRequest,
    user_id: UUID = Depends(get_admin_user_id),
    supabase: AsyncClient = Depends(get_service_supabase),
) -> dict[str, str]:
    await review_progression_edge(
        supabase,
        edge_id=edge_id,
        reviewed_by=user_id,
        review_status=body.review_status,
        from_exercise_id=body.from_exercise_id,
        from_reps=body.from_reps,
        to_exercise_id=body.to_exercise_id,
        to_reps=body.to_reps,
        goal_scope=body.goal_scope,
        review_note=body.review_note,
        add_aliases=body.add_aliases,
    )
    return {"status": "ok"}
