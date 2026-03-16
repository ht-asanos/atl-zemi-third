"""週次プラン生成 — 7日分の食事 + トレーニングをまとめて生成する。

DB 保存責務は持たない（ルーター側で RPC 経由で一括保存）。
"""

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from math import ceil
from uuid import UUID

from app.models.food import FoodItem, MealSuggestion, MealType, NutritionStatus
from app.models.nutrition import PFCBudget
from app.models.training import MuscleGroup, TrainingDay
from app.repositories import recipe_repo
from app.services.meal_suggestion import (
    _make_breakfast,
    _make_lunch,
    calc_dinner_budget,
    generate_daily_meals,
    generate_daily_meals_v2,
    generate_structured_daily_meals,
)
from app.services.plan_validator import ValidationResult, validate_weekly_plan
from app.services.training_template import get_template

from supabase import AsyncClient

logger = logging.getLogger(__name__)


@dataclass
class DailyPlanData:
    plan_date: date
    meals: list[MealSuggestion]
    training_day: TrainingDay | None


@dataclass
class WeeklyPlanResult:
    plans: list[DailyPlanData] = field(default_factory=list)


def _apply_training_adjustments(
    training_day: TrainingDay,
    scale: float,
    protect_forearms: bool,
) -> TrainingDay:
    exercises = []
    for ex in training_day.exercises:
        ex_copy = ex.model_copy(deep=True)
        if protect_forearms and ex_copy.muscle_group.value == "forearms":
            ex_copy.id = "scapular_pull_up"
            ex_copy.name_ja = "スキャプラプルアップ"
            ex_copy.muscle_group = MuscleGroup.BACK
            ex_copy.sets = 3
            ex_copy.reps = 10
            ex_copy.rest_seconds = 75

        if isinstance(ex_copy.reps, int):
            ex_copy.reps = max(1, ceil(ex_copy.reps * scale))
        ex_copy.sets = max(1, ceil(ex_copy.sets * scale))
        exercises.append(ex_copy)
    return TrainingDay(day_label=training_day.day_label, exercises=exercises)


def generate_weekly_plan(
    start_date: date,
    pfc_budget: PFCBudget,
    staple: FoodItem,
    goal_type: str,
    protein_foods: list[FoodItem] | None = None,
    bulk_foods: list[FoodItem] | None = None,
    training_scale: float = 1.0,
    protect_forearms: bool = False,
) -> list[DailyPlanData]:
    """7日分のプランを生成する。

    トレーニング日はテンプレートの日数でサイクルする。
    """
    template = get_template(goal_type)
    training_days = template.days
    bouldering_schedule = [0, None, 1, None, 2, None, 3] if goal_type == "bouldering" else None
    result: list[DailyPlanData] = []

    for day_offset in range(7):
        current_date = start_date + timedelta(days=day_offset)
        if bouldering_schedule is not None:
            idx = bouldering_schedule[day_offset]
            if idx is None:
                training_day = None
            else:
                training_day = _apply_training_adjustments(training_days[idx], training_scale, protect_forearms)
        else:
            training_day = training_days[day_offset % len(training_days)]
        meals = generate_daily_meals(
            pfc_budget,
            staple,
            protein_foods=protein_foods,
            bulk_foods=bulk_foods,
        )
        result.append(
            DailyPlanData(
                plan_date=current_date,
                meals=meals,
                training_day=training_day,
            )
        )

    return result


async def generate_weekly_plan_v2(
    start_date: date,
    pfc_budget: PFCBudget,
    staple: FoodItem,
    goal_type: str,
    supabase: AsyncClient | None = None,
    protein_foods: list[FoodItem] | None = None,
    bulk_foods: list[FoodItem] | None = None,
    training_scale: float = 1.0,
    protect_forearms: bool = False,
) -> list[DailyPlanData]:
    """7日分のプランを生成する（レシピ提案対応版）。"""
    template = get_template(goal_type)
    training_days = template.days
    bouldering_schedule = [0, None, 1, None, 2, None, 3] if goal_type == "bouldering" else None
    result: list[DailyPlanData] = []

    for day_offset in range(7):
        current_date = start_date + timedelta(days=day_offset)
        if bouldering_schedule is not None:
            idx = bouldering_schedule[day_offset]
            if idx is None:
                training_day = None
            else:
                training_day = _apply_training_adjustments(training_days[idx], training_scale, protect_forearms)
        else:
            training_day = training_days[day_offset % len(training_days)]
        meals = await generate_daily_meals_v2(
            pfc_budget,
            staple,
            supabase=supabase,
            protein_foods=protein_foods,
            bulk_foods=bulk_foods,
        )
        result.append(
            DailyPlanData(
                plan_date=current_date,
                meals=meals,
                training_day=training_day,
            )
        )

    return result


async def generate_weekly_plan_v3(
    start_date: date,
    pfc_budget: PFCBudget,
    goal_type: str,
    supabase: AsyncClient,
    favorite_ids: set | None = None,
    staple_tags: list[str] | None = None,
    staple_keywords: list[str] | None = None,
    training_scale: float = 1.0,
    protect_forearms: bool = False,
    exclude_recipe_ids: list[UUID] | None = None,
) -> tuple[list[DailyPlanData], dict]:
    """朝食固定 + 昼食固定 + 夕食レシピ（7日重複なし、PFC フィルタ付き）。

    Returns:
        tuple of (plans, selection_metrics)
    """
    template = get_template(goal_type)
    training_days = template.days
    bouldering_schedule = [0, None, 1, None, 2, None, 3] if goal_type == "bouldering" else None

    # 朝食・昼食の栄養を差し引いて夕食予算を算出
    sample_breakfast = _make_breakfast()
    sample_lunch = _make_lunch()
    dinner_budget = calc_dinner_budget(pfc_budget, sample_breakfast, sample_lunch)

    # PFC フィルタ付きで 7 件のユニークレシピを取得
    dinner_result = await recipe_repo.get_recipes_for_dinner(
        supabase,
        dinner_budget,
        count=7,
        exclude_ids=exclude_recipe_ids,
        favorite_ids=favorite_ids,
        staple_tags=staple_tags,
        staple_keywords=staple_keywords,
    )
    dinner_recipes = dinner_result.recipes

    selection_metrics = {
        "staple_match_count": dinner_result.staple_match_count,
        "staple_fallback_used": dinner_result.staple_fallback_used,
        "dinner_total_count": dinner_result.total_count,
    }

    result: list[DailyPlanData] = []
    for day_offset in range(7):
        recipe = dinner_recipes[day_offset] if day_offset < len(dinner_recipes) else None
        meals = generate_structured_daily_meals(recipe=recipe)
        if bouldering_schedule is not None:
            idx = bouldering_schedule[day_offset]
            if idx is None:
                training_day = None
            else:
                training_day = _apply_training_adjustments(training_days[idx], training_scale, protect_forearms)
        else:
            training_day = training_days[day_offset % len(training_days)]
        result.append(
            DailyPlanData(
                plan_date=start_date + timedelta(days=day_offset),
                meals=meals,
                training_day=training_day,
            )
        )
    return result, selection_metrics


MAX_RETRIES = 3


async def generate_weekly_plan_v3_validated(
    start_date: date,
    pfc_budget: PFCBudget,
    goal_type: str,
    supabase: AsyncClient,
    favorite_ids: set | None = None,
    staple_tags: list[str] | None = None,
    staple_keywords: list[str] | None = None,
    training_scale: float = 1.0,
    protect_forearms: bool = False,
    exclude_recipe_ids: list[UUID] | None = None,
) -> tuple[list[DailyPlanData], ValidationResult]:
    """品質ゲート付き生成。NG時は問題レシピを除外してリトライする。"""
    all_exclude = list(exclude_recipe_ids or [])
    plans: list[DailyPlanData] = []
    validation = ValidationResult()

    for attempt in range(MAX_RETRIES):
        plans, selection_metrics = await generate_weekly_plan_v3(
            start_date=start_date,
            pfc_budget=pfc_budget,
            goal_type=goal_type,
            supabase=supabase,
            favorite_ids=favorite_ids,
            staple_tags=staple_tags,
            staple_keywords=staple_keywords,
            training_scale=training_scale,
            protect_forearms=protect_forearms,
            exclude_recipe_ids=all_exclude if all_exclude else None,
        )
        validation = validate_weekly_plan(plans)
        validation.metrics.update(selection_metrics)

        if validation.is_valid or attempt == MAX_RETRIES - 1:
            if not validation.is_valid:
                logger.warning("Plan validation failed after %d retries: %s", MAX_RETRIES, validation.issues)
            return plans, validation

        # 問題レシピを exclude に追加してリトライ
        for dp in plans:
            for meal in dp.meals:
                if meal.meal_type != MealType.DINNER:
                    continue
                if meal.nutrition_status == NutritionStatus.FAILED and meal.recipe and isinstance(meal.recipe, dict):
                    rid = meal.recipe.get("id")
                    if rid:
                        try:
                            all_exclude.append(UUID(rid))
                        except (ValueError, AttributeError):
                            pass

        logger.info("Plan validation retry %d/%d, excluding %d recipes", attempt + 1, MAX_RETRIES, len(all_exclude))

    return plans, validation
