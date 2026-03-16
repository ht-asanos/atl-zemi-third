"""買い物リスト自動生成サービス。

週間プランの夕食レシピから食材を集約し、買い物リストを作成する。
集約キー: mext_food_id 優先、NULL の場合は ingredient_name でフォールバック。
"""

import hashlib
from datetime import date
from uuid import UUID

from app.repositories import plan_repo, recipe_repo
from app.schemas.plan import ShoppingListItem, ShoppingListResponse
from app.services.shopping_normalizer import is_purchasable, normalize_ingredient_candidates

from supabase import AsyncClient


def _make_group_id(candidates: list[str]) -> str:
    base = "|".join(sorted(candidates))
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]
    return f"g:{digest}"


async def generate_shopping_list(
    supabase: AsyncClient,
    user_id: UUID,
    start_date: date,
    checked_group_ids: set[str] | None = None,
) -> ShoppingListResponse:
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

    # 集約: mext_food_id 優先、None の場合は正規化名でフォールバック
    aggregated: dict[str, dict] = {}
    checked = checked_group_ids or set()
    for ing in ingredients:
        mext_food_id = ing.get("mext_food_id")
        ingredient_name = ing.get("ingredient_name", "")
        recipe_title = ing.get("recipe_title", "")
        candidates = normalize_ingredient_candidates(ingredient_name)
        if not candidates:
            continue
        group_id = _make_group_id(candidates)
        checked_state = group_id in checked

        mext_foods = ing.get("mext_foods") or {}
        category_name = mext_foods.get("category_name") if mext_food_id else None

        for canonical_name in candidates:
            if mext_food_id:
                key = f"mext:{mext_food_id}"
            else:
                key = f"name:{canonical_name}:g:{group_id}"

            if key not in aggregated:
                display_name = (
                    (mext_foods.get("display_name") or mext_foods.get("name", canonical_name))
                    if mext_food_id
                    else canonical_name
                )
                aggregated[key] = {
                    "ingredient_name": display_name,
                    "group_id": group_id,
                    "checked": checked_state,
                    "mext_food_id": mext_food_id,
                    "amount_text": ing.get("amount_text"),
                    "amount_g": ing.get("amount_g") or 0.0,
                    "category_name": category_name,
                    "recipe_titles": set(),
                    "is_purchasable": is_purchasable(canonical_name, category_name),
                }
            else:
                # amount_g を合算
                aggregated[key]["amount_g"] += ing.get("amount_g") or 0.0

            if recipe_title:
                aggregated[key]["recipe_titles"].add(recipe_title)

    items = [
        ShoppingListItem(
            ingredient_name=v["ingredient_name"],
            group_id=v.get("group_id"),
            checked=bool(v.get("checked")),
            mext_food_id=v["mext_food_id"],
            amount_text=v["amount_text"],
            amount_g=v["amount_g"] if v["amount_g"] > 0 else None,
            category_name=v["category_name"],
            recipe_titles=sorted(v["recipe_titles"]),
            is_purchasable=v["is_purchasable"],
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
