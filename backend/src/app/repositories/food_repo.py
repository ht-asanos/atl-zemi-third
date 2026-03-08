from typing import Any

from app.models.food import FoodCategory, FoodItem

from supabase import AsyncClient


def _row_to_food(row: dict[str, Any]) -> FoodItem:
    return FoodItem(
        name=row["name"],
        category=FoodCategory(row["category"]),
        kcal_per_serving=row["kcal_per_serving"],
        protein_g=row["protein_g"],
        fat_g=row["fat_g"],
        carbs_g=row["carbs_g"],
        serving_unit=row["serving_unit"],
        price_yen=row["price_yen"],
        cooking_minutes=row["cooking_minutes"],
    )


async def get_foods_by_category(supabase: AsyncClient, category: FoodCategory) -> list[FoodItem]:
    response = await supabase.table("food_master").select("*").eq("category", category.value).execute()
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    return [_row_to_food(row) for row in rows]


async def get_staple_foods(supabase: AsyncClient) -> list[FoodItem]:
    return await get_foods_by_category(supabase, FoodCategory.STAPLE)


async def get_protein_foods(supabase: AsyncClient) -> list[FoodItem]:
    return await get_foods_by_category(supabase, FoodCategory.PROTEIN)


async def get_bulk_foods(supabase: AsyncClient) -> list[FoodItem]:
    return await get_foods_by_category(supabase, FoodCategory.BULK)


async def get_food_by_name(supabase: AsyncClient, name: str) -> FoodItem | None:
    response = await supabase.table("food_master").select("*").eq("name", name).limit(1).execute()
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    if not rows:
        return None
    return _row_to_food(rows[0])
