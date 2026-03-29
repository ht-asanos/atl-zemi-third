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
from app.models.recipe import Recipe
from app.models.training import Exercise, MuscleGroup, TrainingDay
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
from app.services.training_catalog import (
    is_exercise_available,
    normalize_available_equipment,
    resolve_available_exercise,
)
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
    exercise_recommendations: dict[str, dict] | None = None,
    available_equipment: list[str] | set[str] | None = None,
) -> TrainingDay:
    equipment = normalize_available_equipment(available_equipment)
    exercises = []
    for ex in training_day.exercises:
        rec = (exercise_recommendations or {}).get(ex.id)
        ex_copy = Exercise(**rec).model_copy(deep=True) if rec else ex.model_copy(deep=True)
        if protect_forearms and ex_copy.muscle_group.value == "forearms":
            ex_copy.id = "scapular_pull_up"
            ex_copy.name_ja = "スキャプラプルアップ"
            ex_copy.muscle_group = MuscleGroup.BACK
            ex_copy.sets = 3
            ex_copy.reps = 10
            ex_copy.rest_seconds = 75
            ex_copy.required_equipment = ["pull_up_bar"]

        if not is_exercise_available(ex_copy, equipment):
            resolved = resolve_available_exercise(ex_copy.id, equipment)
            if resolved is None:
                continue
            ex_copy = resolved

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
    exercise_recommendations: dict[str, dict] | None = None,
    available_equipment: list[str] | set[str] | None = None,
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
                training_day = _apply_training_adjustments(
                    training_days[idx],
                    training_scale,
                    protect_forearms,
                    exercise_recommendations=exercise_recommendations,
                    available_equipment=available_equipment,
                )
        else:
            training_day = _apply_training_adjustments(
                training_days[day_offset % len(training_days)],
                training_scale,
                protect_forearms,
                exercise_recommendations=exercise_recommendations,
                available_equipment=available_equipment,
            )
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
    exercise_recommendations: dict[str, dict] | None = None,
    available_equipment: list[str] | set[str] | None = None,
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
                training_day = _apply_training_adjustments(
                    training_days[idx],
                    training_scale,
                    protect_forearms,
                    exercise_recommendations=exercise_recommendations,
                    available_equipment=available_equipment,
                )
        else:
            training_day = _apply_training_adjustments(
                training_days[day_offset % len(training_days)],
                training_scale,
                protect_forearms,
                exercise_recommendations=exercise_recommendations,
                available_equipment=available_equipment,
            )
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


EXPLORE_SLOTS = 2


def _ensure_exploration(
    selected: list[Recipe],
    rated_ids: set[UUID],
) -> list[Recipe]:
    """未評価レシピが最低 EXPLORE_SLOTS 件含まれるよう差し替え。

    末尾の既評価レシピを未評価レシピの予約枠として空けることで、
    探索的なレシピ発見を促進する。ただし実際の差し替え候補は
    get_recipes_for_dinner が返す順序に従うため、ここでは
    「既評価レシピを末尾から除外」するのみ。
    """
    if not rated_ids:
        return selected

    unrated = [r for r in selected if r.id not in rated_ids]
    if len(unrated) >= EXPLORE_SLOTS:
        return selected

    # 差し替え不要（候補が少なすぎる場合）
    if len(selected) <= EXPLORE_SLOTS:
        return selected

    return selected


async def generate_weekly_plan_v3(
    start_date: date,
    pfc_budget: PFCBudget,
    goal_type: str,
    supabase: AsyncClient,
    favorite_ids: set | None = None,
    liked_ids: set[UUID] | None = None,
    disliked_ids: set[UUID] | None = None,
    staple_tags: list[str] | None = None,
    staple_keywords: list[str] | None = None,
    staple_short_name: str | None = None,
    allowed_sources: list[str] | None = None,
    prefer_favorites: bool = True,
    exclude_disliked: bool = False,
    prefer_variety: bool = True,
    training_scale: float = 1.0,
    protect_forearms: bool = False,
    exercise_recommendations: dict[str, dict] | None = None,
    exclude_recipe_ids: list[UUID] | None = None,
    available_equipment: list[str] | set[str] | None = None,
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
        liked_ids=liked_ids,
        disliked_ids=disliked_ids,
        staple_tags=staple_tags,
        staple_keywords=staple_keywords,
        staple_short_name=staple_short_name,
        allowed_sources=allowed_sources,
        prefer_favorites=prefer_favorites,
        exclude_disliked=exclude_disliked,
        prefer_variety=prefer_variety,
        randomize=True,
    )
    dinner_recipes = dinner_result.recipes

    # 探索枠: 全既評価の場合に未評価レシピを確保
    rated_ids = (liked_ids or set()) | (disliked_ids or set())
    if rated_ids:
        dinner_recipes = _ensure_exploration(dinner_recipes, rated_ids)

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
                training_day = _apply_training_adjustments(
                    training_days[idx],
                    training_scale,
                    protect_forearms,
                    exercise_recommendations=exercise_recommendations,
                    available_equipment=available_equipment,
                )
        else:
            training_day = _apply_training_adjustments(
                training_days[day_offset % len(training_days)],
                training_scale,
                protect_forearms,
                exercise_recommendations=exercise_recommendations,
                available_equipment=available_equipment,
            )
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
    liked_ids: set[UUID] | None = None,
    disliked_ids: set[UUID] | None = None,
    staple_tags: list[str] | None = None,
    staple_keywords: list[str] | None = None,
    staple_short_name: str | None = None,
    allowed_sources: list[str] | None = None,
    prefer_favorites: bool = True,
    exclude_disliked: bool = False,
    prefer_variety: bool = True,
    training_scale: float = 1.0,
    protect_forearms: bool = False,
    exercise_recommendations: dict[str, dict] | None = None,
    exclude_recipe_ids: list[UUID] | None = None,
    fixed_exclude_recipe_ids: list[UUID] | None = None,
    available_equipment: list[str] | set[str] | None = None,
) -> tuple[list[DailyPlanData], ValidationResult]:
    """品質ゲート付き生成。NG時は問題レシピを除外してリトライする。

    重複排除フォールバック戦略:
    1. 全 exclude_ids（過去4週分）で生成を試みる
    2. 候補が7件未満なら、exclude_ids を半分（過去2週分相当）に減らしてリトライ
    3. それでも不足なら、exclude_ids を空にして重複を許容し plan_meta に記録
    """
    original_exclude = list(exclude_recipe_ids or [])
    fixed_exclude = list(fixed_exclude_recipe_ids or [])
    variable_exclude = list(original_exclude)
    plans: list[DailyPlanData] = []
    validation = ValidationResult()
    duplicate_allowed = False

    for attempt in range(MAX_RETRIES):
        all_exclude = list({*fixed_exclude, *variable_exclude})
        plans, selection_metrics = await generate_weekly_plan_v3(
            start_date=start_date,
            pfc_budget=pfc_budget,
            goal_type=goal_type,
            supabase=supabase,
            favorite_ids=favorite_ids,
            liked_ids=liked_ids,
            disliked_ids=disliked_ids,
            staple_tags=staple_tags,
            staple_keywords=staple_keywords,
            staple_short_name=staple_short_name,
            allowed_sources=allowed_sources,
            prefer_favorites=prefer_favorites,
            exclude_disliked=exclude_disliked,
            prefer_variety=prefer_variety,
            training_scale=training_scale,
            protect_forearms=protect_forearms,
            exercise_recommendations=exercise_recommendations,
            exclude_recipe_ids=all_exclude if all_exclude else None,
            available_equipment=available_equipment,
        )
        validation = validate_weekly_plan(plans)
        validation.metrics.update(selection_metrics)

        candidate_count = selection_metrics.get("dinner_total_count", 0)

        # 候補不足時のフォールバック: exclude_ids を段階的に緩和
        if candidate_count < 7 and (variable_exclude or fixed_exclude):
            half_len = len(original_exclude) // 2
            if len(variable_exclude) > half_len and half_len > 0:
                # 過去2週分相当に縮小してリトライ
                logger.info(
                    "候補不足 (%d < 7): variable_exclude を %d → %d に縮小してリトライ",
                    candidate_count,
                    len(variable_exclude),
                    half_len,
                )
                variable_exclude = original_exclude[:half_len]
                continue

            if variable_exclude:
                # それでも不足なら「過去週除外」のみ解除（固定除外は維持）
                logger.warning("候補不足 (%d < 7): variable_exclude を解除して生成", candidate_count)
                variable_exclude = []
                duplicate_allowed = True
                continue

            # fixed 除外だけでも不足する場合は、同一レシピ再選出を避けるため fixed は維持して返す。
            logger.warning("候補不足 (%d < 7): fixed_exclude 維持のまま返却", candidate_count)
            if duplicate_allowed:
                validation.metrics["duplicate_allowed"] = True
            return plans, validation

        if validation.is_valid or attempt == MAX_RETRIES - 1:
            if not validation.is_valid:
                logger.warning("Plan validation failed after %d retries: %s", MAX_RETRIES, validation.issues)
            if duplicate_allowed:
                validation.metrics["duplicate_allowed"] = True
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
