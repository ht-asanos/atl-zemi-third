from datetime import date
from uuid import UUID

from postgrest.exceptions import APIError

from supabase import AsyncClient


def _is_missing_table_error(e: APIError) -> bool:
    # PostgREST schema cache miss (migration 未適用)
    return "PGRST205" in str(e)


async def get_checked_group_ids(
    supabase: AsyncClient,
    user_id: UUID,
    start_date: date,
) -> set[str]:
    try:
        resp = (
            await supabase.table("shopping_list_checks")
            .select("group_id")
            .eq("user_id", str(user_id))
            .eq("start_date", start_date.isoformat())
            .eq("checked", True)
            .execute()
        )
    except APIError as e:
        if _is_missing_table_error(e):
            return set()
        raise
    rows = resp.data or []
    return {str(r.get("group_id")) for r in rows if r.get("group_id")}


async def set_group_checked(
    supabase: AsyncClient,
    user_id: UUID,
    start_date: date,
    group_id: str,
    checked: bool,
) -> None:
    if checked:
        try:
            await (
                supabase.table("shopping_list_checks")
                .upsert(
                    {
                        "user_id": str(user_id),
                        "start_date": start_date.isoformat(),
                        "group_id": group_id,
                        "checked": True,
                    },
                    on_conflict="user_id,start_date,group_id",
                )
                .execute()
            )
        except APIError as e:
            if _is_missing_table_error(e):
                return
            raise
        return

    try:
        await (
            supabase.table("shopping_list_checks")
            .delete()
            .eq("user_id", str(user_id))
            .eq("start_date", start_date.isoformat())
            .eq("group_id", group_id)
            .execute()
        )
    except APIError as e:
        if _is_missing_table_error(e):
            return
        raise
