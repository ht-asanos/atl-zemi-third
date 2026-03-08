"""API 結合テスト — GET /foods/staples"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.data.food_master import FOOD_MASTER
from app.dependencies.auth import get_current_user_id
from app.dependencies.supabase_client import get_authenticated_supabase
from app.main import app
from app.models.food import FoodCategory
from fastapi.testclient import TestClient

TEST_USER_ID = uuid4()

STAPLE_FOODS = [f for f in FOOD_MASTER if f.category == FoodCategory.STAPLE]


@pytest.fixture
def client():
    mock_supabase = AsyncMock()
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_authenticated_supabase] = lambda: mock_supabase
    yield TestClient(app, raise_server_exceptions=False), mock_supabase
    app.dependency_overrides.clear()


class TestGetStapleFoods:
    def test_success(self, client) -> None:
        test_client, _ = client
        with patch("app.routers.foods.food_repo") as mock_food:
            mock_food.get_staple_foods = AsyncMock(return_value=STAPLE_FOODS)
            resp = test_client.get("/foods/staples")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5
        assert all(item["category"] == "staple" for item in data)

    def test_empty(self, client) -> None:
        test_client, _ = client
        with patch("app.routers.foods.food_repo") as mock_food:
            mock_food.get_staple_foods = AsyncMock(return_value=[])
            resp = test_client.get("/foods/staples")
        assert resp.status_code == 200
        assert resp.json() == []
