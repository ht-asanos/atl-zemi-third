from __future__ import annotations

import re

from app.models.training import Exercise, MuscleGroup
from app.services.training_template import get_bouldering_template, get_diet_template, get_strength_template

TRAINING_EQUIPMENT_OPTIONS = ("none", "pull_up_bar", "dip_bars", "dumbbells")

DEFAULT_ALIASES: dict[str, str] = {
    "懸垂": "pull_up",
    "チンニング": "pull_up",
    "プルアップ": "pull_up",
    "チンアップ": "chin_up",
    "腕立て伏せ": "push_up",
    "プッシュアップ": "push_up",
    "ディップス": "tricep_dip",
    "ディップ": "tricep_dip",
    "自重ロウ": "bodyweight_row",
    "ロウ": "bodyweight_row",
    "スキャプラプルアップ": "scapular_pull_up",
    "デッドハング": "dead_hang",
    "ハング": "dead_hang",
    "ハンギングニーレイズ": "hanging_knee_raise",
    "ハンギングレッグレイズ": "hanging_leg_raise",
    "レッグレイズ": "hanging_leg_raise",
    "プランク": "plank",
    "サイドプランク": "side_plank",
    "ゴブレットスクワット": "goblet_squat",
    "リバーススキャピュラープッシュアップ": "reverse_scapular_push_up",
    "リバースプランクレイズ": "reverse_plank_raise",
    "ハーフブリッジリーチ": "half_bridge_reach",
    "ウォールブリッジローテーション": "wall_bridge_rotation",
    "ブリッジ": "bridge",
    "ディップスバーの上でスイング": "dip_bar_swing",
    "スイングタックプラン": "swing_tuck_planche",
    "Lシットタックプラン": "l_sit_tuck_planche",
    "タックプランプッシュアップtoLシット": "tuck_planche_pushup_to_l_sit",
    "白プランプッシュアップ": "planche_pushup",
}

EXERCISE_REQUIRED_EQUIPMENT: dict[str, list[str]] = {
    "pull_up": ["pull_up_bar"],
    "chin_up": ["pull_up_bar"],
    "scapular_pull_up": ["pull_up_bar"],
    "dead_hang": ["pull_up_bar"],
    "hanging_knee_raise": ["pull_up_bar"],
    "hanging_leg_raise": ["pull_up_bar"],
    "tricep_dip": ["dip_bars"],
    "parallel_bar_dip": ["dip_bars"],
    "dip_bar_swing": ["dip_bars"],
    "swing_tuck_planche": ["dip_bars"],
    "l_sit_tuck_planche": ["dip_bars"],
    "tuck_planche_pushup_to_l_sit": ["dip_bars"],
    "dumbbell_press": ["dumbbells"],
    "dumbbell_row": ["dumbbells"],
    "goblet_squat": ["dumbbells"],
    "farmer_carry": ["dumbbells"],
}

EQUIPMENT_FALLBACKS: dict[str, list[str]] = {
    "pull_up": ["bodyweight_row"],
    "chin_up": ["bodyweight_row"],
    "scapular_pull_up": ["bodyweight_row"],
    "dead_hang": ["hollow_body_hold", "plank"],
    "hanging_knee_raise": ["dead_bug", "plank"],
    "hanging_leg_raise": ["dead_bug", "hollow_body_hold"],
    "tricep_dip": ["push_up"],
    "parallel_bar_dip": ["push_up"],
    "dip_bar_swing": ["push_up"],
    "swing_tuck_planche": ["push_up"],
    "l_sit_tuck_planche": ["hollow_body_hold", "plank"],
    "tuck_planche_pushup_to_l_sit": ["push_up"],
    "dumbbell_press": ["push_up"],
    "dumbbell_row": ["bodyweight_row"],
    "goblet_squat": ["lunge"],
    "farmer_carry": ["side_plank", "plank"],
}

EXTRA_EXERCISES: dict[str, Exercise] = {
    "chin_up": Exercise(
        id="chin_up",
        name_ja="チンアップ",
        muscle_group=MuscleGroup.BACK,
        sets=3,
        reps=5,
        rest_seconds=90,
        required_equipment=["pull_up_bar"],
    ),
    "parallel_bar_dip": Exercise(
        id="parallel_bar_dip",
        name_ja="パラレルバーディップ",
        muscle_group=MuscleGroup.ARMS,
        sets=3,
        reps=5,
        rest_seconds=90,
        required_equipment=["dip_bars"],
    ),
    "reverse_scapular_push_up": Exercise(
        id="reverse_scapular_push_up",
        name_ja="リバーススキャピュラープッシュアップ",
        muscle_group=MuscleGroup.SHOULDERS,
        sets=3,
        reps=10,
        rest_seconds=60,
    ),
    "reverse_plank_raise": Exercise(
        id="reverse_plank_raise",
        name_ja="リバースプランクレイズ",
        muscle_group=MuscleGroup.CORE,
        sets=3,
        reps=5,
        rest_seconds=60,
    ),
    "half_bridge_reach": Exercise(
        id="half_bridge_reach",
        name_ja="ハーフブリッジリーチ",
        muscle_group=MuscleGroup.CORE,
        sets=3,
        reps=3,
        rest_seconds=60,
    ),
    "wall_bridge_rotation": Exercise(
        id="wall_bridge_rotation",
        name_ja="ウォールブリッジローテーション",
        muscle_group=MuscleGroup.CORE,
        sets=3,
        reps=2,
        rest_seconds=60,
    ),
    "bridge": Exercise(
        id="bridge",
        name_ja="ブリッジ",
        muscle_group=MuscleGroup.FULL_BODY,
        sets=3,
        reps=1,
        rest_seconds=75,
    ),
    "dip_bar_swing": Exercise(
        id="dip_bar_swing",
        name_ja="ディップスバーの上でスイング",
        muscle_group=MuscleGroup.CORE,
        sets=3,
        reps=5,
        rest_seconds=75,
        required_equipment=["dip_bars"],
    ),
    "swing_tuck_planche": Exercise(
        id="swing_tuck_planche",
        name_ja="スイングタックプラン",
        muscle_group=MuscleGroup.SHOULDERS,
        sets=3,
        reps=5,
        rest_seconds=75,
        required_equipment=["dip_bars"],
    ),
    "l_sit_tuck_planche": Exercise(
        id="l_sit_tuck_planche",
        name_ja="Lシットタックプラン",
        muscle_group=MuscleGroup.CORE,
        sets=3,
        reps=5,
        rest_seconds=75,
        required_equipment=["dip_bars"],
    ),
    "tuck_planche_pushup_to_l_sit": Exercise(
        id="tuck_planche_pushup_to_l_sit",
        name_ja="タックプランプッシュアップtoLシット",
        muscle_group=MuscleGroup.SHOULDERS,
        sets=3,
        reps=3,
        rest_seconds=90,
        required_equipment=["dip_bars"],
    ),
    "planche_pushup": Exercise(
        id="planche_pushup",
        name_ja="プランシェプッシュアップ",
        muscle_group=MuscleGroup.SHOULDERS,
        sets=3,
        reps=3,
        rest_seconds=90,
    ),
}


def normalize_alias(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip().lower())


def get_exercise_catalog() -> dict[str, Exercise]:
    catalog: dict[str, Exercise] = {}
    for template in (get_diet_template(), get_bouldering_template(), get_strength_template()):
        for day in template.days:
            for ex in day.exercises:
                ex_copy = ex.model_copy(deep=True)
                ex_copy.required_equipment = EXERCISE_REQUIRED_EQUIPMENT.get(ex.id, ex_copy.required_equipment)
                catalog[ex.id] = ex_copy
    for ex_id, exercise in EXTRA_EXERCISES.items():
        catalog[ex_id] = exercise.model_copy(deep=True)
    return catalog


def get_exercise_definition(exercise_id: str) -> Exercise | None:
    exercise = get_exercise_catalog().get(exercise_id)
    return exercise.model_copy(deep=True) if exercise else None


def normalize_available_equipment(available_equipment: list[str] | set[str] | None) -> set[str]:
    if not available_equipment:
        return {"none"}
    return {item for item in available_equipment if item in TRAINING_EQUIPMENT_OPTIONS} or {"none"}


def is_exercise_available(exercise: Exercise, available_equipment: list[str] | set[str] | None) -> bool:
    equipment = normalize_available_equipment(available_equipment)
    required = set(exercise.required_equipment or ["none"])
    return required == {"none"} or required.issubset(equipment)


def resolve_available_exercise(exercise_id: str, available_equipment: list[str] | set[str] | None) -> Exercise | None:
    equipment = normalize_available_equipment(available_equipment)
    visited: set[str] = set()
    queue = [exercise_id]

    while queue:
        current_id = queue.pop(0)
        if current_id in visited:
            continue
        visited.add(current_id)

        exercise = get_exercise_definition(current_id)
        if exercise and is_exercise_available(exercise, equipment):
            return exercise

        queue.extend(EQUIPMENT_FALLBACKS.get(current_id, []))

    return None
