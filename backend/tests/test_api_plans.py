"""API 結合テスト — POST /plans/weekly, PATCH /plans/{id}/meal"""

from datetime import date
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.data.food_master import FOOD_MASTER
from app.dependencies.auth import get_current_user_id
from app.dependencies.supabase_client import get_authenticated_supabase
from app.main import app
from app.models.food import FoodCategory
from app.models.nutrition import Goal
from app.schemas.goal import GoalResponse
from app.schemas.plan import DailyPlanResponse
from fastapi.testclient import TestClient

TEST_USER_ID = uuid4()
GOAL_ID = uuid4()
PLAN_ID = uuid4()

STAPLE_FOODS = [f for f in FOOD_MASTER if f.category == FoodCategory.STAPLE]
PROTEIN_FOODS = [f for f in FOOD_MASTER if f.category == FoodCategory.PROTEIN]
BULK_FOODS = [f for f in FOOD_MASTER if f.category == FoodCategory.BULK]

MOCK_GOAL = GoalResponse(
    id=GOAL_ID,
    goal_type=Goal.DIET,
    target_kcal=2282.5,
    protein_g=140.0,
    fat_g=56.0,
    carbs_g=388.1,
)


@pytest.fixture
def client():
    mock_supabase = AsyncMock()
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_authenticated_supabase] = lambda: mock_supabase
    yield TestClient(app, raise_server_exceptions=False), mock_supabase
    app.dependency_overrides.clear()


def _make_daily_plans_response(start_date: str = "2026-03-09"):
    from datetime import date, timedelta

    sd = date.fromisoformat(start_date)
    return [
        DailyPlanResponse(
            id=uuid4(),
            plan_date=sd + timedelta(days=i),
            meal_plan=[],
            workout_plan={},
            plan_meta={"mode": "recipe", "staple_name": None},
        )
        for i in range(7)
    ]


class TestCreateWeeklyPlanClassic:
    def test_success(self, client) -> None:
        test_client, _ = client
        with (
            patch("app.routers.plans.goal_repo") as mock_goal,
            patch("app.routers.plans.food_repo") as mock_food,
            patch("app.routers.plans.plan_repo") as mock_plan,
            patch("app.routers.plans.build_next_week_training_adjustment") as mock_training_adj,
        ):
            mock_goal.get_latest_goal = AsyncMock(return_value=MOCK_GOAL)
            mock_food.get_food_by_name = AsyncMock(return_value=STAPLE_FOODS[0])
            mock_food.get_protein_foods = AsyncMock(return_value=PROTEIN_FOODS)
            mock_food.get_bulk_foods = AsyncMock(return_value=BULK_FOODS)
            mock_plan.upsert_weekly_plans = AsyncMock(return_value=None)
            mock_plan.get_weekly_plans = AsyncMock(return_value=_make_daily_plans_response())
            mock_training_adj.return_value = type("Adj", (), {"scale": 1.0, "protect_forearms": False})()

            resp = test_client.post(
                "/plans/weekly",
                json={"start_date": "2026-03-09", "staple_name": "冷凍うどん", "mode": "classic"},
            )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["plans"]) == 7

        # upsert が 1 回呼ばれ、引数が list[dict] であること
        mock_plan.upsert_weekly_plans.assert_called_once()
        call_plans = mock_plan.upsert_weekly_plans.call_args[0][1]
        assert isinstance(call_plans, list)
        assert len(call_plans) == 7
        assert all(isinstance(p, dict) for p in call_plans)
        # plan_meta が含まれること
        assert call_plans[0]["plan_meta"] == {"mode": "classic", "staple_name": "冷凍うどん"}
        mock_training_adj.assert_called_once()

    def test_goal_not_found(self, client) -> None:
        test_client, _ = client
        with patch("app.routers.plans.goal_repo") as mock_goal:
            mock_goal.get_latest_goal = AsyncMock(return_value=None)
            resp = test_client.post(
                "/plans/weekly",
                json={"start_date": "2026-03-09", "staple_name": "冷凍うどん", "mode": "classic"},
            )
        assert resp.status_code == 404

    def test_staple_not_found(self, client) -> None:
        test_client, _ = client
        with (
            patch("app.routers.plans.goal_repo") as mock_goal,
            patch("app.routers.plans.food_repo") as mock_food,
        ):
            mock_goal.get_latest_goal = AsyncMock(return_value=MOCK_GOAL)
            mock_food.get_food_by_name = AsyncMock(return_value=None)
            resp = test_client.post(
                "/plans/weekly",
                json={"start_date": "2026-03-09", "staple_name": "存在しない食材", "mode": "classic"},
            )
        assert resp.status_code == 404

    def test_staple_wrong_category_422(self, client) -> None:
        test_client, _ = client
        with (
            patch("app.routers.plans.goal_repo") as mock_goal,
            patch("app.routers.plans.food_repo") as mock_food,
        ):
            mock_goal.get_latest_goal = AsyncMock(return_value=MOCK_GOAL)
            mock_food.get_food_by_name = AsyncMock(return_value=PROTEIN_FOODS[0])
            resp = test_client.post(
                "/plans/weekly",
                json={"start_date": "2026-03-09", "staple_name": "卵", "mode": "classic"},
            )
        assert resp.status_code == 422

    def test_regenerate_upserts(self, client) -> None:
        """Same week re-generation should succeed (upsert)"""
        test_client, _ = client
        with (
            patch("app.routers.plans.goal_repo") as mock_goal,
            patch("app.routers.plans.food_repo") as mock_food,
            patch("app.routers.plans.plan_repo") as mock_plan,
        ):
            mock_goal.get_latest_goal = AsyncMock(return_value=MOCK_GOAL)
            mock_food.get_food_by_name = AsyncMock(return_value=STAPLE_FOODS[0])
            mock_food.get_protein_foods = AsyncMock(return_value=PROTEIN_FOODS)
            mock_food.get_bulk_foods = AsyncMock(return_value=BULK_FOODS)
            mock_plan.upsert_weekly_plans = AsyncMock(return_value=None)
            mock_plan.get_weekly_plans = AsyncMock(return_value=_make_daily_plans_response())

            resp1 = test_client.post(
                "/plans/weekly",
                json={"start_date": "2026-03-09", "staple_name": "冷凍うどん", "mode": "classic"},
            )
            resp2 = test_client.post(
                "/plans/weekly",
                json={"start_date": "2026-03-09", "staple_name": "冷凍うどん", "mode": "classic"},
            )
        assert resp1.status_code == 201
        assert resp2.status_code == 201

    def test_classic_mode_without_staple_name_422(self, client) -> None:
        test_client, _ = client
        with patch("app.routers.plans.goal_repo") as mock_goal:
            mock_goal.get_latest_goal = AsyncMock(return_value=MOCK_GOAL)
            resp = test_client.post(
                "/plans/weekly",
                json={"start_date": "2026-03-09", "mode": "classic"},
            )
        assert resp.status_code == 422


class TestCreateWeeklyPlanRecipe:
    def test_recipe_mode_success(self, client) -> None:
        test_client, _ = client
        with (
            patch("app.routers.plans.goal_repo") as mock_goal,
            patch("app.routers.plans.plan_repo") as mock_plan,
            patch("app.routers.plans.generate_weekly_plan_v3") as mock_v3,
            patch("app.routers.plans.favorite_repo") as mock_fav,
            patch("app.routers.plans.build_next_week_training_adjustment") as mock_training_adj,
        ):
            mock_goal.get_latest_goal = AsyncMock(return_value=MOCK_GOAL)
            mock_plan.upsert_weekly_plans = AsyncMock(return_value=None)
            mock_plan.get_weekly_plans = AsyncMock(return_value=_make_daily_plans_response())
            mock_fav.get_favorite_recipe_ids = AsyncMock(return_value=set())
            mock_training_adj.return_value = type("Adj", (), {"scale": 1.0, "protect_forearms": False})()

            # generate_weekly_plan_v3 をモック（実際の DB アクセスを回避）
            from datetime import timedelta

            from app.services.meal_suggestion import generate_structured_daily_meals
            from app.services.weekly_planner import DailyPlanData

            start = date(2026, 3, 9)
            mock_v3.return_value = [
                DailyPlanData(
                    plan_date=start + timedelta(days=i),
                    meals=generate_structured_daily_meals(recipe=None),
                    training_day=None,
                )
                for i in range(7)
            ]

            resp = test_client.post(
                "/plans/weekly",
                json={"start_date": "2026-03-09", "mode": "recipe"},
            )
        assert resp.status_code == 201
        assert len(resp.json()["plans"]) == 7
        mock_training_adj.assert_called_once()
        _, kwargs = mock_v3.call_args
        assert kwargs["training_scale"] == 1.0
        assert kwargs["protect_forearms"] is False

    def test_default_mode_is_recipe(self, client) -> None:
        """mode 未指定時のデフォルトは recipe"""
        test_client, _ = client
        with (
            patch("app.routers.plans.goal_repo") as mock_goal,
            patch("app.routers.plans.plan_repo") as mock_plan,
            patch("app.routers.plans.generate_weekly_plan_v3") as mock_v3,
            patch("app.routers.plans.favorite_repo") as mock_fav,
            patch("app.routers.plans.build_next_week_training_adjustment") as mock_training_adj,
        ):
            mock_goal.get_latest_goal = AsyncMock(return_value=MOCK_GOAL)
            mock_plan.upsert_weekly_plans = AsyncMock(return_value=None)
            mock_plan.get_weekly_plans = AsyncMock(return_value=_make_daily_plans_response())
            mock_fav.get_favorite_recipe_ids = AsyncMock(return_value=set())
            mock_training_adj.return_value = type("Adj", (), {"scale": 1.0, "protect_forearms": False})()

            from datetime import timedelta

            from app.services.meal_suggestion import generate_structured_daily_meals
            from app.services.weekly_planner import DailyPlanData

            start = date(2026, 3, 9)
            mock_v3.return_value = [
                DailyPlanData(
                    plan_date=start + timedelta(days=i),
                    meals=generate_structured_daily_meals(recipe=None),
                    training_day=None,
                )
                for i in range(7)
            ]

            resp = test_client.post(
                "/plans/weekly",
                json={"start_date": "2026-03-09"},
            )
        assert resp.status_code == 201
        # generate_weekly_plan_v3 が呼ばれたことを確認
        mock_v3.assert_called_once()


class TestPatchMeal:
    def test_success(self, client) -> None:
        test_client, _ = client
        with (
            patch("app.routers.plans.plan_repo") as mock_plan,
            patch("app.routers.plans.goal_repo") as mock_goal,
            patch("app.routers.plans.food_repo") as mock_food,
        ):
            mock_plan.get_daily_plan_by_user = AsyncMock(
                return_value=DailyPlanResponse(
                    id=PLAN_ID,
                    plan_date=date(2026, 3, 9),
                    meal_plan=[],
                    workout_plan={},
                )
            )
            mock_goal.get_latest_goal = AsyncMock(return_value=MOCK_GOAL)
            mock_food.get_food_by_name = AsyncMock(return_value=STAPLE_FOODS[1])
            mock_food.get_protein_foods = AsyncMock(return_value=PROTEIN_FOODS)
            mock_food.get_bulk_foods = AsyncMock(return_value=BULK_FOODS)
            mock_plan.update_meal_plan = AsyncMock(return_value=None)
            mock_plan.get_daily_plan = AsyncMock(
                return_value=DailyPlanResponse(
                    id=PLAN_ID,
                    plan_date=date(2026, 3, 9),
                    meal_plan=[],
                    workout_plan={},
                )
            )

            resp = test_client.patch(
                f"/plans/{PLAN_ID}/meal",
                json={"staple_name": "白米"},
            )
        assert resp.status_code == 200

        # update_meal_plan が 1 回呼ばれ、meal_plan 引数が list であること
        mock_plan.update_meal_plan.assert_called_once()
        call_meal_plan = mock_plan.update_meal_plan.call_args[0][2]
        assert isinstance(call_meal_plan, list)

    def test_plan_not_found(self, client) -> None:
        test_client, _ = client
        with patch("app.routers.plans.plan_repo") as mock_plan:
            mock_plan.get_daily_plan_by_user = AsyncMock(return_value=None)
            resp = test_client.patch(
                f"/plans/{PLAN_ID}/meal",
                json={"staple_name": "白米"},
            )
        assert resp.status_code == 404


class TestGetWeeklyPlan:
    def test_success(self, client) -> None:
        test_client, _ = client
        with patch("app.routers.plans.plan_repo") as mock_plan:
            mock_plan.get_weekly_plans = AsyncMock(return_value=_make_daily_plans_response())
            resp = test_client.get("/plans/weekly?start_date=2026-03-09")
        assert resp.status_code == 200
        assert len(resp.json()["plans"]) == 7

    def test_empty_returns_empty_list(self, client) -> None:
        test_client, _ = client
        with patch("app.routers.plans.plan_repo") as mock_plan:
            mock_plan.get_weekly_plans = AsyncMock(return_value=[])
            resp = test_client.get("/plans/weekly?start_date=2026-03-09")
        assert resp.status_code == 200
        assert resp.json()["plans"] == []

    def test_missing_start_date_422(self, client) -> None:
        test_client, _ = client
        resp = test_client.get("/plans/weekly")
        assert resp.status_code == 422
