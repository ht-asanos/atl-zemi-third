from uuid import UUID

from app.dependencies.auth import get_current_user_id
from app.dependencies.supabase_client import get_authenticated_supabase
from app.models.nutrition import UserProfile
from app.repositories import goal_repo, profile_repo
from app.schemas.goal import CreateGoalRequest, GoalResponse
from app.services.nutrition_engine import calculate_nutrition_target
from fastapi import APIRouter, Depends, HTTPException, status

from supabase import AsyncClient

router = APIRouter(prefix="/goals", tags=["goals"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=GoalResponse)
async def create_goal(
    body: CreateGoalRequest,
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> GoalResponse:
    profile = await profile_repo.get_profile(supabase, user_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found. Create profile first.")

    user_profile = UserProfile(
        age=profile.age,
        gender=profile.gender,
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        activity_level=profile.activity_level,
        goal=body.goal_type,
    )
    target = calculate_nutrition_target(user_profile)

    return await goal_repo.upsert_goal(
        supabase,
        user_id,
        goal_type=body.goal_type.value,
        target_kcal=target.target_kcal,
        protein_g=target.pfc.protein_g,
        fat_g=target.pfc.fat_g,
        carbs_g=target.pfc.carbs_g,
    )


@router.get("/me", response_model=GoalResponse)
async def get_my_goal(
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> GoalResponse:
    goal = await goal_repo.get_latest_goal(supabase, user_id)
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    return goal
