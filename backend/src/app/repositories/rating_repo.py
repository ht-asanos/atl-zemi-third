"""user_recipe_ratings テーブル操作"""

from typing import Any
from uuid import UUID

from supabase import AsyncClient


async def upsert_rating(supabase: AsyncClient, user_id: UUID, recipe_id: UUID, rating: int) -> None:
    """レシピ評価を登録/更新する。rating=0 の場合はレコードを削除（未評価に戻す）。"""
    if rating == 0:
        await (
            supabase.table("user_recipe_ratings")
            .delete()
            .eq("user_id", str(user_id))
            .eq("recipe_id", str(recipe_id))
            .execute()
        )
        return

    await (
        supabase.table("user_recipe_ratings")
        .upsert(
            {
                "user_id": str(user_id),
                "recipe_id": str(recipe_id),
                "rating": rating,
                "updated_at": "now()",
            },
            on_conflict="user_id,recipe_id",
        )
        .execute()
    )


async def get_ratings_for_user(supabase: AsyncClient, user_id: UUID) -> dict[UUID, int]:
    """ユーザーの全評価を取得する。{recipe_id: rating}"""
    response = await (
        supabase.table("user_recipe_ratings").select("recipe_id, rating").eq("user_id", str(user_id)).execute()
    )
    rows: list[dict[str, Any]] = response.data or []
    return {UUID(r["recipe_id"]): r["rating"] for r in rows}


async def get_liked_recipe_ids(supabase: AsyncClient, user_id: UUID) -> set[UUID]:
    """rating=1 のレシピ ID を取得する。"""
    response = await (
        supabase.table("user_recipe_ratings").select("recipe_id").eq("user_id", str(user_id)).eq("rating", 1).execute()
    )
    rows: list[dict[str, Any]] = response.data or []
    return {UUID(r["recipe_id"]) for r in rows}


async def get_disliked_recipe_ids(supabase: AsyncClient, user_id: UUID) -> set[UUID]:
    """rating=-1 のレシピ ID を取得する。"""
    response = await (
        supabase.table("user_recipe_ratings").select("recipe_id").eq("user_id", str(user_id)).eq("rating", -1).execute()
    )
    rows: list[dict[str, Any]] = response.data or []
    return {UUID(r["recipe_id"]) for r in rows}


async def get_all_rated_recipe_ids(supabase: AsyncClient, user_id: UUID) -> set[UUID]:
    """評価済み（liked ∪ disliked）のレシピ ID を取得する。探索枠用。"""
    response = await supabase.table("user_recipe_ratings").select("recipe_id").eq("user_id", str(user_id)).execute()
    rows: list[dict[str, Any]] = response.data or []
    return {UUID(r["recipe_id"]) for r in rows}
