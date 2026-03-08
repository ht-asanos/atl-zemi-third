"""買い物リスト自動生成サービス。

週間プランの夕食レシピから食材を集約し、買い物リストを作成する。
集約キー: mext_food_id 優先、NULL の場合は ingredient_name でフォールバック。
"""

from datetime import date
from uuid import UUID

from app.repositories import plan_repo, recipe_repo
from app.schemas.plan import ShoppingListItem, ShoppingListResponse

from supabase import AsyncClient


async def generate_shopping_list(supabase: AsyncClient, user_id: UUID, start_date: date) -> ShoppingListResponse:
    plans = await plan_repo.get_weekly_plans(supabase, user_id, start_date)

    # dinner の recipe.id を抽出
    recipe_ids: list[UUID] = []
    for plan in plans:
        meal_plan = plan.meal_plan
        if not isinstance(meal_plan, list):
            continue
        for meal in meal_plan:
            if not isinstance(meal, dict):
                continue
            if meal.get("meal_type") != "dinner":
                continue
            recipe = meal.get("recipe")
            if recipe and recipe.get("id"):
                recipe_ids.append(UUID(recipe["id"]))

    if not recipe_ids:
        return ShoppingListResponse(start_date=start_date, items=[], recipe_count=0)

    unique_recipe_ids = list(set(recipe_ids))
    ingredients = await recipe_repo.get_ingredients_for_recipes(supabase, unique_recipe_ids)

    # 集約: mext_food_id 優先、None の場合は ingredient_name
    aggregated: dict[str, dict] = {}
    for ing in ingredients:
        mext_food_id = ing.get("mext_food_id")
        ingredient_name = ing.get("ingredient_name", "")
        recipe_title = ing.get("recipe_title", "")

        if mext_food_id:
            key = f"mext:{mext_food_id}"
        else:
            key = f"name:{ingredient_name}"

        if key not in aggregated:
            mext_foods = ing.get("mext_foods") or {}
            display_name = mext_foods.get("name", ingredient_name) if mext_food_id else ingredient_name
            category_name = mext_foods.get("category_name") if mext_food_id else None
            aggregated[key] = {
                "ingredient_name": display_name,
                "mext_food_id": mext_food_id,
                "amount_text": ing.get("amount_text"),
                "amount_g": ing.get("amount_g") or 0.0,
                "category_name": category_name,
                "recipe_titles": set(),
            }
        else:
            # amount_g を合算
            aggregated[key]["amount_g"] += ing.get("amount_g") or 0.0

        if recipe_title:
            aggregated[key]["recipe_titles"].add(recipe_title)

    items = [
        ShoppingListItem(
            ingredient_name=v["ingredient_name"],
            mext_food_id=v["mext_food_id"],
            amount_text=v["amount_text"],
            amount_g=v["amount_g"] if v["amount_g"] > 0 else None,
            category_name=v["category_name"],
            recipe_titles=sorted(v["recipe_titles"]),
        )
        for v in aggregated.values()
    ]

    # category_name でソート（None は末尾）
    items.sort(key=lambda x: (x.category_name or "zzz", x.ingredient_name))

    return ShoppingListResponse(
        start_date=start_date,
        items=items,
        recipe_count=len(unique_recipe_ids),
    )
