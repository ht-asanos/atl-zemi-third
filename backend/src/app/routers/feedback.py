import logging
from uuid import UUID

from app.dependencies.auth import get_current_user_id
from app.dependencies.supabase_client import get_authenticated_supabase
from app.repositories import feedback_repo, food_repo, plan_repo
from app.schemas.feedback import AdaptationResponse, CreateFeedbackRequest, FeedbackTagResponse
from app.services import adaptation_engine, tag_extractor
from fastapi import APIRouter, Depends, HTTPException, status

from supabase import AsyncClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=AdaptationResponse)
async def create_feedback(
    body: CreateFeedbackRequest,
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> AdaptationResponse:
    # 1. 所有権チェック付きでプラン取得 (raw row for updated_at)
    plan_row = await plan_repo.get_daily_plan_row_by_user(supabase, body.plan_id, user_id)
    if plan_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    # 2. タグ抽出
    result = await tag_extractor.extract_tags(body.source_text)

    # 3. タグ保存 (extraction_status に関わらずテキストは保存)
    await feedback_repo.create_feedback_tags(supabase, user_id, body.plan_id, result.tags, body.source_text)

    # 4. タグ 0 件 → early return
    if not result.tags:
        return AdaptationResponse(
            tags_applied=[],
            changes_summary=[],
            extraction_status=result.status,
            new_plan=None,
        )

    # 5. 適応実行
    current_plan = {
        "meal_plan": plan_row["meal_plan"],
        "workout_plan": plan_row["workout_plan"],
    }

    # 現在の主食名を取得
    current_staple_name = ""
    meal_plan = plan_row.get("meal_plan", [])
    if isinstance(meal_plan, list) and meal_plan:
        first_meal = meal_plan[0]
        if isinstance(first_meal, dict) and "staple" in first_meal:
            current_staple_name = first_meal["staple"].get("name", "")

    available_staples = await food_repo.get_staple_foods(supabase)

    new_plan, changes = adaptation_engine.adapt_plan(current_plan, result.tags, available_staples, current_staple_name)

    # 6. 楽観ロック付きプラン更新
    try:
        await plan_repo.update_daily_plan(
            supabase,
            body.plan_id,
            new_plan["meal_plan"],
            new_plan["workout_plan"],
            plan_row["updated_at"],
        )
    except Exception as e:
        error_msg = str(e)
        if "40001" in error_msg or "Conflict" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflict: plan was modified by another operation",
            ) from e
        raise

    # 7. リビジョン保存
    await feedback_repo.create_plan_revision(
        supabase,
        body.plan_id,
        user_id,
        previous_plan=current_plan,
        new_plan=new_plan,
        reason=", ".join(result.tags),
    )

    # 8. 更新後のプランを返却
    updated = await plan_repo.get_daily_plan_by_user(supabase, body.plan_id, user_id)

    return AdaptationResponse(
        tags_applied=result.tags,
        changes_summary=changes,
        extraction_status=result.status,
        new_plan=updated,
    )


@router.get("/{plan_id}", response_model=dict)
async def get_feedback_tags(
    plan_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> dict:
    # 所有権確認
    plan = await plan_repo.get_daily_plan_by_user(supabase, plan_id, user_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    tags: list[FeedbackTagResponse] = await feedback_repo.get_feedback_tags_by_plan(supabase, user_id, plan_id)
    return {"tags": tags}
