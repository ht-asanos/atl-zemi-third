from datetime import date
from typing import Any
from uuid import UUID

from app.schemas.log import CreateMealLogRequest, CreateWorkoutLogRequest, MealLogResponse, WorkoutLogResponse

from supabase import AsyncClient


def _row_to_meal_log(row: dict[str, Any]) -> MealLogResponse:
    return MealLogResponse(
        id=UUID(row["id"]),
        plan_id=UUID(row["plan_id"]),
        log_date=row["log_date"],
        meal_type=row["meal_type"],
        completed=row["completed"],
        satisfaction=row.get("satisfaction"),
        created_at=row["created_at"],
    )


def _row_to_workout_log(row: dict[str, Any]) -> WorkoutLogResponse:
    return WorkoutLogResponse(
        id=UUID(row["id"]),
        plan_id=UUID(row["plan_id"]),
        log_date=row["log_date"],
        exercise_id=row["exercise_id"],
        sets=row["sets"],
        reps=row["reps"],
        rpe=row.get("rpe"),
        completed=row["completed"],
        created_at=row["created_at"],
    )


async def upsert_meal_log(supabase: AsyncClient, user_id: UUID, data: CreateMealLogRequest) -> MealLogResponse:
    row = {
        "user_id": str(user_id),
        "plan_id": str(data.plan_id),
        "log_date": data.log_date.isoformat(),
        "meal_type": data.meal_type,
        "completed": data.completed,
        "satisfaction": data.satisfaction,
    }
    response = await supabase.table("meal_logs").upsert(row, on_conflict="user_id,log_date,meal_type").execute()
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    return _row_to_meal_log(rows[0])


async def get_meal_logs_by_date(supabase: AsyncClient, user_id: UUID, log_date: date) -> list[MealLogResponse]:
    response = (
        await supabase.table("meal_logs")
        .select("*")
        .eq("user_id", str(user_id))
        .eq("log_date", log_date.isoformat())
        .execute()
    )
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    return [_row_to_meal_log(row) for row in rows]


async def upsert_workout_log(supabase: AsyncClient, user_id: UUID, data: CreateWorkoutLogRequest) -> WorkoutLogResponse:
    row = {
        "user_id": str(user_id),
        "plan_id": str(data.plan_id),
        "log_date": data.log_date.isoformat(),
        "exercise_id": data.exercise_id,
        "sets": data.sets,
        "reps": data.reps,
        "rpe": data.rpe,
        "completed": data.completed,
    }
    response = await supabase.table("workout_logs").upsert(row, on_conflict="user_id,log_date,exercise_id").execute()
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    return _row_to_workout_log(rows[0])


async def get_workout_logs_by_date(supabase: AsyncClient, user_id: UUID, log_date: date) -> list[WorkoutLogResponse]:
    response = (
        await supabase.table("workout_logs")
        .select("*")
        .eq("user_id", str(user_id))
        .eq("log_date", log_date.isoformat())
        .execute()
    )
    rows: list[dict[str, Any]] = response.data  # type: ignore[assignment]
    return [_row_to_workout_log(row) for row in rows]
