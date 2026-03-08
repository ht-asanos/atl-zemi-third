"""user_recipe_favorites テーブル操作"""

from typing import Any
from uuid import UUID

from supabase import AsyncClient


async def add_favorite(supabase: AsyncClient, user_id: UUID, recipe_id: UUID) -> UUID:
    response = await (
        supabase.table("user_recipe_favorites").insert({"user_id": str(user_id), "recipe_id": str(recipe_id)}).execute()
    )
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    return UUID(rows[0]["id"])


async def remove_favorite(supabase: AsyncClient, user_id: UUID, recipe_id: UUID) -> bool:
    response = await (
        supabase.table("user_recipe_favorites")
        .delete()
        .eq("user_id", str(user_id))
        .eq("recipe_id", str(recipe_id))
        .execute()
    )
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    return len(rows) > 0


async def get_favorite_recipe_ids(supabase: AsyncClient, user_id: UUID) -> set[UUID]:
    response = await supabase.table("user_recipe_favorites").select("recipe_id").eq("user_id", str(user_id)).execute()
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    return {UUID(r["recipe_id"]) for r in rows}


async def get_favorites_with_created_at(supabase: AsyncClient, user_id: UUID) -> list[dict[str, Any]]:
    response = await (
        supabase.table("user_recipe_favorites")
        .select("recipe_id, created_at")
        .eq("user_id", str(user_id))
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []
