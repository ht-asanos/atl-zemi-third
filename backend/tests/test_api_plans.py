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
            plan_meta={
                "mode": "recipe",
                "staple_name": None,
                "recipe_filters": {
                    "allowed_sources": ["rakuten", "youtube"],
                    "prefer_favorites": True,
                    "exclude_disliked": True,
                    "prefer_variety": True,
                },
            },
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
        assert call_plans[0]["plan_meta"]["mode"] == "classic"
        assert call_plans[0]["plan_meta"]["staple_name"] == "冷凍うどん"
        assert call_plans[0]["plan_meta"]["recipe_filters"] == {
            "allowed_sources": ["rakuten", "youtube"],
            "prefer_favorites": True,
            "exclude_disliked": True,
            "prefer_variety": True,
        }
        assert call_plans[0]["plan_meta"]["available_equipment"] == ["none"]
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
            patch("app.routers.plans.generate_weekly_plan_v3_validated") as mock_v3,
            patch("app.routers.plans.favorite_repo") as mock_fav,
            patch("app.routers.plans.rating_repo") as mock_rating,
            patch("app.routers.plans.build_next_week_training_adjustment") as mock_training_adj,
        ):
            mock_goal.get_latest_goal = AsyncMock(return_value=MOCK_GOAL)
            mock_plan.upsert_weekly_plans = AsyncMock(return_value=None)
            mock_plan.get_weekly_plans = AsyncMock(return_value=_make_daily_plans_response())
            mock_plan.get_past_recipe_ids = AsyncMock(return_value=[])
            mock_fav.get_favorite_recipe_ids = AsyncMock(return_value=set())
            mock_rating.get_liked_recipe_ids = AsyncMock(return_value=set())
            mock_rating.get_disliked_recipe_ids = AsyncMock(return_value=set())
            mock_training_adj.return_value = type("Adj", (), {"scale": 1.0, "protect_forearms": False})()

            # generate_weekly_plan_v3_validated をモック（実際の DB アクセスを回避）
            from datetime import timedelta

            from app.services.meal_suggestion import generate_structured_daily_meals
            from app.services.plan_validator import ValidationResult
            from app.services.weekly_planner import DailyPlanData

            start = date(2026, 3, 9)
            mock_plans = [
                DailyPlanData(
                    plan_date=start + timedelta(days=i),
                    meals=generate_structured_daily_meals(recipe=None),
                    training_day=None,
                )
                for i in range(7)
            ]
            mock_v3.return_value = (mock_plans, ValidationResult())

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
        assert kwargs["allowed_sources"] == ["rakuten", "youtube"]
        assert kwargs["prefer_favorites"] is True
        assert kwargs["exclude_disliked"] is True
        assert kwargs["prefer_variety"] is True
        assert kwargs["available_equipment"] == ["none"]

    def test_recipe_mode_passes_custom_recipe_filters(self, client) -> None:
        test_client, _ = client
        with (
            patch("app.routers.plans.goal_repo") as mock_goal,
            patch("app.routers.plans.plan_repo") as mock_plan,
            patch("app.routers.plans.generate_weekly_plan_v3_validated") as mock_v3,
            patch("app.routers.plans.favorite_repo") as mock_fav,
            patch("app.routers.plans.rating_repo") as mock_rating,
            patch("app.routers.plans.build_next_week_training_adjustment") as mock_training_adj,
        ):
            mock_goal.get_latest_goal = AsyncMock(return_value=MOCK_GOAL)
            mock_plan.upsert_weekly_plans = AsyncMock(return_value=None)
            mock_plan.get_past_recipe_ids = AsyncMock(return_value=[])
            mock_plan.get_weekly_plans = AsyncMock(return_value=_make_daily_plans_response())
            mock_fav.get_favorite_recipe_ids = AsyncMock(return_value=set())
            mock_rating.get_liked_recipe_ids = AsyncMock(return_value=set())
            mock_rating.get_disliked_recipe_ids = AsyncMock(return_value=set())
            mock_training_adj.return_value = type("Adj", (), {"scale": 1.0, "protect_forearms": False})()

            from app.services.plan_validator import ValidationResult

            mock_v3.return_value = ([], ValidationResult())

            resp = test_client.post(
                "/plans/weekly",
                json={
                    "start_date": "2026-03-09",
                    "mode": "recipe",
                    "recipe_filters": {
                        "allowed_sources": ["youtube"],
                        "prefer_favorites": False,
                        "exclude_disliked": False,
                        "prefer_variety": False,
                    },
                },
            )
        assert resp.status_code == 201
        _, kwargs = mock_v3.call_args
        assert kwargs["allowed_sources"] == ["youtube"]
        assert kwargs["prefer_favorites"] is False
        assert kwargs["exclude_disliked"] is False
        assert kwargs["prefer_variety"] is False

    def test_recipe_mode_passes_available_equipment(self, client) -> None:
        test_client, _ = client
        with (
            patch("app.routers.plans.goal_repo") as mock_goal,
            patch("app.routers.plans.plan_repo") as mock_plan,
            patch("app.routers.plans.generate_weekly_plan_v3_validated") as mock_v3,
            patch("app.routers.plans.favorite_repo") as mock_fav,
            patch("app.routers.plans.rating_repo") as mock_rating,
            patch("app.routers.plans.build_next_week_training_adjustment") as mock_training_adj,
        ):
            mock_goal.get_latest_goal = AsyncMock(return_value=MOCK_GOAL)
            mock_plan.upsert_weekly_plans = AsyncMock(return_value=None)
            mock_plan.get_past_recipe_ids = AsyncMock(return_value=[])
            mock_plan.get_weekly_plans = AsyncMock(return_value=_make_daily_plans_response())
            mock_fav.get_favorite_recipe_ids = AsyncMock(return_value=set())
            mock_rating.get_liked_recipe_ids = AsyncMock(return_value=set())
            mock_rating.get_disliked_recipe_ids = AsyncMock(return_value=set())
            mock_training_adj.return_value = type("Adj", (), {"scale": 1.0, "protect_forearms": False})()

            from app.services.plan_validator import ValidationResult

            mock_v3.return_value = ([], ValidationResult())

            resp = test_client.post(
                "/plans/weekly",
                json={
                    "start_date": "2026-03-09",
                    "mode": "recipe",
                    "available_equipment": ["pull_up_bar", "dumbbells"],
                },
            )
        assert resp.status_code == 201
        _, kwargs = mock_v3.call_args
        assert kwargs["available_equipment"] == ["dumbbells", "pull_up_bar"]

    def test_recipe_mode_rejects_empty_allowed_sources(self, client) -> None:
        test_client, _ = client
        with patch("app.routers.plans.goal_repo") as mock_goal:
            mock_goal.get_latest_goal = AsyncMock(return_value=MOCK_GOAL)
            resp = test_client.post(
                "/plans/weekly",
                json={
                    "start_date": "2026-03-09",
                    "mode": "recipe",
                    "recipe_filters": {
                        "allowed_sources": [],
                        "prefer_favorites": True,
                        "exclude_disliked": True,
                        "prefer_variety": True,
                    },
                },
            )
        assert resp.status_code == 422

    def test_default_mode_is_recipe(self, client) -> None:
        """mode 未指定時のデフォルトは recipe"""
        test_client, _ = client
        with (
            patch("app.routers.plans.goal_repo") as mock_goal,
            patch("app.routers.plans.plan_repo") as mock_plan,
            patch("app.routers.plans.generate_weekly_plan_v3_validated") as mock_v3,
            patch("app.routers.plans.favorite_repo") as mock_fav,
            patch("app.routers.plans.rating_repo") as mock_rating,
            patch("app.routers.plans.build_next_week_training_adjustment") as mock_training_adj,
        ):
            mock_goal.get_latest_goal = AsyncMock(return_value=MOCK_GOAL)
            mock_plan.upsert_weekly_plans = AsyncMock(return_value=None)
            mock_plan.get_weekly_plans = AsyncMock(return_value=_make_daily_plans_response())
            mock_plan.get_past_recipe_ids = AsyncMock(return_value=[])
            mock_fav.get_favorite_recipe_ids = AsyncMock(return_value=set())
            mock_rating.get_liked_recipe_ids = AsyncMock(return_value=set())
            mock_rating.get_disliked_recipe_ids = AsyncMock(return_value=set())
            mock_training_adj.return_value = type("Adj", (), {"scale": 1.0, "protect_forearms": False})()

            from datetime import timedelta

            from app.services.meal_suggestion import generate_structured_daily_meals
            from app.services.plan_validator import ValidationResult
            from app.services.weekly_planner import DailyPlanData

            start = date(2026, 3, 9)
            mock_plans = [
                DailyPlanData(
                    plan_date=start + timedelta(days=i),
                    meals=generate_structured_daily_meals(recipe=None),
                    training_day=None,
                )
                for i in range(7)
            ]
            mock_v3.return_value = (mock_plans, ValidationResult())

            resp = test_client.post(
                "/plans/weekly",
                json={"start_date": "2026-03-09"},
            )
        assert resp.status_code == 201
        # generate_weekly_plan_v3_validated が呼ばれたことを確認
        mock_v3.assert_called_once()

    def test_recipe_mode_with_staple_no_match_returns_422(self, client) -> None:
        """主食指定で一致候補ゼロなら422で失敗する。"""
        test_client, _ = client
        with (
            patch("app.routers.plans.goal_repo") as mock_goal,
            patch("app.routers.plans.plan_repo") as mock_plan,
            patch("app.routers.plans.generate_weekly_plan_v3_validated") as mock_v3,
            patch("app.routers.plans.favorite_repo") as mock_fav,
            patch("app.routers.plans.rating_repo") as mock_rating,
            patch("app.routers.plans.build_next_week_training_adjustment") as mock_training_adj,
        ):
            mock_goal.get_latest_goal = AsyncMock(return_value=MOCK_GOAL)
            mock_plan.upsert_weekly_plans = AsyncMock(return_value=None)
            mock_plan.get_weekly_plans = AsyncMock(return_value=_make_daily_plans_response())
            mock_plan.get_past_recipe_ids = AsyncMock(return_value=[])
            mock_fav.get_favorite_recipe_ids = AsyncMock(return_value=set())
            mock_rating.get_liked_recipe_ids = AsyncMock(return_value=set())
            mock_rating.get_disliked_recipe_ids = AsyncMock(return_value=set())
            mock_training_adj.return_value = type("Adj", (), {"scale": 1.0, "protect_forearms": False})()

            from datetime import timedelta

            from app.services.meal_suggestion import generate_structured_daily_meals
            from app.services.plan_validator import ValidationResult
            from app.services.weekly_planner import DailyPlanData

            start = date(2026, 3, 9)
            mock_plans = [
                DailyPlanData(
                    plan_date=start + timedelta(days=i),
                    meals=generate_structured_daily_meals(recipe=None),
                    training_day=None,
                )
                for i in range(7)
            ]
            # 主食一致ゼロを明示
            validation = ValidationResult(is_valid=True, issues=[], metrics={"staple_match_count": 0})
            mock_v3.return_value = (mock_plans, validation)

            resp = test_client.post(
                "/plans/weekly",
                json={"start_date": "2026-03-09", "mode": "recipe", "staple_name": "冷凍うどん"},
            )
        assert resp.status_code == 422


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


class TestGetTrainingSkillTree:
    def test_success(self, client) -> None:
        test_client, _ = client
        with (
            patch("app.routers.plans.goal_repo") as mock_goal,
            patch("app.routers.plans.build_training_skill_tree") as mock_tree,
        ):
            mock_goal.get_latest_goal = AsyncMock(
                return_value=GoalResponse(
                    id=GOAL_ID,
                    goal_type=Goal.STRENGTH,
                    target_kcal=2282.5,
                    protein_g=140.0,
                    fat_g=56.0,
                    carbs_g=388.1,
                )
            )
            mock_tree.return_value = {
                "summary": {
                    "goal_type": "strength",
                    "available_edge_count": 1,
                    "recommended_count": 1,
                    "has_negative_feedback": False,
                },
                "tracks": [
                    {
                        "track_id": "reverse_scapular_push_up",
                        "title": "リバーススキャピュラープッシュアップ",
                        "nodes": [
                            {
                                "exercise_id": "reverse_scapular_push_up",
                                "name_ja": "リバーススキャピュラープッシュアップ",
                                "required_equipment": ["none"],
                                "best_completed_reps": 10,
                                "status": "current",
                                "next_threshold_reps": 10,
                                "recommendation_reason": None,
                            }
                        ],
                        "edges": [],
                    }
                ],
            }

            resp = test_client.get("/plans/training-skill-tree?start_date=2026-03-22&available_equipment=none")

        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["goal_type"] == "strength"
        assert data["tracks"][0]["nodes"][0]["status"] == "current"
        mock_tree.assert_awaited_once()

    def test_goal_not_found_returns_404(self, client) -> None:
        test_client, _ = client
        with patch("app.routers.plans.goal_repo") as mock_goal:
            mock_goal.get_latest_goal = AsyncMock(return_value=None)
            resp = test_client.get("/plans/training-skill-tree?start_date=2026-03-22")
        assert resp.status_code == 404


class TestTrainingRecommendationMeta:
    def test_classic_mode_includes_training_recommendations_in_plan_meta(self, client) -> None:
        test_client, _ = client
        recommendation = type("Rec", (), {"replacement_id": "chin_up", "reason": "pull_up 10回達成"})()
        with (
            patch("app.routers.plans.goal_repo") as mock_goal,
            patch("app.routers.plans.food_repo") as mock_food,
            patch("app.routers.plans.plan_repo") as mock_plan,
            patch("app.routers.plans.build_next_week_training_adjustment") as mock_training_adj,
            patch(
                "app.routers.plans.recommend_progression_replacements",
                AsyncMock(return_value={"pull_up": recommendation}),
            ),
        ):
            mock_goal.get_latest_goal = AsyncMock(
                return_value=GoalResponse(
                    id=GOAL_ID,
                    goal_type=Goal.STRENGTH,
                    target_kcal=2282.5,
                    protein_g=140.0,
                    fat_g=56.0,
                    carbs_g=388.1,
                )
            )
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
        call_plans = mock_plan.upsert_weekly_plans.call_args[0][1]
        assert call_plans[0]["plan_meta"]["training_recommendations"] == [
            {
                "from_exercise_id": "pull_up",
                "to_exercise_id": "chin_up",
                "reason": "pull_up 10回達成",
            }
        ]
