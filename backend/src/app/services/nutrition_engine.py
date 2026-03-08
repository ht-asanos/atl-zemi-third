"""栄養計算エンジン — BMR / TDEE / PFC 目標算出

計算途中は float のまま保持し丸めない。
最終出力の NutritionTarget のみ round(value, 1) で小数第1位に丸める。
"""

from app.models.nutrition import (
    ACTIVITY_MULTIPLIERS,
    ActivityLevel,
    Gender,
    Goal,
    NutritionTarget,
    PFCBudget,
    UserProfile,
)


def calc_bmr(gender: Gender, weight_kg: float, height_cm: float, age: int) -> float:
    """Mifflin-St Jeor 式で BMR を計算する。"""
    if gender == Gender.MALE:
        return 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        return 10 * weight_kg + 6.25 * height_cm - 5 * age - 161


def calc_tdee(bmr: float, activity_level: ActivityLevel) -> float:
    """BMR x 活動係数 で TDEE を算出する。"""
    return bmr * ACTIVITY_MULTIPLIERS[activity_level]


def calc_target_kcal(tdee: float, goal: Goal) -> float:
    """目的別カロリー目標を算出する。"""
    if goal == Goal.DIET:
        return tdee - 400
    elif goal == Goal.STRENGTH:
        return tdee + 250
    else:  # bouldering
        return tdee + 75


def calc_pfc(weight_kg: float, target_kcal: float) -> PFCBudget:
    """PFC 配分を算出する。

    - protein: 2.0 g/kg
    - fat: 0.8 g/kg
    - carbs: 残カロリー / 4
    """
    protein_g = weight_kg * 2.0
    fat_g = weight_kg * 0.8
    protein_kcal = protein_g * 4
    fat_kcal = fat_g * 9
    carbs_kcal = target_kcal - protein_kcal - fat_kcal
    carbs_g = carbs_kcal / 4
    return PFCBudget(protein_g=protein_g, fat_g=fat_g, carbs_g=carbs_g)


def calculate_nutrition_target(profile: UserProfile) -> NutritionTarget:
    """ユーザープロフィールから栄養目標を統合算出する。"""
    bmr = calc_bmr(profile.gender, profile.weight_kg, profile.height_cm, profile.age)
    tdee = calc_tdee(bmr, profile.activity_level)
    target_kcal = calc_target_kcal(tdee, profile.goal)
    pfc = calc_pfc(profile.weight_kg, target_kcal)

    return NutritionTarget(
        bmr=round(bmr, 1),
        tdee=round(tdee, 1),
        target_kcal=round(target_kcal, 1),
        pfc=PFCBudget(
            protein_g=round(pfc.protein_g, 1),
            fat_g=round(pfc.fat_g, 1),
            carbs_g=round(pfc.carbs_g, 1),
        ),
    )
