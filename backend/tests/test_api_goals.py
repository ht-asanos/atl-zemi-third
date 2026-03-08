"""API 結合テスト — POST /goals"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.dependencies.auth import get_current_user_id
from app.dependencies.supabase_client import get_authenticated_supabase
from app.main import app
from app.models.nutrition import ActivityLevel, Gender, Goal
from app.schemas.goal import GoalResponse
from app.schemas.profile import ProfileResponse
from fastapi.testclient import TestClient

TEST_USER_ID = uuid4()
GOAL_ID = uuid4()


@pytest.fixture
def client():
    mock_supabase = AsyncMock()
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_authenticated_supabase] = lambda: mock_supabase
    yield TestClient(app, raise_server_exceptions=False), mock_supabase
    app.dependency_overrides.clear()


MOCK_PROFILE = ProfileResponse(
    id=TEST_USER_ID,
    age=25,
    gender=Gender.MALE,
    height_cm=170.0,
    weight_kg=70.0,
    activity_level=ActivityLevel.MODERATE,
)


class TestCreateGoal:
    def test_success_diet(self, client) -> None:
        test_client, _ = client
        with (
            patch("app.routers.goals.profile_repo") as mock_prof,
            patch("app.routers.goals.goal_repo") as mock_goal,
        ):
            mock_prof.get_profile = AsyncMock(return_value=MOCK_PROFILE)
            mock_goal.upsert_goal = AsyncMock(
                return_value=GoalResponse(
                    id=GOAL_ID,
                    goal_type=Goal.DIET,
                    target_kcal=2282.5,
                    protein_g=140.0,
                    fat_g=56.0,
                    carbs_g=388.1,
                )
            )
            resp = test_client.post("/goals", json={"goal_type": "diet"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["goal_type"] == "diet"
        assert data["protein_g"] > 0

    def test_success_strength(self, client) -> None:
        test_client, _ = client
        with (
            patch("app.routers.goals.profile_repo") as mock_prof,
            patch("app.routers.goals.goal_repo") as mock_goal,
        ):
            mock_prof.get_profile = AsyncMock(return_value=MOCK_PROFILE)
            mock_goal.upsert_goal = AsyncMock(
                return_value=GoalResponse(
                    id=GOAL_ID,
                    goal_type=Goal.STRENGTH,
                    target_kcal=2932.5,
                    protein_g=140.0,
                    fat_g=56.0,
                    carbs_g=550.6,
                )
            )
            resp = test_client.post("/goals", json={"goal_type": "strength"})
        assert resp.status_code == 201

    def test_success_bouldering(self, client) -> None:
        test_client, _ = client
        with (
            patch("app.routers.goals.profile_repo") as mock_prof,
            patch("app.routers.goals.goal_repo") as mock_goal,
        ):
            mock_prof.get_profile = AsyncMock(return_value=MOCK_PROFILE)
            mock_goal.upsert_goal = AsyncMock(
                return_value=GoalResponse(
                    id=GOAL_ID,
                    goal_type=Goal.BOULDERING,
                    target_kcal=2757.5,
                    protein_g=140.0,
                    fat_g=56.0,
                    carbs_g=506.9,
                )
            )
            resp = test_client.post("/goals", json={"goal_type": "bouldering"})
        assert resp.status_code == 201

    def test_profile_not_found(self, client) -> None:
        test_client, _ = client
        with patch("app.routers.goals.profile_repo") as mock_prof:
            mock_prof.get_profile = AsyncMock(return_value=None)
            resp = test_client.post("/goals", json={"goal_type": "diet"})
        assert resp.status_code == 404

    def test_upsert_overwrites(self, client) -> None:
        """Same goal_type should upsert (not 409)"""
        test_client, _ = client
        with (
            patch("app.routers.goals.profile_repo") as mock_prof,
            patch("app.routers.goals.goal_repo") as mock_goal,
        ):
            mock_prof.get_profile = AsyncMock(return_value=MOCK_PROFILE)
            mock_goal.upsert_goal = AsyncMock(
                return_value=GoalResponse(
                    id=GOAL_ID,
                    goal_type=Goal.DIET,
                    target_kcal=2282.5,
                    protein_g=140.0,
                    fat_g=56.0,
                    carbs_g=388.1,
                )
            )
            resp1 = test_client.post("/goals", json={"goal_type": "diet"})
            resp2 = test_client.post("/goals", json={"goal_type": "diet"})
        assert resp1.status_code == 201
        assert resp2.status_code == 201


class TestGetMyGoal:
    def test_success(self, client) -> None:
        test_client, _ = client
        with patch("app.routers.goals.goal_repo") as mock_goal:
            mock_goal.get_latest_goal = AsyncMock(
                return_value=GoalResponse(
                    id=GOAL_ID,
                    goal_type=Goal.DIET,
                    target_kcal=2282.5,
                    protein_g=140.0,
                    fat_g=56.0,
                    carbs_g=388.1,
                )
            )
            resp = test_client.get("/goals/me")
        assert resp.status_code == 200
        assert resp.json()["goal_type"] == "diet"

    def test_not_found(self, client) -> None:
        test_client, _ = client
        with patch("app.routers.goals.goal_repo") as mock_goal:
            mock_goal.get_latest_goal = AsyncMock(return_value=None)
            resp = test_client.get("/goals/me")
        assert resp.status_code == 404
