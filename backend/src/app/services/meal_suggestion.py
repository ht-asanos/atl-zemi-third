"""食事提案ロジック — 主食選択 → 残枠計算 → 組み合わせ生成

食材データは data.food_master を単一ソースとして import する。
レシピベース提案 (v2) も提供し、既存ロジックをフォールバックとして維持。
"""

import random

from app.data.food_master import FOOD_MASTER
from app.models.food import FoodCategory, FoodItem, MealSuggestion, MealType, NutritionStatus
from app.models.nutrition import PFCBudget
from app.models.recipe import Recipe
from app.repositories import recipe_repo
from app.services.nutrition_fallback import get_fallback_nutrition

from supabase import AsyncClient

# --- 朝食・昼食の固定データ ---

BREAKFAST_OPTIONS = [
    FoodItem(
        name="ヨーグルト",
        category=FoodCategory.PROTEIN,
        kcal_per_serving=62,
        protein_g=3.6,
        fat_g=3.0,
        carbs_g=4.9,
        serving_unit="1個(100g)",
        price_yen=30,
        cooking_minutes=0,
    ),
    FoodItem(
        name="納豆",
        category=FoodCategory.PROTEIN,
        kcal_per_serving=100,
        protein_g=8.3,
        fat_g=5.0,
        carbs_g=6.1,
        serving_unit="1パック(50g)",
        price_yen=30,
        cooking_minutes=0,
    ),
]

LUNCH_ITEM = FoodItem(
    name="おにぎり",
    category=FoodCategory.STAPLE,
    kcal_per_serving=180,
    protein_g=2.7,
    fat_g=0.3,
    carbs_g=39.4,
    serving_unit="1個(100g)",
    price_yen=120,
    cooking_minutes=0,
)


def get_staple_foods() -> list[FoodItem]:
    """主食 5 種を返却する。"""
    return [f for f in FOOD_MASTER if f.category == FoodCategory.STAPLE]


def get_protein_foods() -> list[FoodItem]:
    """タンパク源を返却する。"""
    return [f for f in FOOD_MASTER if f.category == FoodCategory.PROTEIN]


def get_bulk_foods() -> list[FoodItem]:
    """かさ増し食材を返却する。"""
    return [f for f in FOOD_MASTER if f.category == FoodCategory.BULK]


def calc_remaining_budget(daily_target: PFCBudget, meals_per_day: int, staple: FoodItem) -> PFCBudget:
    """1 食あたりの残枠 PFC を算出する。日次目標 / 食数 - 主食分。"""
    per_meal_protein = daily_target.protein_g / meals_per_day - staple.protein_g
    per_meal_fat = daily_target.fat_g / meals_per_day - staple.fat_g
    per_meal_carbs = daily_target.carbs_g / meals_per_day - staple.carbs_g
    return PFCBudget(
        protein_g=max(0, per_meal_protein),
        fat_g=max(0, per_meal_fat),
        carbs_g=max(0, per_meal_carbs),
    )


def suggest_meal(
    staple: FoodItem,
    remaining: PFCBudget,
    max_price_yen: int = 500,
    max_cooking_minutes: int = 10,
    protein_foods: list[FoodItem] | None = None,
    bulk_foods: list[FoodItem] | None = None,
) -> MealSuggestion:
    """タンパク源優先 → かさ増し追加で 1 食分を提案する。

    500 円 / 10 分制約を守る。
    """
    if protein_foods is None:
        protein_foods = get_protein_foods()
    if bulk_foods is None:
        bulk_foods = get_bulk_foods()

    used_price = staple.price_yen
    used_minutes = staple.cooking_minutes
    selected_proteins: list[FoodItem] = []
    selected_bulks: list[FoodItem] = []
    remaining_protein_g = remaining.protein_g

    # タンパク源を優先で追加
    for food in protein_foods:
        if remaining_protein_g <= 0:
            break
        if used_price + food.price_yen > max_price_yen:
            continue
        if used_minutes + food.cooking_minutes > max_cooking_minutes:
            continue
        selected_proteins.append(food)
        remaining_protein_g -= food.protein_g
        used_price += food.price_yen
        used_minutes += food.cooking_minutes

    # かさ増し食材を追加
    for food in bulk_foods:
        if used_price + food.price_yen > max_price_yen:
            continue
        if used_minutes + food.cooking_minutes > max_cooking_minutes:
            continue
        selected_bulks.append(food)
        used_price += food.price_yen
        used_minutes += food.cooking_minutes

    all_items = [staple] + selected_proteins + selected_bulks
    total_kcal = sum(f.kcal_per_serving for f in all_items)
    total_protein = sum(f.protein_g for f in all_items)
    total_fat = sum(f.fat_g for f in all_items)
    total_carbs = sum(f.carbs_g for f in all_items)

    return MealSuggestion(
        staple=staple,
        protein_sources=selected_proteins,
        bulk_items=selected_bulks,
        total_kcal=round(total_kcal, 1),
        total_protein_g=round(total_protein, 1),
        total_fat_g=round(total_fat, 1),
        total_carbs_g=round(total_carbs, 1),
        total_price_yen=used_price,
        total_cooking_minutes=used_minutes,
    )


def generate_daily_meals(
    daily_target: PFCBudget,
    staple: FoodItem,
    meals_per_day: int = 3,
    protein_foods: list[FoodItem] | None = None,
    bulk_foods: list[FoodItem] | None = None,
) -> list[MealSuggestion]:
    """1 日分の食事提案を生成する。"""
    remaining = calc_remaining_budget(daily_target, meals_per_day, staple)
    return [
        suggest_meal(staple, remaining, protein_foods=protein_foods, bulk_foods=bulk_foods)
        for _ in range(meals_per_day)
    ]


async def suggest_recipe_meal(remaining: PFCBudget, supabase: AsyncClient) -> Recipe | None:
    """DB からレシピを検索して PFC 予算に最も近いものを返す。"""
    recipes = await recipe_repo.get_recipes_with_nutrition(supabase, limit=50)
    if not recipes:
        return None

    target_protein = remaining.protein_g
    best: Recipe | None = None
    best_diff = float("inf")

    for recipe in recipes:
        nut = recipe.nutrition_per_serving
        if not nut:
            continue
        protein = nut.get("protein_g", 0)
        # protein 80-120% の範囲内でフィルタ
        if not (target_protein * 0.8 <= protein <= target_protein * 1.2):
            continue
        diff = abs(protein - target_protein)
        if diff < best_diff:
            best_diff = diff
            best = recipe

    return best


async def generate_daily_meals_v2(
    daily_target: PFCBudget,
    staple: FoodItem,
    supabase: AsyncClient | None = None,
    meals_per_day: int = 3,
    protein_foods: list[FoodItem] | None = None,
    bulk_foods: list[FoodItem] | None = None,
) -> list[MealSuggestion]:
    """レシピベース提案付きの 1 日分食事提案を生成する。

    各 slot でレシピ提案を試行し、失敗時は既存 greedy アルゴリズムにフォールバック。
    """
    remaining = calc_remaining_budget(daily_target, meals_per_day, staple)
    meals: list[MealSuggestion] = []

    for _ in range(meals_per_day):
        recipe = None
        if supabase is not None:
            recipe = await suggest_recipe_meal(remaining, supabase)

        meal = suggest_meal(staple, remaining, protein_foods=protein_foods, bulk_foods=bulk_foods)
        if recipe is not None:
            meal.recipe = recipe
        meals.append(meal)

    return meals


# --- recipe モード用の新関数 ---


def _make_breakfast() -> MealSuggestion:
    """ヨーグルトか納豆をランダムで返す。meal_type=breakfast。"""
    food = random.choice(BREAKFAST_OPTIONS)
    return MealSuggestion(
        meal_type=MealType.BREAKFAST,
        staple=food,
        protein_sources=[],
        bulk_items=[],
        total_kcal=round(food.kcal_per_serving, 1),
        total_protein_g=round(food.protein_g, 1),
        total_fat_g=round(food.fat_g, 1),
        total_carbs_g=round(food.carbs_g, 1),
        total_price_yen=food.price_yen,
        total_cooking_minutes=food.cooking_minutes,
    )


def _make_lunch() -> MealSuggestion:
    """おにぎり固定。meal_type=lunch。"""
    food = LUNCH_ITEM
    return MealSuggestion(
        meal_type=MealType.LUNCH,
        staple=food,
        protein_sources=[],
        bulk_items=[],
        total_kcal=round(food.kcal_per_serving, 1),
        total_protein_g=round(food.protein_g, 1),
        total_fat_g=round(food.fat_g, 1),
        total_carbs_g=round(food.carbs_g, 1),
        total_price_yen=food.price_yen,
        total_cooking_minutes=food.cooking_minutes,
    )


def _make_dinner_from_recipe(recipe: Recipe) -> MealSuggestion:
    """Recipe → MealSuggestion。meal_type=dinner。

    nutrition_status を recipe から伝搬する。
    nutrition_per_serving が None の場合（fallback 未実行の旧データ）は
    get_fallback_nutrition() でランタイム補完する。
    """
    nut = recipe.nutrition_per_serving
    meal_status = NutritionStatus.CALCULATED
    meal_warning: str | None = None

    if nut is None:
        # fallback 未実行の旧データ → ランタイム補完
        nut = get_fallback_nutrition(recipe)
        meal_status = NutritionStatus.ESTIMATED
        meal_warning = "推定値です"
    elif recipe.nutrition_status == NutritionStatus.ESTIMATED:
        meal_status = NutritionStatus.ESTIMATED
        meal_warning = "一部食材のみで推定した値です"
    elif recipe.nutrition_status == NutritionStatus.FAILED:
        # fallback 適用済みの場合は ESTIMATED になっているはず
        # ここに来るのは fallback 未適用の旧データのみ
        nut = get_fallback_nutrition(recipe)
        meal_status = NutritionStatus.ESTIMATED
        meal_warning = "推定値です"
    # else: CALCULATED → デフォルトのまま

    return MealSuggestion(
        meal_type=MealType.DINNER,
        staple=FoodItem(
            name=recipe.title,
            category=FoodCategory.STAPLE,
            kcal_per_serving=nut.get("kcal", 0),
            protein_g=nut.get("protein_g", 0),
            fat_g=nut.get("fat_g", 0),
            carbs_g=nut.get("carbs_g", 0),
            serving_unit="1人前",
            price_yen=0,
            cooking_minutes=recipe.cooking_minutes or 0,
        ),
        protein_sources=[],
        bulk_items=[],
        total_kcal=round(nut.get("kcal", 0), 1),
        total_protein_g=round(nut.get("protein_g", 0), 1),
        total_fat_g=round(nut.get("fat_g", 0), 1),
        total_carbs_g=round(nut.get("carbs_g", 0), 1),
        total_price_yen=0,
        total_cooking_minutes=recipe.cooking_minutes or 0,
        recipe={
            "id": str(recipe.id),
            "title": recipe.title,
            "image_url": recipe.image_url,
            "recipe_url": recipe.recipe_url,
            "youtube_video_id": recipe.youtube_video_id,
            "recipe_source": recipe.recipe_source or "rakuten",
            "cooking_minutes": recipe.cooking_minutes,
            "nutrition_per_serving": {
                "kcal": round(nut.get("kcal", 0), 1),
                "protein_g": round(nut.get("protein_g", 0), 1),
                "fat_g": round(nut.get("fat_g", 0), 1),
                "carbs_g": round(nut.get("carbs_g", 0), 1),
            },
        },
        nutrition_status=meal_status,
        nutrition_warning=meal_warning,
    )


def calc_dinner_budget(daily_target: PFCBudget, breakfast: MealSuggestion, lunch: MealSuggestion) -> PFCBudget:
    """日次目標 - 朝食 - 昼食 = 夕食予算。"""
    return PFCBudget(
        protein_g=max(0, daily_target.protein_g - breakfast.total_protein_g - lunch.total_protein_g),
        fat_g=max(0, daily_target.fat_g - breakfast.total_fat_g - lunch.total_fat_g),
        carbs_g=max(0, daily_target.carbs_g - breakfast.total_carbs_g - lunch.total_carbs_g),
    )


def generate_structured_daily_meals(recipe: Recipe | None = None) -> list[MealSuggestion]:
    """[朝食, 昼食, 夕食] の3要素を返す。夕食は recipe or フォールバック。"""
    breakfast = _make_breakfast()
    lunch = _make_lunch()

    if recipe is not None:
        dinner = _make_dinner_from_recipe(recipe)
    else:
        # フォールバック: 既存 suggest_meal を使用
        fallback_staple = get_staple_foods()[0]
        remaining = PFCBudget(protein_g=40, fat_g=15, carbs_g=50)
        dinner = suggest_meal(fallback_staple, remaining)
        dinner.meal_type = MealType.DINNER

    return [breakfast, lunch, dinner]
