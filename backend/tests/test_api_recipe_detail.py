from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.dependencies.auth import get_current_user_id
from app.dependencies.supabase_client import get_authenticated_supabase
from app.main import app
from app.models.food import NutritionStatus
from app.models.recipe import Recipe, RecipeIngredient, RecipeStep
from fastapi.testclient import TestClient

TEST_USER_ID = uuid4()


@pytest.fixture
def client():
    mock_supabase = AsyncMock()
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_authenticated_supabase] = lambda: mock_supabase
    yield TestClient(app, raise_server_exceptions=False), mock_supabase
    app.dependency_overrides.clear()


def _auth_header() -> dict:
    return {"Authorization": "Bearer dummy"}


def _sample_recipe() -> Recipe:
    rid = uuid4()
    return Recipe(
        id=rid,
        title="鍋焼きうどん",
        description="あったかうどん",
        image_url=None,
        recipe_url="https://example.com/recipe",
        ingredients=[
            RecipeIngredient(
                ingredient_name="冷凍うどん",
                display_ingredient_name="冷凍うどん",
                alternative_ingredient_names=[],
                amount_text="1玉",
                kcal=250,
                protein_g=6.0,
                fat_g=1.0,
                carbs_g=55.0,
                nutrition_match_status="matched",
                nutrition_source="mext",
                matched_food_name="冷凍うどん",
            )
        ],
        nutrition_per_serving={"kcal": 400, "protein_g": 20, "fat_g": 8, "carbs_g": 60},
        servings=1,
        cooking_minutes=12,
        tags=["うどん"],
        nutrition_status=NutritionStatus.CALCULATED,
        generated_steps=[RecipeStep(step_no=1, text="うどんを茹でる", est_minutes=3)],
        steps_status="generated",
        ingredient_nutrition_coverage={"matched_count": 1, "total_count": 1, "coverage_rate": 1.0},
    )


def test_get_recipe_detail_includes_coverage_and_steps(client):
    test_client, _ = client
    sample = _sample_recipe()
    with (
        patch("app.routers.recipes.recipe_repo.get_recipe_by_id", new=AsyncMock(return_value=sample)),
        patch("app.routers.recipes.ensure_generated_steps", new=AsyncMock(return_value=sample)),
    ):
        resp = test_client.get(f"/recipes/{sample.id}", headers=_auth_header())
    assert resp.status_code == 200
    body = resp.json()
    assert body["ingredient_nutrition_coverage"]["coverage_rate"] == 1.0
    assert body["ingredients"][0]["nutrition_match_status"] == "matched"
    assert body["ingredients"][0]["display_ingredient_name"] == "冷凍うどん"
    assert body["ingredients"][0]["alternative_ingredient_names"] == []
    assert body["generated_steps"][0]["text"] == "うどんを茹でる"
    assert body["steps_status"] == "generated"
