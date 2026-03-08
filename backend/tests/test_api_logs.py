"""API テスト — POST/GET /logs/meal, /logs/workout"""

from datetime import date, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.dependencies.auth import get_current_user_id
from app.dependencies.supabase_client import get_authenticated_supabase
from app.main import app
from app.schemas.log import MealLogResponse, WorkoutLogResponse
from fastapi.testclient import TestClient

TEST_USER_ID = uuid4()
PLAN_ID = uuid4()
LOG_DATE = "2026-03-09"


@pytest.fixture
def client():
    mock_supabase = AsyncMock()
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_authenticated_supabase] = lambda: mock_supabase
    yield TestClient(app, raise_server_exceptions=False), mock_supabase
    app.dependency_overrides.clear()


@pytest.fixture
def no_auth_client():
    """Token なしクライアント (認可異常系テスト)"""
    app.dependency_overrides.clear()
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


MOCK_MEAL_LOG = MealLogResponse(
    id=uuid4(),
    plan_id=PLAN_ID,
    log_date=date(2026, 3, 9),
    meal_type="breakfast",
    completed=True,
    satisfaction=4,
    created_at=datetime(2026, 3, 9, 12, 0),
)

MOCK_WORKOUT_LOG = WorkoutLogResponse(
    id=uuid4(),
    plan_id=PLAN_ID,
    log_date=date(2026, 3, 9),
    exercise_id="push_up",
    sets=3,
    reps=12,
    rpe=7.0,
    completed=True,
    created_at=datetime(2026, 3, 9, 12, 0),
)


class TestMealLogs:
    def test_create_meal_log_success(self, client) -> None:
        test_client, _ = client
        with patch("app.routers.logs.log_repo") as mock_repo:
            mock_repo.upsert_meal_log = AsyncMock(return_value=MOCK_MEAL_LOG)
            resp = test_client.post(
                "/logs/meal",
                json={
                    "plan_id": str(PLAN_ID),
                    "log_date": LOG_DATE,
                    "meal_type": "breakfast",
                    "completed": True,
                    "satisfaction": 4,
                },
            )
        assert resp.status_code == 201

    def test_create_meal_log_upsert(self, client) -> None:
        """同一キー再送信 → 201 (upsert)"""
        test_client, _ = client
        with patch("app.routers.logs.log_repo") as mock_repo:
            mock_repo.upsert_meal_log = AsyncMock(return_value=MOCK_MEAL_LOG)
            resp1 = test_client.post(
                "/logs/meal",
                json={
                    "plan_id": str(PLAN_ID),
                    "log_date": LOG_DATE,
                    "meal_type": "breakfast",
                    "completed": True,
                    "satisfaction": 3,
                },
            )
            resp2 = test_client.post(
                "/logs/meal",
                json={
                    "plan_id": str(PLAN_ID),
                    "log_date": LOG_DATE,
                    "meal_type": "breakfast",
                    "completed": True,
                    "satisfaction": 5,
                },
            )
        assert resp1.status_code == 201
        assert resp2.status_code == 201

    def test_get_meal_logs(self, client) -> None:
        test_client, _ = client
        with patch("app.routers.logs.log_repo") as mock_repo:
            mock_repo.get_meal_logs_by_date = AsyncMock(return_value=[MOCK_MEAL_LOG])
            resp = test_client.get(f"/logs/meal?log_date={LOG_DATE}")
        assert resp.status_code == 200
        assert len(resp.json()["logs"]) == 1

    def test_satisfaction_out_of_range(self, client) -> None:
        test_client, _ = client
        resp = test_client.post(
            "/logs/meal",
            json={
                "plan_id": str(PLAN_ID),
                "log_date": LOG_DATE,
                "meal_type": "breakfast",
                "completed": True,
                "satisfaction": 6,
            },
        )
        assert resp.status_code == 422

    def test_no_token_401(self, no_auth_client) -> None:
        resp = no_auth_client.post(
            "/logs/meal",
            json={
                "plan_id": str(PLAN_ID),
                "log_date": LOG_DATE,
                "meal_type": "breakfast",
                "completed": True,
            },
        )
        assert resp.status_code in (401, 403)


class TestWorkoutLogs:
    def test_create_workout_log_success(self, client) -> None:
        test_client, _ = client
        with patch("app.routers.logs.log_repo") as mock_repo:
            mock_repo.upsert_workout_log = AsyncMock(return_value=MOCK_WORKOUT_LOG)
            resp = test_client.post(
                "/logs/workout",
                json={
                    "plan_id": str(PLAN_ID),
                    "log_date": LOG_DATE,
                    "exercise_id": "push_up",
                    "sets": 3,
                    "reps": 12,
                    "rpe": 7.0,
                    "completed": True,
                },
            )
        assert resp.status_code == 201

    def test_get_workout_logs(self, client) -> None:
        test_client, _ = client
        with patch("app.routers.logs.log_repo") as mock_repo:
            mock_repo.get_workout_logs_by_date = AsyncMock(return_value=[MOCK_WORKOUT_LOG])
            resp = test_client.get(f"/logs/workout?log_date={LOG_DATE}")
        assert resp.status_code == 200
        assert len(resp.json()["logs"]) == 1

    def test_rpe_out_of_range(self, client) -> None:
        test_client, _ = client
        resp = test_client.post(
            "/logs/workout",
            json={
                "plan_id": str(PLAN_ID),
                "log_date": LOG_DATE,
                "exercise_id": "push_up",
                "sets": 3,
                "reps": 12,
                "rpe": 11.0,
                "completed": True,
            },
        )
        assert resp.status_code == 422

    def test_no_token_401(self, no_auth_client) -> None:
        resp = no_auth_client.post(
            "/logs/workout",
            json={
                "plan_id": str(PLAN_ID),
                "log_date": LOG_DATE,
                "exercise_id": "push_up",
                "sets": 3,
                "reps": 12,
                "completed": True,
            },
        )
        assert resp.status_code in (401, 403)
