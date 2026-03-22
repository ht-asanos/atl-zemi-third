"""管理者レビュー API のテスト"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.dependencies.auth import get_admin_user_id
from app.dependencies.supabase_client import get_service_supabase
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

ADMIN_USER_ID = uuid4()


def _auth_header() -> dict:
    return {"Authorization": "Bearer dummy"}


@pytest.fixture(autouse=True)
def _override_deps():
    mock_sb = AsyncMock()
    app.dependency_overrides[get_admin_user_id] = lambda: ADMIN_USER_ID
    app.dependency_overrides[get_service_supabase] = lambda: mock_sb
    yield mock_sb
    app.dependency_overrides.clear()


class TestListReviewIngredients:
    def test_returns_items(self):
        ingredient_id = str(uuid4())
        recipe_id = str(uuid4())
        mock_data = [
            {
                "id": ingredient_id,
                "recipe_id": recipe_id,
                "ingredient_name": "鶏もも肉",
                "amount_text": "200g",
                "mext_food_id": None,
                "match_confidence": 0.4,
                "manual_review_needed": True,
                "recipes": {"title": "チキンカレー", "is_nutrition_calculated": False},
                "mext_foods": None,
            }
        ]

        with patch("app.routers.admin_review.recipe_repo.get_ingredients_for_review") as mock_get:
            mock_get.return_value = (mock_data, 1)
            resp = client.get("/admin/review/ingredients", headers=_auth_header())
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 1
            assert len(data["items"]) == 1
            assert data["items"][0]["ingredient_name"] == "鶏もも肉"
            assert data["items"][0]["is_nutrition_calculated"] is False


class TestUpdateReviewIngredient:
    def test_approve_with_mext_food_id(self):
        ingredient_id = uuid4()
        recipe_id = uuid4()
        mext_food_id = uuid4()

        with patch("app.routers.admin_review.recipe_repo.update_ingredient_match") as mock_update:
            mock_update.return_value = recipe_id
            with patch("app.routers.admin_review.calculate_recipe_nutrition") as mock_calc:
                from app.models.food import NutritionStatus
                from app.services.ingredient_matcher import NutritionResult

                mock_calc.return_value = NutritionResult(
                    nutrition={"kcal": 300}, status=NutritionStatus.CALCULATED, matched_count=1, total_count=1
                )
                resp = client.patch(
                    f"/admin/review/ingredients/{ingredient_id}",
                    json={"mext_food_id": str(mext_food_id), "approved": True},
                    headers=_auth_header(),
                )
                assert resp.status_code == 200
                mock_update.assert_called_once()
                args, kwargs = mock_update.call_args
                # positional: supabase, ingredient_id, mext_food_id, confidence, review_needed
                assert args[3] == 1.0  # confidence
                assert args[4] is False  # review_needed
                mock_calc.assert_called_once()

    def test_reject_sets_null(self):
        ingredient_id = uuid4()
        recipe_id = uuid4()

        with patch("app.routers.admin_review.recipe_repo.update_ingredient_match") as mock_update:
            mock_update.return_value = recipe_id
            with patch("app.routers.admin_review.calculate_recipe_nutrition") as mock_calc:
                from app.models.food import NutritionStatus
                from app.services.ingredient_matcher import NutritionResult

                mock_calc.return_value = NutritionResult(
                    nutrition=None, status=NutritionStatus.FAILED, matched_count=0, total_count=0
                )
                resp = client.patch(
                    f"/admin/review/ingredients/{ingredient_id}",
                    json={"approved": False},
                    headers=_auth_header(),
                )
                assert resp.status_code == 200
                args, kwargs = mock_update.call_args
                assert args[2] is None  # mext_food_id
                assert args[3] == 0.0  # confidence

    def test_not_found_returns_404(self):
        ingredient_id = uuid4()

        with patch("app.routers.admin_review.recipe_repo.update_ingredient_match") as mock_update:
            mock_update.return_value = None
            resp = client.patch(
                f"/admin/review/ingredients/{ingredient_id}",
                json={"approved": True},
                headers=_auth_header(),
            )
            assert resp.status_code == 404


class TestNonAdminReview:
    def test_non_admin_returns_403(self):
        from fastapi import HTTPException

        def raise_403():
            raise HTTPException(status_code=403, detail="Admin access required")

        app.dependency_overrides[get_admin_user_id] = raise_403
        resp = client.get("/admin/review/ingredients", headers=_auth_header())
        assert resp.status_code == 403
