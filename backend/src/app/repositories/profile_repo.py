from typing import Any
from uuid import UUID

from app.schemas.profile import CreateProfileRequest, ProfileResponse, UpdateProfileRequest

from supabase import AsyncClient


def _row_to_profile(row: dict[str, Any]) -> ProfileResponse:
    return ProfileResponse(
        id=UUID(row["id"]),
        age=row["age"],
        gender=row["gender"],
        height_cm=row["height_cm"],
        weight_kg=row["weight_kg"],
        activity_level=row["activity_level"],
    )


async def create_profile(supabase: AsyncClient, user_id: UUID, data: CreateProfileRequest) -> ProfileResponse:
    response = (
        await supabase.table("profiles")
        .insert(
            {
                "id": str(user_id),
                "age": data.age,
                "gender": data.gender.value,
                "height_cm": data.height_cm,
                "weight_kg": data.weight_kg,
                "activity_level": data.activity_level.value,
            }
        )
        .execute()
    )
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    return _row_to_profile(rows[0])


async def get_profile(supabase: AsyncClient, user_id: UUID) -> ProfileResponse | None:
    response = await supabase.table("profiles").select("*").eq("id", str(user_id)).limit(1).execute()
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    if not rows:
        return None
    return _row_to_profile(rows[0])


async def update_profile(supabase: AsyncClient, user_id: UUID, data: UpdateProfileRequest) -> ProfileResponse:
    response = (
        await supabase.table("profiles")
        .update(
            {
                "age": data.age,
                "gender": data.gender.value,
                "height_cm": data.height_cm,
                "weight_kg": data.weight_kg,
                "activity_level": data.activity_level.value,
            }
        )
        .eq("id", str(user_id))
        .execute()
    )
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    return _row_to_profile(rows[0])
