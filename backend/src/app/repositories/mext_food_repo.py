"""mext_foods テーブル操作"""

from typing import Any
from uuid import UUID

from app.models.food import MextFood

from supabase import AsyncClient


def _row_to_mext_food(row: dict[str, Any]) -> MextFood:
    return MextFood(
        id=row["id"],
        mext_food_id=row["mext_food_id"],
        name=row["name"],
        display_name=row.get("display_name"),
        category_code=row["category_code"],
        category_name=row["category_name"],
        kcal_per_100g=row["kcal_per_100g"],
        protein_g_per_100g=row["protein_g_per_100g"],
        fat_g_per_100g=row["fat_g_per_100g"],
        carbs_g_per_100g=row["carbs_g_per_100g"],
        fiber_g_per_100g=row.get("fiber_g_per_100g"),
        sodium_mg_per_100g=row.get("sodium_mg_per_100g"),
        calcium_mg_per_100g=row.get("calcium_mg_per_100g"),
        iron_mg_per_100g=row.get("iron_mg_per_100g"),
        raw_data=row.get("raw_data", {}),
    )


async def search_by_name(supabase: AsyncClient, query: str, limit: int = 20) -> list[MextFood]:
    """MEXT 食品名を部分一致で検索する。

    入力の空白・記号ゆらぎを吸収するため、クエリをトークンに分割して
    `%token1%token2%...%` 形式の ILIKE で検索する。
    """
    tokens = [t for t in query.replace("　", " ").replace("/", " ").split() if t]
    if tokens:
        pattern = "%" + "%".join(tokens) + "%"
    else:
        pattern = f"%{query}%"
    response = await supabase.table("mext_foods").select("*").ilike("name", pattern).limit(limit).execute()
    rows: list[dict[str, Any]] = response.data or []
    return [_row_to_mext_food(r) for r in rows]


async def get_by_id(supabase: AsyncClient, food_id: UUID) -> MextFood | None:
    response = await supabase.table("mext_foods").select("*").eq("id", str(food_id)).limit(1).execute()
    rows: list[dict[str, Any]] = response.data or []
    if not rows:
        return None
    return _row_to_mext_food(rows[0])


async def upsert_foods(supabase: AsyncClient, foods: list[MextFood], batch_size: int = 500) -> int:
    """MEXT 食品を一括 upsert する。mext_food_id で重複判定。バッチ処理対応。"""
    if not foods:
        return 0

    total = 0
    for i in range(0, len(foods), batch_size):
        batch = foods[i : i + batch_size]
        records = [
            {
                "mext_food_id": f.mext_food_id,
                "name": f.name,
                "category_code": f.category_code,
                "category_name": f.category_name,
                "kcal_per_100g": f.kcal_per_100g,
                "protein_g_per_100g": f.protein_g_per_100g,
                "fat_g_per_100g": f.fat_g_per_100g,
                "carbs_g_per_100g": f.carbs_g_per_100g,
                "fiber_g_per_100g": f.fiber_g_per_100g,
                "sodium_mg_per_100g": f.sodium_mg_per_100g,
                "calcium_mg_per_100g": f.calcium_mg_per_100g,
                "iron_mg_per_100g": f.iron_mg_per_100g,
                "raw_data": f.raw_data,
            }
            for f in batch
        ]
        response = await supabase.table("mext_foods").upsert(records, on_conflict="mext_food_id").execute()
        total += len(response.data or [])
    return total


async def get_foods_without_display_name(supabase: AsyncClient, limit: int = 200) -> list[MextFood]:
    """display_name が NULL のレコードを取得する。"""
    response = await supabase.table("mext_foods").select("*").is_("display_name", "null").limit(limit).execute()
    rows: list[dict[str, Any]] = response.data or []
    return [_row_to_mext_food(r) for r in rows]


async def update_display_names(supabase: AsyncClient, updates: list[tuple[UUID, str]]) -> int:
    """display_name を一括更新する。update-display-names CLI 専用。"""
    count = 0
    for food_id, display_name in updates:
        await supabase.table("mext_foods").update({"display_name": display_name}).eq("id", str(food_id)).execute()
        count += 1
    return count
