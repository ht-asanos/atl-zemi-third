from datetime import date
from uuid import UUID

from app.data.food_master import STAPLE_TAG_MAP, STAPLE_TITLE_KEYWORDS
from app.dependencies.auth import get_current_user_id
from app.dependencies.supabase_client import get_authenticated_supabase
from app.models.food import FoodCategory, MealSuggestion
from app.models.nutrition import PFCBudget
from app.repositories import favorite_repo, food_repo, goal_repo, plan_repo, recipe_repo, shopping_check_repo
from app.schemas.plan import (
    DailyPlanResponse,
    PatchMealRequest,
    SetShoppingListCheckRequest,
    ShoppingListChecksResponse,
    ShoppingListResponse,
    WeeklyPlanRequest,
    WeeklyPlanResponse,
)
from app.services.meal_suggestion import _make_dinner_from_recipe, calc_dinner_budget, generate_daily_meals
from app.services.shopping_list import generate_shopping_list
from app.services.training_adaptation import build_next_week_training_adjustment
from app.services.weekly_planner import generate_weekly_plan, generate_weekly_plan_v3_validated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from postgrest.exceptions import APIError

from supabase import AsyncClient

router = APIRouter(prefix="/plans", tags=["plans"])


async def _validate_staple(supabase: AsyncClient, staple_name: str):
    food = await food_repo.get_food_by_name(supabase, staple_name)
    if food is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Food not found: {staple_name}")
    if food.category != FoodCategory.STAPLE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Food '{staple_name}' is not a staple (category: {food.category.value})",
        )
    return food


@router.get("/weekly", response_model=WeeklyPlanResponse)
async def get_weekly_plan(
    start_date: date = Query(...),
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> WeeklyPlanResponse:
    plans = await plan_repo.get_weekly_plans(supabase, user_id, start_date)
    return WeeklyPlanResponse(plans=plans)


@router.get("/weekly/shopping-list", response_model=ShoppingListResponse)
async def get_shopping_list(
    start_date: date = Query(...),
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> ShoppingListResponse:
    checked_group_ids = await shopping_check_repo.get_checked_group_ids(supabase, user_id, start_date)
    return await generate_shopping_list(supabase, user_id, start_date, checked_group_ids=checked_group_ids)


@router.get("/weekly/shopping-list/checks", response_model=ShoppingListChecksResponse)
async def get_shopping_list_checks(
    start_date: date = Query(...),
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> ShoppingListChecksResponse:
    checked_group_ids = await shopping_check_repo.get_checked_group_ids(supabase, user_id, start_date)
    return ShoppingListChecksResponse(start_date=start_date, checked_group_ids=sorted(checked_group_ids))


@router.post("/weekly/shopping-list/checks", status_code=status.HTTP_204_NO_CONTENT)
async def set_shopping_list_check(
    body: SetShoppingListCheckRequest,
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> None:
    await shopping_check_repo.set_group_checked(
        supabase=supabase,
        user_id=user_id,
        start_date=body.start_date,
        group_id=body.group_id,
        checked=body.checked,
    )


@router.post("/weekly", status_code=status.HTTP_201_CREATED, response_model=WeeklyPlanResponse)
async def create_weekly_plan(
    body: WeeklyPlanRequest,
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> WeeklyPlanResponse:
    goal = await goal_repo.get_latest_goal(supabase, user_id)
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found. Create goal first.")

    pfc_budget = PFCBudget(protein_g=goal.protein_g, fat_g=goal.fat_g, carbs_g=goal.carbs_g)
    training_adj = await build_next_week_training_adjustment(supabase, user_id, body.start_date, goal.goal_type)

    if body.mode == "recipe":
        fav_ids = await favorite_repo.get_favorite_recipe_ids(supabase, user_id)
        staple_tags = None
        staple_keywords = None
        if body.staple_name:
            staple_tags = STAPLE_TAG_MAP.get(body.staple_name)
            staple_keywords = STAPLE_TITLE_KEYWORDS.get(body.staple_name)
        daily_plans, validation = await generate_weekly_plan_v3_validated(
            start_date=body.start_date,
            pfc_budget=pfc_budget,
            goal_type=goal.goal_type,
            supabase=supabase,
            favorite_ids=fav_ids,
            staple_tags=staple_tags,
            staple_keywords=staple_keywords,
            training_scale=training_adj.scale,
            protect_forearms=training_adj.protect_forearms,
        )
        # 主食指定時は非一致フォールバックを許容しない。
        # 一致候補ゼロなら生成を失敗として返し、ユーザーに再設定を促す。
        if body.staple_name and validation.metrics.get("staple_match_count", 0) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"主食「{body.staple_name}」に一致する夕食レシピが見つかりません。"
                    "主食を変更するか、レシピデータを追加してください。"
                ),
            )
    else:  # classic
        if not body.staple_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="staple_name is required for classic mode",
            )
        staple = await _validate_staple(supabase, body.staple_name)
        protein_foods = await food_repo.get_protein_foods(supabase)
        bulk_foods = await food_repo.get_bulk_foods(supabase)
        daily_plans = generate_weekly_plan(
            start_date=body.start_date,
            pfc_budget=pfc_budget,
            staple=staple,
            goal_type=goal.goal_type,
            protein_foods=protein_foods,
            bulk_foods=bulk_foods,
            training_scale=training_adj.scale,
            protect_forearms=training_adj.protect_forearms,
        )

    plan_meta: dict = {"mode": body.mode, "staple_name": body.staple_name}
    if body.mode == "recipe":
        plan_meta["validation"] = validation.metrics
        plan_meta["validation_issues"] = validation.issues
    plans_data = [
        {
            "user_id": str(user_id),
            "plan_date": dp.plan_date.isoformat(),
            "meal_plan": [m.model_dump() for m in dp.meals],
            "workout_plan": dp.training_day.model_dump() if dp.training_day else {},
            "plan_meta": plan_meta,
        }
        for dp in daily_plans
    ]
    await plan_repo.upsert_weekly_plans(supabase, plans_data)

    saved = await plan_repo.get_weekly_plans(supabase, user_id, body.start_date)
    return WeeklyPlanResponse(plans=saved)


@router.patch("/{plan_id}/recipe", response_model=DailyPlanResponse)
async def patch_recipe(
    plan_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> DailyPlanResponse:
    """夕食レシピを差し替える。"""
    row = await plan_repo.get_daily_plan_row_by_user(supabase, plan_id, user_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    meal_plan = row["meal_plan"]
    if not isinstance(meal_plan, list):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid meal_plan format")

    # dinner を特定
    dinner_index: int | None = None
    current_recipe_id: UUID | None = None
    for i, meal in enumerate(meal_plan):
        if meal.get("meal_type") == "dinner":
            dinner_index = i
            recipe_data = meal.get("recipe")
            if recipe_data and recipe_data.get("id"):
                current_recipe_id = UUID(recipe_data["id"])
            break

    if dinner_index is None or current_recipe_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="This plan does not use recipe mode",
        )

    # 朝昼の実データから dinner 予算を計算
    goal = await goal_repo.get_latest_goal(supabase, user_id)
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")

    pfc_budget = PFCBudget(protein_g=goal.protein_g, fat_g=goal.fat_g, carbs_g=goal.carbs_g)

    breakfast_data = None
    lunch_data = None
    for meal in meal_plan:
        if meal.get("meal_type") == "breakfast":
            breakfast_data = meal
        elif meal.get("meal_type") == "lunch":
            lunch_data = meal

    def _meal_data_to_suggestion(data: dict) -> MealSuggestion:
        return MealSuggestion(
            staple=data.get("staple", {}),
            protein_sources=data.get("protein_sources", []),
            bulk_items=data.get("bulk_items", []),
            total_kcal=data.get("total_kcal", 0),
            total_protein_g=data.get("total_protein_g", 0),
            total_fat_g=data.get("total_fat_g", 0),
            total_carbs_g=data.get("total_carbs_g", 0),
            total_price_yen=data.get("total_price_yen", 0),
            total_cooking_minutes=data.get("total_cooking_minutes", 0),
        )

    _empty_staple = {
        "name": "",
        "category": "staple",
        "kcal_per_serving": 0,
        "protein_g": 0,
        "fat_g": 0,
        "carbs_g": 0,
        "serving_unit": "",
        "price_yen": 0,
        "cooking_minutes": 0,
    }
    _zero_meal = MealSuggestion(
        staple=_empty_staple,
        protein_sources=[],
        bulk_items=[],
        total_kcal=0,
        total_protein_g=0,
        total_fat_g=0,
        total_carbs_g=0,
        total_price_yen=0,
        total_cooking_minutes=0,
    )
    breakfast_meal = _meal_data_to_suggestion(breakfast_data) if breakfast_data else _zero_meal
    lunch_meal = _meal_data_to_suggestion(lunch_data) if lunch_data else _zero_meal

    dinner_budget = calc_dinner_budget(pfc_budget, breakfast_meal, lunch_meal)

    # plan_meta から staple 情報を復元
    plan_meta = row.get("plan_meta") or {}
    staple_name = plan_meta.get("staple_name")
    patch_staple_tags = STAPLE_TAG_MAP.get(staple_name) if staple_name else None
    patch_staple_keywords = STAPLE_TITLE_KEYWORDS.get(staple_name) if staple_name else None

    # 新レシピ取得（現在のレシピを除外、主食フィルタ付き）
    result = await recipe_repo.get_recipes_for_dinner(
        supabase,
        dinner_budget,
        count=1,
        exclude_ids=[current_recipe_id],
        staple_tags=patch_staple_tags,
        staple_keywords=patch_staple_keywords,
    )
    if staple_name and result.staple_match_count == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"主食「{staple_name}」に一致する代替レシピが見つかりません",
        )
    new_recipes = result.recipes
    if not new_recipes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No alternative recipe found")

    new_dinner = _make_dinner_from_recipe(new_recipes[0])
    meal_plan[dinner_index] = new_dinner.model_dump()

    workout_plan = row["workout_plan"]
    expected_updated_at = row["updated_at"]

    try:
        await plan_repo.update_daily_plan(supabase, plan_id, meal_plan, workout_plan, expected_updated_at)
    except APIError as e:
        if "40001" in str(e):
            raise HTTPException(status_code=409, detail="Plan was modified concurrently") from e
        raise

    updated = await plan_repo.get_daily_plan(supabase, plan_id)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found after update")
    return updated


@router.patch("/{plan_id}/meal", response_model=DailyPlanResponse)
async def patch_meal(
    plan_id: UUID,
    body: PatchMealRequest,
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> DailyPlanResponse:
    existing = await plan_repo.get_daily_plan_by_user(supabase, plan_id, user_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    goal = await goal_repo.get_latest_goal(supabase, user_id)
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")

    staple = await _validate_staple(supabase, body.staple_name)
    protein_foods = await food_repo.get_protein_foods(supabase)
    bulk_foods = await food_repo.get_bulk_foods(supabase)

    pfc_budget = PFCBudget(protein_g=goal.protein_g, fat_g=goal.fat_g, carbs_g=goal.carbs_g)
    meals = generate_daily_meals(pfc_budget, staple, protein_foods=protein_foods, bulk_foods=bulk_foods)
    new_meal_plan = [m.model_dump() for m in meals]

    await plan_repo.update_meal_plan(supabase, plan_id, new_meal_plan)

    updated = await plan_repo.get_daily_plan(supabase, plan_id)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found after update")
    return updated
