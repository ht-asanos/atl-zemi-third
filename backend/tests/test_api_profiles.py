"""API 結合テスト — POST /profiles"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.config import settings
from app.dependencies.auth import get_current_user_id
from app.dependencies.supabase_client import get_authenticated_supabase
from app.main import app
from app.models.nutrition import ActivityLevel, Gender
from app.schemas.profile import ProfileResponse
from fastapi.testclient import TestClient

TEST_USER_ID = uuid4()


@pytest.fixture
def client():
    mock_supabase = AsyncMock()

    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_authenticated_supabase] = lambda: mock_supabase
    yield TestClient(app, raise_server_exceptions=False), mock_supabase
    app.dependency_overrides.clear()


class TestCreateProfile:
    def test_success(self, client) -> None:
        test_client, mock_sb = client
        with patch("app.routers.profiles.profile_repo") as mock_repo:
            mock_repo.get_profile = AsyncMock(return_value=None)
            mock_repo.create_profile = AsyncMock(
                return_value=ProfileResponse(
                    id=TEST_USER_ID,
                    age=25,
                    gender=Gender.MALE,
                    height_cm=170.0,
                    weight_kg=70.0,
                    activity_level=ActivityLevel.MODERATE,
                )
            )
            resp = test_client.post(
                "/profiles",
                json={
                    "age": 25,
                    "gender": "male",
                    "height_cm": 170.0,
                    "weight_kg": 70.0,
                    "activity_level": "moderate",
                },
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["age"] == 25
        assert data["id"] == str(TEST_USER_ID)

    def test_duplicate_409(self, client) -> None:
        test_client, mock_sb = client
        with patch("app.routers.profiles.profile_repo") as mock_repo:
            mock_repo.get_profile = AsyncMock(
                return_value=ProfileResponse(
                    id=TEST_USER_ID,
                    age=25,
                    gender=Gender.MALE,
                    height_cm=170.0,
                    weight_kg=70.0,
                    activity_level=ActivityLevel.MODERATE,
                )
            )
            resp = test_client.post(
                "/profiles",
                json={
                    "age": 25,
                    "gender": "male",
                    "height_cm": 170.0,
                    "weight_kg": 70.0,
                    "activity_level": "moderate",
                },
            )
        assert resp.status_code == 409

    def test_invalid_body_422(self, client) -> None:
        test_client, _ = client
        resp = test_client.post("/profiles", json={"age": 5})
        assert resp.status_code == 422

    def test_no_auth_returns_401_or_403(self) -> None:
        """Without auth override, HTTPBearer returns 401 or 403"""
        app.dependency_overrides.clear()
        test_client = TestClient(app, raise_server_exceptions=False)
        resp = test_client.post(
            "/profiles",
            json={
                "age": 25,
                "gender": "male",
                "height_cm": 170.0,
                "weight_kg": 70.0,
                "activity_level": "moderate",
            },
        )
        assert resp.status_code in (401, 403)


class TestGetMyProfile:
    def test_success(self, client) -> None:
        test_client, _ = client
        with patch("app.routers.profiles.profile_repo") as mock_repo:
            mock_repo.get_profile = AsyncMock(
                return_value=ProfileResponse(
                    id=TEST_USER_ID,
                    age=25,
                    gender=Gender.MALE,
                    height_cm=170.0,
                    weight_kg=70.0,
                    activity_level=ActivityLevel.MODERATE,
                )
            )
            resp = test_client.get("/profiles/me")
        assert resp.status_code == 200
        assert resp.json()["age"] == 25

    def test_not_found(self, client) -> None:
        test_client, _ = client
        with patch("app.routers.profiles.profile_repo") as mock_repo:
            mock_repo.get_profile = AsyncMock(return_value=None)
            resp = test_client.get("/profiles/me")
        assert resp.status_code == 404


class TestGetMyAdminStatus:
    def test_returns_true_for_admin(self, client) -> None:
        test_client, _ = client
        with patch.object(settings, "admin_user_ids", str(TEST_USER_ID)):
            resp = test_client.get("/profiles/me/admin-status")
        assert resp.status_code == 200
        assert resp.json() == {"is_admin": True}

    def test_returns_false_for_non_admin(self, client) -> None:
        test_client, _ = client
        with patch.object(settings, "admin_user_ids", str(uuid4())):
            resp = test_client.get("/profiles/me/admin-status")
        assert resp.status_code == 200
        assert resp.json() == {"is_admin": False}


class TestUpdateMyProfile:
    def _existing_profile(self):
        return ProfileResponse(
            id=TEST_USER_ID,
            age=25,
            gender=Gender.MALE,
            height_cm=170.0,
            weight_kg=70.0,
            activity_level=ActivityLevel.MODERATE,
        )

    def test_success(self, client) -> None:
        test_client, _ = client
        updated = ProfileResponse(
            id=TEST_USER_ID,
            age=26,
            gender=Gender.MALE,
            height_cm=170.0,
            weight_kg=65.0,
            activity_level=ActivityLevel.MODERATE,
        )
        with patch("app.routers.profiles.profile_repo") as mock_repo:
            mock_repo.get_profile = AsyncMock(return_value=self._existing_profile())
            mock_repo.update_profile = AsyncMock(return_value=updated)
            resp = test_client.put(
                "/profiles/me",
                json={
                    "age": 26,
                    "gender": "male",
                    "height_cm": 170.0,
                    "weight_kg": 65.0,
                    "activity_level": "moderate",
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["profile"]["weight_kg"] == 65.0
        assert data["goal_recalculation_needed"] is True

    def test_not_found(self, client) -> None:
        test_client, _ = client
        with patch("app.routers.profiles.profile_repo") as mock_repo:
            mock_repo.get_profile = AsyncMock(return_value=None)
            resp = test_client.put(
                "/profiles/me",
                json={
                    "age": 25,
                    "gender": "male",
                    "height_cm": 170.0,
                    "weight_kg": 70.0,
                    "activity_level": "moderate",
                },
            )
        assert resp.status_code == 404

    def test_no_recalc_when_no_change(self, client) -> None:
        test_client, _ = client
        existing = self._existing_profile()
        with patch("app.routers.profiles.profile_repo") as mock_repo:
            mock_repo.get_profile = AsyncMock(return_value=existing)
            mock_repo.update_profile = AsyncMock(return_value=existing)
            resp = test_client.put(
                "/profiles/me",
                json={
                    "age": 30,
                    "gender": "male",
                    "height_cm": 170.0,
                    "weight_kg": 70.0,
                    "activity_level": "moderate",
                },
            )
        assert resp.status_code == 200
        assert resp.json()["goal_recalculation_needed"] is False
