from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from app.repositories import feedback_event_repo, log_repo, training_progression_repo
from app.schemas.feedback import FeedbackEventDetailResponse
from app.schemas.log import WorkoutLogResponse
from app.services.training_catalog import get_exercise_definition, is_exercise_available, normalize_available_equipment

from supabase import AsyncClient


@dataclass
class ExerciseRecommendation:
    replacement_id: str
    reason: str


STRENGTH_ADVANCED_SOURCE_IDS = {
    "tricep_dip",
    "push_up",
    "plank",
    "hollow_body_hold",
}

STRENGTH_ADVANCED_SLOT_SOURCES: dict[str, tuple[str, ...]] = {
    "tricep_dip": ("tricep_dip", "push_up"),
    "overhead_press": ("overhead_press", "push_up"),
}

STRENGTH_TRACK_CHAINS: dict[str, tuple[str, ...]] = {
    "tricep_dip": (
        "dip_bar_swing",
        "swing_tuck_planche",
        "l_sit_tuck_planche",
        "tuck_planche_pushup_to_l_sit",
        "planche_pushup",
    ),
    "overhead_press": (
        "reverse_scapular_push_up",
        "reverse_plank_raise",
        "half_bridge_reach",
        "wall_bridge_rotation",
        "bridge",
    ),
}


def _edge_lookup(edges: Iterable) -> dict[tuple[str, str], tuple[int, int]]:
    lookup: dict[tuple[str, str], tuple[int, int]] = {}
    for edge in edges:
        if not edge.from_exercise_id or not edge.to_exercise_id:
            continue
        lookup[(edge.from_exercise_id, edge.to_exercise_id)] = (edge.from_reps, edge.to_reps)
    return lookup


def _best_track_recommendation(
    *,
    slot_id: str,
    chain: tuple[str, ...],
    best_reps: dict[str, int],
    negative_ids: set[str],
    edge_requirements: dict[tuple[str, str], tuple[int, int]],
    equipment: set[str],
) -> ExerciseRecommendation | None:
    seed_sources = STRENGTH_ADVANCED_SLOT_SOURCES[slot_id]
    best_seed = max(best_reps.get(source_id, 0) for source_id in seed_sources)
    first_stage = chain[0]
    first_ex = get_exercise_definition(first_stage)
    if first_ex is None or not is_exercise_available(first_ex, equipment):
        return None

    current_idx = -1
    current_label = slot_id
    current_best = best_seed
    next_target = first_stage
    next_required = 0

    for idx, stage_id in enumerate(chain):
        stage_best = best_reps.get(stage_id, 0)
        if stage_best > 0:
            current_idx = idx
            current_label = stage_id
            current_best = stage_best

    if current_idx == -1:
        if len(chain) < 2:
            return None
        edge_key = (chain[0], chain[1])
        if edge_key not in edge_requirements:
            return None
        next_required = edge_requirements[edge_key][0]
        if best_seed < next_required or first_stage in negative_ids:
            return None
        return ExerciseRecommendation(
            replacement_id=first_stage,
            reason=f"{slot_id} の基礎負荷が十分なため {first_stage} を導入",
        )

    if current_idx >= len(chain) - 1:
        return None

    next_target = chain[current_idx + 1]
    next_ex = get_exercise_definition(next_target)
    if next_ex is None or not is_exercise_available(next_ex, equipment) or next_target in negative_ids:
        return None
    edge_key = (chain[current_idx], next_target)
    if edge_key not in edge_requirements:
        return None
    next_required = edge_requirements[edge_key][0]
    if current_best < next_required:
        return None
    return ExerciseRecommendation(
        replacement_id=next_target,
        reason=f"{current_label} {next_required}回条件を満たしたため {next_target} へ進行",
    )


def _negative_feedback_exercise_ids(events: Iterable[FeedbackEventDetailResponse]) -> set[str]:
    negative: set[str] = set()
    for event in events:
        if not event.exercise_id:
            continue
        tags = {tag.tag for tag in event.tags}
        if "too_hard" in tags or "cannot_complete_reps" in tags:
            negative.add(event.exercise_id)
            continue
        if event.completed is False and event.rpe is not None and event.rpe >= 9.0:
            negative.add(event.exercise_id)
    return negative


def _best_completed_reps(logs: Iterable[WorkoutLogResponse]) -> dict[str, int]:
    best: dict[str, int] = defaultdict(int)
    for log in logs:
        if log.completed:
            best[log.exercise_id] = max(best[log.exercise_id], log.reps)
    return dict(best)


async def recommend_progression_replacements(
    supabase: AsyncClient,
    *,
    user_id: UUID,
    start_date: date,
    goal_type: str,
    available_equipment: list[str] | set[str] | None = None,
) -> dict[str, ExerciseRecommendation]:
    if goal_type not in {"bouldering", "strength"}:
        return {}

    end_date = start_date
    begin_date = start_date - timedelta(days=14)
    logs = await log_repo.get_workout_logs_in_range(supabase, user_id, begin_date, end_date)
    events = await feedback_event_repo.get_feedback_events_in_range(
        supabase,
        user_id=user_id,
        start_date=begin_date,
        end_date=end_date + timedelta(days=1),
        domain="workout",
    )
    approved_edges = await training_progression_repo.list_approved_edges(supabase, goal_type=goal_type)
    if not approved_edges:
        return {}

    best_reps = _best_completed_reps(logs)
    negative_ids = _negative_feedback_exercise_ids(events)
    equipment = normalize_available_equipment(available_equipment)
    recommendations: dict[str, ExerciseRecommendation] = {}
    edge_requirements = _edge_lookup(approved_edges)

    for edge in approved_edges:
        if not edge.from_exercise_id or not edge.to_exercise_id:
            continue
        to_exercise = get_exercise_definition(edge.to_exercise_id)
        if to_exercise is None or not is_exercise_available(to_exercise, equipment):
            continue

        current_best = best_reps.get(edge.from_exercise_id, 0)
        source_best = current_best
        if source_best >= edge.from_reps and edge.to_exercise_id not in negative_ids:
            existing = recommendations.get(edge.from_exercise_id)
            if existing is None:
                recommendations[edge.from_exercise_id] = ExerciseRecommendation(
                    replacement_id=edge.to_exercise_id,
                    reason=f"{edge.from_exercise_id} {edge.from_reps}回達成で {edge.to_exercise_id} {edge.to_reps}回へ",
                )

        from_exercise = get_exercise_definition(edge.from_exercise_id)
        if (
            edge.to_exercise_id in negative_ids
            and from_exercise is not None
            and is_exercise_available(from_exercise, equipment)
        ):
            recommendations[edge.to_exercise_id] = ExerciseRecommendation(
                replacement_id=edge.from_exercise_id,
                reason=f"{edge.to_exercise_id} に負荷過多反応があるため {edge.from_exercise_id} へ戻す",
            )

    if goal_type == "strength":
        for slot_id, chain in STRENGTH_TRACK_CHAINS.items():
            rec = _best_track_recommendation(
                slot_id=slot_id,
                chain=chain,
                best_reps=best_reps,
                negative_ids=negative_ids,
                edge_requirements=edge_requirements,
                equipment=equipment,
            )
            if rec is not None:
                recommendations[slot_id] = rec

    return recommendations
