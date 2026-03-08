"""ルールベース適応エンジン — タグに基づいてプランを修正する。

純粋な決定論ロジック（AI 非依存、完全テスト可能）。
"""

import copy
import math

from app.models.food import FoodItem

SUBSTITUTIONS: dict[str, str] = {
    "pull_up": "bodyweight_row",
    "barbell_squat": "goblet_squat",
    "bench_press": "push_up",
    "overhead_press": "dumbbell_press",
    "barbell_row": "dumbbell_row",
    "dead_hang": "finger_curl",
    "tricep_dip": "push_up",
}

FALLBACK_EXERCISE: dict = {
    "id": "plank",
    "name_ja": "プランク",
    "muscle_group": "core",
    "sets": 3,
    "reps": "30秒",
    "rest_seconds": 60,
}


def adapt_plan(
    current_plan: dict,
    tags: list[str],
    available_staples: list[FoodItem],
    current_staple_name: str,
) -> tuple[dict, list[str]]:
    """(new_plan, changes_summary) を返す。"""
    plan = copy.deepcopy(current_plan)
    changes: list[str] = []

    if not tags:
        return plan, changes

    workout = plan.get("workout_plan", {})
    exercises = workout.get("exercises", []) if isinstance(workout, dict) else []
    meal_plan = plan.get("meal_plan", [])

    if "too_hard" in tags:
        _apply_too_hard(exercises, changes)

    if "cannot_complete_reps" in tags:
        _apply_cannot_complete_reps(exercises, changes)

    if "forearm_sore" in tags:
        exercises = _apply_forearm_sore(exercises, changes)

    if "bored_staple" in tags:
        meal_plan = _apply_bored_staple(meal_plan, available_staples, current_staple_name, changes)

    if "too_much_food" in tags:
        _apply_too_much_food(meal_plan, changes)

    if isinstance(workout, dict) and workout:
        workout["exercises"] = exercises
        plan["workout_plan"] = workout
    plan["meal_plan"] = meal_plan

    return plan, changes


def _apply_too_hard(exercises: list[dict], changes: list[str]) -> None:
    for ex in exercises:
        reps = ex.get("reps")
        if not isinstance(reps, int):
            continue
        old_sets: int = ex.get("sets", 1)
        old_reps = reps
        new_sets = max(1, old_sets - 1)
        new_reps = max(1, math.floor(old_reps * 0.8))
        if new_sets != old_sets or new_reps != old_reps:
            ex["sets"] = new_sets
            ex["reps"] = new_reps
            changes.append(f"{ex['id']}: sets {old_sets}→{new_sets}, reps {old_reps}→{new_reps}")


def _apply_cannot_complete_reps(exercises: list[dict], changes: list[str]) -> None:
    new_exercises = []
    for ex in exercises:
        reps = ex.get("reps")
        if not isinstance(reps, int):
            new_exercises.append(ex)
            continue
        new_reps = max(1, reps - 2)
        if new_reps < reps:
            ex["reps"] = new_reps
            changes.append(f"{ex['id']}: reps {reps}→{new_reps}")
        elif reps <= 1 and ex["id"] in SUBSTITUTIONS:
            sub_id = SUBSTITUTIONS[ex["id"]]
            changes.append(f"{ex['id']}→{sub_id} に代替")
            ex["id"] = sub_id
        new_exercises.append(ex)
    exercises.clear()
    exercises.extend(new_exercises)


def _apply_forearm_sore(exercises: list[dict], changes: list[str]) -> list[dict]:
    removed = [ex for ex in exercises if ex.get("muscle_group") == "forearms"]
    remaining = [ex for ex in exercises if ex.get("muscle_group") != "forearms"]
    for ex in removed:
        changes.append(f"{ex['id']}(forearms) を除外")
    if not remaining and removed:
        remaining = [copy.deepcopy(FALLBACK_EXERCISE)]
        changes.append("exercises が空のため plank で補完")
    return remaining


def _apply_bored_staple(
    meal_plan: list[dict],
    available_staples: list[FoodItem],
    current_staple_name: str,
    changes: list[str],
) -> list[dict]:
    candidates = [s for s in available_staples if s.name != current_staple_name]
    if not candidates or not meal_plan:
        return meal_plan

    current_staple = next((s for s in available_staples if s.name == current_staple_name), None)
    target_kcal = current_staple.kcal_per_serving if current_staple else 0

    best = min(candidates, key=lambda s: abs(s.kcal_per_serving - target_kcal))

    new_staple_dict = {
        "name": best.name,
        "category": best.category.value,
        "kcal_per_serving": best.kcal_per_serving,
        "protein_g": best.protein_g,
        "fat_g": best.fat_g,
        "carbs_g": best.carbs_g,
        "serving_unit": best.serving_unit,
        "price_yen": best.price_yen,
        "cooking_minutes": best.cooking_minutes,
    }

    for meal in meal_plan:
        if isinstance(meal, dict) and "staple" in meal:
            meal["staple"] = new_staple_dict

    changes.append(f"主食: {current_staple_name}→{best.name}")
    return meal_plan


def _apply_too_much_food(meal_plan: list[dict], changes: list[str]) -> None:
    for meal in meal_plan:
        if not isinstance(meal, dict):
            continue
        bulk_items = meal.get("bulk_items", [])
        if bulk_items:
            removed = bulk_items.pop()
            changes.append(f"かさ増し食材 {removed.get('name', '?')} を1品除去")
        else:
            protein_sources = meal.get("protein_sources", [])
            if protein_sources:
                removed = protein_sources.pop()
                changes.append(f"タンパク源 {removed.get('name', '?')} を1品除去")
