"""プラン品質検証。

生成後のプランを検証し、栄養計算失敗・重複レシピ等の品質問題を検出する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.models.food import MealType, NutritionStatus

if TYPE_CHECKING:
    pass


@dataclass
class ValidationResult:
    is_valid: bool = True
    issues: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


def validate_weekly_plan(daily_plans: list[Any]) -> ValidationResult:
    """生成後の品質検証を行う。"""
    issues: list[str] = []
    failed_count = 0
    zero_kcal_count = 0
    recipe_ids: list[str] = []

    for dp in daily_plans:
        for meal in dp.meals:
            if meal.meal_type != MealType.DINNER:
                continue
            if meal.nutrition_status == NutritionStatus.FAILED:
                failed_count += 1
                issues.append(f"{dp.plan_date}: 夕食の栄養計算に失敗")
            if meal.total_kcal == 0:
                zero_kcal_count += 1
                issues.append(f"{dp.plan_date}: 夕食のカロリーが0")
            if meal.recipe and isinstance(meal.recipe, dict):
                rid = meal.recipe.get("id")
                if rid:
                    recipe_ids.append(rid)

    # 重複率チェック
    unique_ids = set(recipe_ids)
    dup_count = len(recipe_ids) - len(unique_ids)
    dup_rate = dup_count / len(recipe_ids) if recipe_ids else 0.0
    if dup_rate > 0.3:
        issues.append(f"レシピ重複率 {dup_rate:.0%} (>{30}%)")

    is_valid = failed_count == 0 and zero_kcal_count == 0 and dup_rate <= 0.3

    metrics = {
        "failed_count": failed_count,
        "zero_kcal_count": zero_kcal_count,
        "dup_rate": round(dup_rate, 2),
        "total_dinners": len(recipe_ids),
        "unique_recipes": len(unique_ids),
    }

    return ValidationResult(is_valid=is_valid, issues=issues, metrics=metrics)
