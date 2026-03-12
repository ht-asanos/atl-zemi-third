from dataclasses import dataclass
from datetime import date, timedelta
from statistics import fmean
from uuid import UUID

from app.repositories import feedback_repo, log_repo, plan_repo
from app.schemas.log import WorkoutLogResponse

from supabase import AsyncClient


@dataclass
class TrainingAdjustment:
    scale: float = 1.0
    protect_forearms: bool = False


def _derive_scale(avg_rpe: float | None, completion_rate: float | None) -> float:
    if completion_rate is None and avg_rpe is None:
        return 1.0
    if (completion_rate is not None and completion_rate < 0.4) or (avg_rpe is not None and avg_rpe >= 9.0):
        return 0.9
    if (completion_rate is not None and completion_rate < 0.6) or (avg_rpe is not None and avg_rpe >= 8.5):
        return 0.95
    if (completion_rate is not None and completion_rate >= 0.85) and (avg_rpe is None or avg_rpe <= 7.0):
        return 1.05
    return 1.0


def _completion_rate(logs: list[WorkoutLogResponse]) -> float | None:
    if not logs:
        return None
    completed = sum(1 for log in logs if log.completed)
    return completed / len(logs)


def _average_rpe(logs: list[WorkoutLogResponse]) -> float | None:
    rpes = [log.rpe for log in logs if log.rpe is not None]
    if not rpes:
        return None
    return float(fmean(rpes))


def _extract_forearm_exercise_ids(plans: list) -> set[str]:
    ids: set[str] = set()
    for plan in plans:
        workout_plan = plan.workout_plan
        if not isinstance(workout_plan, dict):
            continue
        exercises = workout_plan.get("exercises", [])
        if not isinstance(exercises, list):
            continue
        for ex in exercises:
            if isinstance(ex, dict) and ex.get("muscle_group") == "forearms" and ex.get("id"):
                ids.add(str(ex["id"]))
    return ids


def _forearm_completion_rate(logs: list[WorkoutLogResponse], forearm_ids: set[str]) -> float | None:
    if not forearm_ids:
        return None
    target = [log for log in logs if log.exercise_id in forearm_ids]
    if not target:
        return None
    completed = sum(1 for log in target if log.completed)
    return completed / len(target)


async def build_next_week_training_adjustment(
    supabase: AsyncClient,
    user_id: UUID,
    start_date: date,
    goal_type: str,
) -> TrainingAdjustment:
    """次週生成向けのトレーニング調整係数を返す（bouldering のみ有効）。"""
    if goal_type != "bouldering":
        return TrainingAdjustment()

    prev_start = start_date - timedelta(days=7)
    prev_end = start_date - timedelta(days=1)
    prev_plans = await plan_repo.get_weekly_plans(supabase, user_id, prev_start)
    if not prev_plans:
        return TrainingAdjustment()

    logs = await log_repo.get_workout_logs_in_range(supabase, user_id, prev_start, prev_end)

    avg_rpe = _average_rpe(logs)
    completion_rate = _completion_rate(logs)
    scale = _derive_scale(avg_rpe, completion_rate)

    forearm_ids = _extract_forearm_exercise_ids(prev_plans)
    forearm_rate = _forearm_completion_rate(logs, forearm_ids)

    has_forearm_sore_tag = False
    for plan in prev_plans:
        tags = await feedback_repo.get_feedback_tags_by_plan(supabase, user_id, plan.id)
        if any(tag.tag == "forearm_sore" for tag in tags):
            has_forearm_sore_tag = True
            break

    protect_forearms = has_forearm_sore_tag or (forearm_rate is not None and forearm_rate < 0.7)

    return TrainingAdjustment(scale=scale, protect_forearms=protect_forearms)
