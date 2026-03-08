from datetime import date
from uuid import UUID

from app.dependencies.auth import get_current_user_id
from app.dependencies.supabase_client import get_authenticated_supabase
from app.repositories import log_repo
from app.schemas.log import (
    CreateMealLogRequest,
    CreateWorkoutLogRequest,
    MealLogResponse,
    WorkoutLogResponse,
)
from fastapi import APIRouter, Depends, Query, status

from supabase import AsyncClient

router = APIRouter(prefix="/logs", tags=["logs"])


@router.post("/meal", status_code=status.HTTP_201_CREATED, response_model=MealLogResponse)
async def create_meal_log(
    body: CreateMealLogRequest,
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> MealLogResponse:
    return await log_repo.upsert_meal_log(supabase, user_id, body)


@router.get("/meal", response_model=dict)
async def get_meal_logs(
    log_date: date = Query(...),
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> dict:
    logs = await log_repo.get_meal_logs_by_date(supabase, user_id, log_date)
    return {"logs": logs}


@router.post("/workout", status_code=status.HTTP_201_CREATED, response_model=WorkoutLogResponse)
async def create_workout_log(
    body: CreateWorkoutLogRequest,
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> WorkoutLogResponse:
    return await log_repo.upsert_workout_log(supabase, user_id, body)


@router.get("/workout", response_model=dict)
async def get_workout_logs(
    log_date: date = Query(...),
    user_id: UUID = Depends(get_current_user_id),
    supabase: AsyncClient = Depends(get_authenticated_supabase),
) -> dict:
    logs = await log_repo.get_workout_logs_by_date(supabase, user_id, log_date)
    return {"logs": logs}
