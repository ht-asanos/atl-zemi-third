"""週次プラン生成 — 7日分の食事 + トレーニングをまとめて生成する。

DB 保存責務は持たない（ルーター側で RPC 経由で一括保存）。
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from app.models.food import FoodItem, MealSuggestion
from app.models.nutrition import PFCBudget
from app.models.training import TrainingDay
from app.repositories import recipe_repo
from app.services.meal_suggestion import (
    _make_breakfast,
    _make_lunch,
    calc_dinner_budget,
    generate_daily_meals,
    generate_daily_meals_v2,
    generate_structured_daily_meals,
)
from app.services.training_template import get_template

from supabase import AsyncClient


@dataclass
class DailyPlanData:
    plan_date: date
    meals: list[MealSuggestion]
    training_day: TrainingDay | None


@dataclass
class WeeklyPlanResult:
    plans: list[DailyPlanData] = field(default_factory=list)


def generate_weekly_plan(
    start_date: date,
    pfc_budget: PFCBudget,
    staple: FoodItem,
    goal_type: str,
    protein_foods: list[FoodItem] | None = None,
    bulk_foods: list[FoodItem] | None = None,
) -> list[DailyPlanData]:
    """7日分のプランを生成する。

    トレーニング日はテンプレートの日数でサイクルする。
    """
    template = get_template(goal_type)
    training_days = template.days
    result: list[DailyPlanData] = []

    for day_offset in range(7):
        current_date = start_date + timedelta(days=day_offset)
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
) -> list[DailyPlanData]:
    """7日分のプランを生成する（レシピ提案対応版）。"""
    template = get_template(goal_type)
    training_days = template.days
    result: list[DailyPlanData] = []

    for day_offset in range(7):
        current_date = start_date + timedelta(days=day_offset)
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
) -> list[DailyPlanData]:
    """朝食固定 + 昼食固定 + 夕食レシピ（7日重複なし、PFC フィルタ付き）。"""
    template = get_template(goal_type)
    training_days = template.days

    # 朝食・昼食の栄養を差し引いて夕食予算を算出
    sample_breakfast = _make_breakfast()
    sample_lunch = _make_lunch()
    dinner_budget = calc_dinner_budget(pfc_budget, sample_breakfast, sample_lunch)

    # PFC フィルタ付きで 7 件のユニークレシピを取得
    dinner_recipes = await recipe_repo.get_recipes_for_dinner(
        supabase,
        dinner_budget,
        count=7,
        favorite_ids=favorite_ids,
        staple_tags=staple_tags,
        staple_keywords=staple_keywords,
    )

    result: list[DailyPlanData] = []
    for day_offset in range(7):
        recipe = dinner_recipes[day_offset] if day_offset < len(dinner_recipes) else None
        meals = generate_structured_daily_meals(recipe=recipe)
        training_day = training_days[day_offset % len(training_days)]
        result.append(
            DailyPlanData(
                plan_date=start_date + timedelta(days=day_offset),
                meals=meals,
                training_day=training_day,
            )
        )
    return result
