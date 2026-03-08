from uuid import UUID

from app.dependencies.auth import get_current_user_id
from app.dependencies.supabase_client import get_authenticated_supabase
from app.repositories import profile_repo
from app.schemas.profile import CreateProfileRequest, ProfileResponse, UpdateProfileRequest, UpdateProfileResponse
from fastapi import APIRouter, Depends, HTTPException, status

from supabase import AsyncClient

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProfileResponse)
async def create_profile(
    body: CreateProfileRequest,
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> ProfileResponse:
    existing = await profile_repo.get_profile(supabase, user_id)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Profile already exists")
    return await profile_repo.create_profile(supabase, user_id, body)


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> ProfileResponse:
    profile = await profile_repo.get_profile(supabase, user_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile


@router.put("/me", response_model=UpdateProfileResponse)
async def update_my_profile(
    body: UpdateProfileRequest,
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> UpdateProfileResponse:
    old = await profile_repo.get_profile(supabase, user_id)
    if old is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    updated = await profile_repo.update_profile(supabase, user_id, body)
    needs_recalc = (
        old.weight_kg != body.weight_kg or old.height_cm != body.height_cm or old.activity_level != body.activity_level
    )
    return UpdateProfileResponse(profile=updated, goal_recalculation_needed=needs_recalc)
