"""API テスト — POST /feedback, GET /feedback/{plan_id}"""

from datetime import date, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.dependencies.auth import get_current_user_id
from app.dependencies.supabase_client import get_authenticated_supabase
from app.main import app
from app.schemas.feedback import FeedbackTagResponse
from app.schemas.plan import DailyPlanResponse
from app.services.tag_extractor import ExtractionResult
from fastapi.testclient import TestClient

TEST_USER_ID = uuid4()
OTHER_USER_ID = uuid4()
PLAN_ID = uuid4()

MOCK_PLAN_ROW = {
    "id": str(PLAN_ID),
    "user_id": str(TEST_USER_ID),
    "plan_date": "2026-03-09",
    "meal_plan": [
        {
            "staple": {
                "name": "冷凍うどん",
                "category": "staple",
                "kcal_per_serving": 210,
                "protein_g": 5.2,
                "fat_g": 0.8,
                "carbs_g": 44.0,
                "serving_unit": "1玉",
                "price_yen": 40,
                "cooking_minutes": 3,
            },
            "protein_sources": [
                {
                    "name": "卵",
                    "category": "protein",
                    "kcal_per_serving": 91,
                    "protein_g": 7.4,
                    "fat_g": 6.2,
                    "carbs_g": 0.2,
                    "serving_unit": "1個",
                    "price_yen": 25,
                    "cooking_minutes": 3,
                }
            ],
            "bulk_items": [
                {
                    "name": "きのこミックス",
                    "category": "bulk",
                    "kcal_per_serving": 18,
                    "protein_g": 2.7,
                    "fat_g": 0.2,
                    "carbs_g": 3.1,
                    "serving_unit": "100g",
                    "price_yen": 80,
                    "cooking_minutes": 2,
                }
            ],
        }
    ],
    "workout_plan": {
        "day_label": "全身A",
        "exercises": [
            {
                "id": "push_up",
                "name_ja": "プッシュアップ",
                "muscle_group": "chest",
                "sets": 3,
                "reps": 12,
                "rest_seconds": 60,
            },
        ],
    },
    "updated_at": "2026-03-09T00:00:00+00:00",
}


@pytest.fixture
def client():
    mock_supabase = AsyncMock()
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_authenticated_supabase] = lambda: mock_supabase
    yield TestClient(app, raise_server_exceptions=False), mock_supabase
    app.dependency_overrides.clear()


@pytest.fixture
def no_auth_client():
    app.dependency_overrides.clear()
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


class TestCreateFeedback:
    def test_success_with_tags(self, client) -> None:
        test_client, _ = client
        with (
            patch("app.routers.feedback.plan_repo") as mock_plan,
            patch("app.routers.feedback.tag_extractor") as mock_extractor,
            patch("app.routers.feedback.feedback_repo") as mock_fb,
            patch("app.routers.feedback.food_repo") as mock_food,
        ):
            mock_plan.get_daily_plan_row_by_user = AsyncMock(return_value=MOCK_PLAN_ROW)
            mock_extractor.extract_tags = AsyncMock(return_value=ExtractionResult(tags=["too_hard"], status="success"))
            mock_fb.create_feedback_tags = AsyncMock(return_value=[])
            mock_plan.update_daily_plan = AsyncMock(return_value=None)
            mock_fb.create_plan_revision = AsyncMock(return_value=uuid4())
            mock_plan.get_daily_plan_by_user = AsyncMock(
                return_value=DailyPlanResponse(id=PLAN_ID, plan_date=date(2026, 3, 9), meal_plan=[], workout_plan={})
            )
            from app.data.food_master import FOOD_MASTER
            from app.models.food import FoodCategory

            mock_food.get_staple_foods = AsyncMock(
                return_value=[f for f in FOOD_MASTER if f.category == FoodCategory.STAPLE]
            )

            resp = test_client.post(
                "/feedback",
                json={"plan_id": str(PLAN_ID), "source_text": "トレーニングがきつすぎた"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["extraction_status"] == "success"
        assert "too_hard" in data["tags_applied"]

    def test_no_tags_no_adaptation(self, client) -> None:
        test_client, _ = client
        with (
            patch("app.routers.feedback.plan_repo") as mock_plan,
            patch("app.routers.feedback.tag_extractor") as mock_extractor,
            patch("app.routers.feedback.feedback_repo") as mock_fb,
        ):
            mock_plan.get_daily_plan_row_by_user = AsyncMock(return_value=MOCK_PLAN_ROW)
            mock_extractor.extract_tags = AsyncMock(return_value=ExtractionResult(tags=[], status="success"))
            mock_fb.create_feedback_tags = AsyncMock(return_value=[])

            resp = test_client.post(
                "/feedback",
                json={"plan_id": str(PLAN_ID), "source_text": "特に問題なし"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["extraction_status"] == "success"
        assert data["tags_applied"] == []
        assert data["new_plan"] is None

    def test_extraction_failed(self, client) -> None:
        test_client, _ = client
        with (
            patch("app.routers.feedback.plan_repo") as mock_plan,
            patch("app.routers.feedback.tag_extractor") as mock_extractor,
            patch("app.routers.feedback.feedback_repo") as mock_fb,
        ):
            mock_plan.get_daily_plan_row_by_user = AsyncMock(return_value=MOCK_PLAN_ROW)
            mock_extractor.extract_tags = AsyncMock(return_value=ExtractionResult(tags=[], status="failed"))
            mock_fb.create_feedback_tags = AsyncMock(return_value=[])

            resp = test_client.post(
                "/feedback",
                json={"plan_id": str(PLAN_ID), "source_text": "テスト"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["extraction_status"] == "failed"
        assert data["tags_applied"] == []
        # テキストは保存済み (create_feedback_tags が呼ばれている)
        mock_fb.create_feedback_tags.assert_called_once()

    def test_plan_not_found_404(self, client) -> None:
        test_client, _ = client
        with patch("app.routers.feedback.plan_repo") as mock_plan:
            mock_plan.get_daily_plan_row_by_user = AsyncMock(return_value=None)
            resp = test_client.post(
                "/feedback",
                json={"plan_id": str(uuid4()), "source_text": "テスト"},
            )
        assert resp.status_code == 404

    def test_other_user_plan_404(self, client) -> None:
        """他ユーザーの plan_id → 404"""
        test_client, _ = client
        with patch("app.routers.feedback.plan_repo") as mock_plan:
            mock_plan.get_daily_plan_row_by_user = AsyncMock(return_value=None)
            resp = test_client.post(
                "/feedback",
                json={"plan_id": str(uuid4()), "source_text": "テスト"},
            )
        assert resp.status_code == 404

    def test_optimistic_lock_conflict_409(self, client) -> None:
        test_client, _ = client
        with (
            patch("app.routers.feedback.plan_repo") as mock_plan,
            patch("app.routers.feedback.tag_extractor") as mock_extractor,
            patch("app.routers.feedback.feedback_repo") as mock_fb,
            patch("app.routers.feedback.food_repo") as mock_food,
        ):
            mock_plan.get_daily_plan_row_by_user = AsyncMock(return_value=MOCK_PLAN_ROW)
            mock_extractor.extract_tags = AsyncMock(return_value=ExtractionResult(tags=["too_hard"], status="success"))
            mock_fb.create_feedback_tags = AsyncMock(return_value=[])
            mock_plan.update_daily_plan = AsyncMock(side_effect=Exception("40001: Conflict: plan was modified"))
            from app.data.food_master import FOOD_MASTER
            from app.models.food import FoodCategory

            mock_food.get_staple_foods = AsyncMock(
                return_value=[f for f in FOOD_MASTER if f.category == FoodCategory.STAPLE]
            )

            resp = test_client.post(
                "/feedback",
                json={"plan_id": str(PLAN_ID), "source_text": "きつすぎ"},
            )
        assert resp.status_code == 409

    def test_no_token_401(self, no_auth_client) -> None:
        resp = no_auth_client.post(
            "/feedback",
            json={"plan_id": str(PLAN_ID), "source_text": "テスト"},
        )
        assert resp.status_code in (401, 403)


class TestGetFeedbackTags:
    def test_success(self, client) -> None:
        test_client, _ = client
        with (
            patch("app.routers.feedback.plan_repo") as mock_plan,
            patch("app.routers.feedback.feedback_repo") as mock_fb,
        ):
            mock_plan.get_daily_plan_by_user = AsyncMock(
                return_value=DailyPlanResponse(id=PLAN_ID, plan_date=date(2026, 3, 9), meal_plan=[], workout_plan={})
            )
            mock_fb.get_feedback_tags_by_plan = AsyncMock(
                return_value=[
                    FeedbackTagResponse(
                        id=uuid4(),
                        tag="too_hard",
                        source_text="きつい",
                        created_at=datetime(2026, 3, 9, 12, 0),
                    )
                ]
            )
            resp = test_client.get(f"/feedback/{PLAN_ID}")
        assert resp.status_code == 200
        assert len(resp.json()["tags"]) == 1

    def test_plan_not_found_404(self, client) -> None:
        test_client, _ = client
        with patch("app.routers.feedback.plan_repo") as mock_plan:
            mock_plan.get_daily_plan_by_user = AsyncMock(return_value=None)
            resp = test_client.get(f"/feedback/{uuid4()}")
        assert resp.status_code == 404
