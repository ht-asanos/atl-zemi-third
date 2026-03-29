import logging
from copy import deepcopy
from uuid import UUID

from app.dependencies.auth import get_current_user_id
from app.dependencies.supabase_client import get_authenticated_supabase
from app.exceptions import AppException, ErrorCode
from app.repositories import feedback_event_repo, feedback_repo, food_repo, plan_repo, rating_repo
from app.schemas.feedback import (
    AdaptationResponse,
    CreateFeedbackRequest,
    FeedbackEventDetailResponse,
    FeedbackTagResponse,
)
from app.services import adaptation_engine, tag_extractor
from fastapi import APIRouter, Depends, status

from supabase import AsyncClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])

MEAL_TAGS = {"bored_staple", "too_much_food"}
WORKOUT_TAGS = {"too_hard", "cannot_complete_reps", "forearm_sore"}


def _infer_feedback_domain(body: CreateFeedbackRequest, tags: list[str]) -> str:
    if body.domain is not None:
        return body.domain
    if body.meal_type is not None:
        return "meal"
    if body.exercise_id is not None:
        return "workout"
    return "mixed"


def _resolve_feedback_fields(body: CreateFeedbackRequest, tags: list[str]) -> tuple[str, str | None, str | None]:
    """旧クライアント互換で feedback event 用の構造化項目を解決する。"""
    domain = _infer_feedback_domain(body, tags)
    if domain == "meal":
        return domain, body.meal_type, None
    if domain == "workout":
        return domain, None, body.exercise_id
    return "mixed", None, None


def _split_changes_by_domain(changes: list[str]) -> tuple[list[str], list[str]]:
    meal_changes: list[str] = []
    workout_changes: list[str] = []
    for change in changes:
        if change.startswith("主食:") or change.startswith("かさ増し食材") or change.startswith("タンパク源"):
            meal_changes.append(change)
        else:
            workout_changes.append(change)
    return meal_changes, workout_changes


def _build_adaptation_events(
    *,
    before_plan: dict,
    after_plan: dict,
    changes: list[str],
) -> list[dict]:
    meal_changes, workout_changes = _split_changes_by_domain(changes)
    events: list[dict] = []
    if before_plan.get("meal_plan") != after_plan.get("meal_plan"):
        events.append(
            {
                "domain": "meal",
                "target_type": "meal_plan",
                "target_ref": None,
                "before_snapshot": deepcopy(before_plan.get("meal_plan", [])),
                "after_snapshot": deepcopy(after_plan.get("meal_plan", [])),
                "change_summary_json": meal_changes or changes,
            }
        )
    if before_plan.get("workout_plan") != after_plan.get("workout_plan"):
        events.append(
            {
                "domain": "workout",
                "target_type": "workout_plan",
                "target_ref": None,
                "before_snapshot": deepcopy(before_plan.get("workout_plan", {})),
                "after_snapshot": deepcopy(after_plan.get("workout_plan", {})),
                "change_summary_json": workout_changes or changes,
            }
        )
    return events


def _extract_target_recipe_id(plan_row: dict, meal_type: str | None) -> UUID | None:
    meal_plan = plan_row.get("meal_plan", [])
    if not isinstance(meal_plan, list):
        return None

    # まず指定 meal_type に一致する recipe を優先
    if meal_type is not None:
        for meal in meal_plan:
            if not isinstance(meal, dict) or meal.get("meal_type") != meal_type:
                continue
            recipe = meal.get("recipe")
            if isinstance(recipe, dict) and recipe.get("id"):
                try:
                    return UUID(str(recipe["id"]))
                except (TypeError, ValueError):
                    return None

    # recipe モードでは dinner にだけ recipe が入る想定だが、互換性のため最初の recipe へフォールバック
    for meal in meal_plan:
        if not isinstance(meal, dict):
            continue
        recipe = meal.get("recipe")
        if isinstance(recipe, dict) and recipe.get("id"):
            try:
                return UUID(str(recipe["id"]))
            except (TypeError, ValueError):
                return None
    return None


def _derive_meal_recipe_rating(body: CreateFeedbackRequest, tags: list[str]) -> int | None:
    tag_set = set(tags)
    if "too_much_food" in tag_set or "bored_staple" in tag_set:
        return -1
    if body.satisfaction is not None and body.satisfaction <= 2:
        return -1
    if body.satisfaction is not None and body.satisfaction >= 4:
        return 1
    return None


async def _build_recipe_selection_event(
    *,
    supabase: AsyncClient,
    user_id: UUID,
    plan_row: dict,
    body: CreateFeedbackRequest,
    tags: list[str],
) -> tuple[dict | None, str | None]:
    if _infer_feedback_domain(body, tags) != "meal" or body.meal_type != "dinner":
        return None, None

    recipe_id = _extract_target_recipe_id(plan_row, body.meal_type)
    if recipe_id is None:
        return None, None

    next_rating = _derive_meal_recipe_rating(body, tags)
    if next_rating is None:
        return None, None

    previous_rating = await rating_repo.get_recipe_rating(supabase, user_id, recipe_id)
    if previous_rating == next_rating:
        return None, None

    await rating_repo.upsert_rating(supabase, user_id, recipe_id, next_rating)
    summary = f"recipe_rating: {previous_rating or 0}→{next_rating}"
    user_message = "夕食レシピを次回候補で優先します" if next_rating > 0 else "夕食レシピを次回候補で下げます"
    return (
        {
            "domain": "meal",
            "target_type": "recipe_selection",
            "target_ref": str(recipe_id),
            "before_snapshot": {"recipe_id": str(recipe_id), "rating": previous_rating},
            "after_snapshot": {"recipe_id": str(recipe_id), "rating": next_rating},
            "change_summary_json": [summary],
        },
        user_message,
    )


@router.post("", response_model=AdaptationResponse)
async def create_feedback(
    body: CreateFeedbackRequest,
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> AdaptationResponse:
    # 1. 所有権チェック付きでプラン取得 (raw row for updated_at)
    plan_row = await plan_repo.get_daily_plan_row_by_user(supabase, body.plan_id, user_id)
    if plan_row is None:
        raise AppException(ErrorCode.PLAN_NOT_FOUND, status.HTTP_404_NOT_FOUND, "Plan not found")

    # 2. タグ抽出
    result = await tag_extractor.extract_tags(body.source_text)
    event_domain, event_meal_type, event_exercise_id = _resolve_feedback_fields(body, result.tags)

    # 3. 親イベント保存
    feedback_event_id = await feedback_event_repo.create_feedback_event(
        supabase,
        user_id=user_id,
        plan_id=body.plan_id,
        domain=event_domain,
        source_text=body.source_text,
        meal_type=event_meal_type,
        exercise_id=event_exercise_id,
        satisfaction=body.satisfaction,
        rpe=body.rpe,
        completed=body.completed,
    )

    # 4. タグ保存 (extraction_status に関わらずテキストは保存)
    await feedback_event_repo.create_feedback_event_tags(
        supabase,
        event_id=feedback_event_id,
        tags=result.tags,
        tag_source="llm",
    )
    await feedback_repo.create_feedback_tags(supabase, user_id, body.plan_id, result.tags, body.source_text)

    rating_event, rating_change_message = await _build_recipe_selection_event(
        supabase=supabase,
        user_id=user_id,
        plan_row=plan_row,
        body=body,
        tags=result.tags,
    )

    # 5. タグ 0 件 → early return
    if not result.tags:
        adaptation_event_ids: list[UUID] = []
        if rating_event is not None:
            adaptation_event_ids = await feedback_event_repo.create_adaptation_events(
                supabase,
                feedback_event_id=feedback_event_id,
                plan_revision_id=None,
                events=[rating_event],
            )
        return AdaptationResponse(
            feedback_event_id=feedback_event_id,
            adaptation_event_ids=adaptation_event_ids,
            tags_applied=[],
            changes_summary=[rating_change_message] if rating_change_message else [],
            extraction_status=result.status,
            new_plan=None,
        )

    # 6. 適応実行
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
    adaptation_events = _build_adaptation_events(
        before_plan=current_plan,
        after_plan=new_plan,
        changes=changes,
    )
    if rating_event is not None:
        adaptation_events.append(rating_event)

    # 7. 楽観ロック付きプラン更新
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
            raise AppException(
                ErrorCode.CONFLICT, status.HTTP_409_CONFLICT, "Conflict: plan was modified by another operation"
            ) from e
        raise

    # 8. リビジョン保存
    plan_revision_id = await feedback_repo.create_plan_revision(
        supabase,
        body.plan_id,
        user_id,
        previous_plan=current_plan,
        new_plan=new_plan,
        reason=", ".join(result.tags),
    )
    adaptation_event_ids = await feedback_event_repo.create_adaptation_events(
        supabase,
        feedback_event_id=feedback_event_id,
        plan_revision_id=plan_revision_id,
        events=adaptation_events,
    )

    # 9. 更新後のプランを返却
    updated = await plan_repo.get_daily_plan_by_user(supabase, body.plan_id, user_id)

    return AdaptationResponse(
        feedback_event_id=feedback_event_id,
        adaptation_event_ids=adaptation_event_ids,
        tags_applied=result.tags,
        changes_summary=changes + ([rating_change_message] if rating_change_message else []),
        extraction_status=result.status,
        new_plan=updated,
    )


@router.get("/history", response_model=list[FeedbackEventDetailResponse])
async def get_feedback_history(
    limit: int = 20,
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> list[FeedbackEventDetailResponse]:
    return await feedback_event_repo.get_feedback_history(supabase, user_id=user_id, limit=limit)


@router.get("/history/{event_id}", response_model=FeedbackEventDetailResponse)
async def get_feedback_history_detail(
    event_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> FeedbackEventDetailResponse:
    detail = await feedback_event_repo.get_feedback_event_detail(supabase, user_id=user_id, event_id=event_id)
    if detail is None:
        raise AppException(ErrorCode.FEEDBACK_NOT_FOUND, status.HTTP_404_NOT_FOUND, "Feedback event not found")
    return detail


@router.get("/{plan_id}", response_model=dict)
async def get_feedback_tags(
    plan_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> dict:
    # 所有権確認
    plan = await plan_repo.get_daily_plan_by_user(supabase, plan_id, user_id)
    if plan is None:
        raise AppException(ErrorCode.PLAN_NOT_FOUND, status.HTTP_404_NOT_FOUND, "Plan not found")

    tags: list[FeedbackTagResponse] = await feedback_repo.get_feedback_tags_by_plan(supabase, user_id, plan_id)
    return {"tags": tags}
