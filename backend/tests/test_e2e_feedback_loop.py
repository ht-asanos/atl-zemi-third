"""E2E フローテスト — プラン → ログ → フィードバック → 適応"""

from datetime import date, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.dependencies.auth import get_current_user_id
from app.dependencies.supabase_client import get_authenticated_supabase
from app.main import app
from app.schemas.log import MealLogResponse, WorkoutLogResponse
from app.schemas.plan import DailyPlanResponse
from app.services.tag_extractor import ExtractionResult
from fastapi.testclient import TestClient

TEST_USER_ID = uuid4()
OTHER_USER_ID = uuid4()
PLAN_ID = uuid4()

PLAN_ROW = {
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


class TestE2EFeedbackLoop:
    def test_full_flow(self, client) -> None:
        """プラン作成 → ログ記録 → フィードバック → 適応 → リビジョン確認"""
        test_client, _ = client

        # 1. ログ記録 (meal)
        with patch("app.routers.logs.log_repo") as mock_log:
            mock_log.upsert_meal_log = AsyncMock(
                return_value=MealLogResponse(
                    id=uuid4(),
                    plan_id=PLAN_ID,
                    log_date=date(2026, 3, 9),
                    meal_type="breakfast",
                    completed=True,
                    satisfaction=3,
                    created_at=datetime(2026, 3, 9, 12, 0),
                )
            )
            resp = test_client.post(
                "/logs/meal",
                json={
                    "plan_id": str(PLAN_ID),
                    "log_date": "2026-03-09",
                    "meal_type": "breakfast",
                    "completed": True,
                    "satisfaction": 3,
                },
            )
        assert resp.status_code == 201

        # 2. ログ記録 (workout)
        with patch("app.routers.logs.log_repo") as mock_log:
            mock_log.upsert_workout_log = AsyncMock(
                return_value=WorkoutLogResponse(
                    id=uuid4(),
                    plan_id=PLAN_ID,
                    log_date=date(2026, 3, 9),
                    exercise_id="push_up",
                    sets=3,
                    reps=12,
                    rpe=8.0,
                    completed=True,
                    created_at=datetime(2026, 3, 9, 12, 0),
                )
            )
            resp = test_client.post(
                "/logs/workout",
                json={
                    "plan_id": str(PLAN_ID),
                    "log_date": "2026-03-09",
                    "exercise_id": "push_up",
                    "sets": 3,
                    "reps": 12,
                    "rpe": 8.0,
                    "completed": True,
                },
            )
        assert resp.status_code == 201

        # 3. フィードバック → 適応
        with (
            patch("app.routers.feedback.plan_repo") as mock_plan,
            patch("app.routers.feedback.tag_extractor") as mock_extractor,
            patch("app.routers.feedback.feedback_event_repo") as mock_event_repo,
            patch("app.routers.feedback.feedback_repo") as mock_fb,
            patch("app.routers.feedback.food_repo") as mock_food,
        ):
            mock_plan.get_daily_plan_row_by_user = AsyncMock(return_value=PLAN_ROW)
            mock_extractor.extract_tags = AsyncMock(return_value=ExtractionResult(tags=["too_hard"], status="success"))
            mock_event_repo.create_feedback_event = AsyncMock(return_value=uuid4())
            mock_event_repo.create_feedback_event_tags = AsyncMock(return_value=[uuid4()])
            mock_event_repo.create_adaptation_events = AsyncMock(return_value=[uuid4()])
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
        assert "too_hard" in data["tags_applied"]
        assert data["extraction_status"] == "success"

        # plan_revision が作成されたことを確認
        mock_fb.create_plan_revision.assert_called_once()

    def test_upsert_meal_log_idempotent(self, client) -> None:
        """同日ログ再送信がupsert動作であることを確認"""
        test_client, _ = client
        with patch("app.routers.logs.log_repo") as mock_log:
            mock_log.upsert_meal_log = AsyncMock(
                return_value=MealLogResponse(
                    id=uuid4(),
                    plan_id=PLAN_ID,
                    log_date=date(2026, 3, 9),
                    meal_type="breakfast",
                    completed=True,
                    satisfaction=3,
                    created_at=datetime(2026, 3, 9, 12, 0),
                )
            )
            for _ in range(3):
                resp = test_client.post(
                    "/logs/meal",
                    json={
                        "plan_id": str(PLAN_ID),
                        "log_date": "2026-03-09",
                        "meal_type": "breakfast",
                        "completed": True,
                        "satisfaction": 3,
                    },
                )
                assert resp.status_code == 201

    def test_other_user_plan_feedback_404(self, client) -> None:
        """他ユーザーのplan_idでフィードバック → 404"""
        test_client, _ = client
        with patch("app.routers.feedback.plan_repo") as mock_plan:
            # get_daily_plan_row_by_user は user_id スコープなので None を返す
            mock_plan.get_daily_plan_row_by_user = AsyncMock(return_value=None)
            resp = test_client.post(
                "/feedback",
                json={"plan_id": str(uuid4()), "source_text": "テスト"},
            )
        assert resp.status_code == 404
