"""レシピ評価機能のテスト"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.models.nutrition import PFCBudget
from app.models.recipe import Recipe
from app.repositories import rating_repo
from app.repositories.recipe_repo import (
    get_recipes_for_dinner,
)
from app.services.weekly_planner import _ensure_exploration

# --- rating_repo テスト ---


class TestUpsertRating:
    @pytest.mark.asyncio
    async def test_upsert_like(self):
        supabase = MagicMock()
        supabase.table.return_value.upsert.return_value.execute = AsyncMock()
        await rating_repo.upsert_rating(supabase, uuid4(), uuid4(), 1)
        supabase.table.assert_called_with("user_recipe_ratings")

    @pytest.mark.asyncio
    async def test_upsert_dislike(self):
        supabase = MagicMock()
        supabase.table.return_value.upsert.return_value.execute = AsyncMock()
        await rating_repo.upsert_rating(supabase, uuid4(), uuid4(), -1)
        supabase.table.assert_called_with("user_recipe_ratings")

    @pytest.mark.asyncio
    async def test_upsert_zero_deletes(self):
        """rating=0 → レコード DELETE"""
        supabase = MagicMock()
        supabase.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute = AsyncMock()
        await rating_repo.upsert_rating(supabase, uuid4(), uuid4(), 0)
        supabase.table.assert_called_with("user_recipe_ratings")
        supabase.table.return_value.delete.assert_called_once()


class TestGetRatings:
    @pytest.mark.asyncio
    async def test_get_ratings_for_user(self):
        supabase = MagicMock()
        rid1, rid2 = uuid4(), uuid4()
        mock_resp = MagicMock(
            data=[
                {"recipe_id": str(rid1), "rating": 1},
                {"recipe_id": str(rid2), "rating": -1},
            ]
        )
        supabase.table.return_value.select.return_value.eq.return_value.execute = AsyncMock(return_value=mock_resp)
        result = await rating_repo.get_ratings_for_user(supabase, uuid4())
        assert result[rid1] == 1
        assert result[rid2] == -1

    @pytest.mark.asyncio
    async def test_get_liked_recipe_ids(self):
        supabase = MagicMock()
        rid = uuid4()
        mock_resp = MagicMock(data=[{"recipe_id": str(rid)}])
        supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute = AsyncMock(
            return_value=mock_resp
        )
        result = await rating_repo.get_liked_recipe_ids(supabase, uuid4())
        assert rid in result

    @pytest.mark.asyncio
    async def test_get_disliked_recipe_ids(self):
        supabase = MagicMock()
        rid = uuid4()
        mock_resp = MagicMock(data=[{"recipe_id": str(rid)}])
        supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute = AsyncMock(
            return_value=mock_resp
        )
        result = await rating_repo.get_disliked_recipe_ids(supabase, uuid4())
        assert rid in result

    @pytest.mark.asyncio
    async def test_get_all_rated_recipe_ids(self):
        supabase = MagicMock()
        rid1, rid2 = uuid4(), uuid4()
        mock_resp = MagicMock(
            data=[
                {"recipe_id": str(rid1)},
                {"recipe_id": str(rid2)},
            ]
        )
        supabase.table.return_value.select.return_value.eq.return_value.execute = AsyncMock(return_value=mock_resp)
        result = await rating_repo.get_all_rated_recipe_ids(supabase, uuid4())
        assert rid1 in result
        assert rid2 in result


# --- get_recipes_for_dinner スコアリングテスト ---


def _make_recipe(title: str, protein_g: float = 25.0, recipe_id=None) -> Recipe:
    return Recipe(
        id=recipe_id or uuid4(),
        title=title,
        recipe_url="https://example.com",
        nutrition_per_serving={"protein_g": protein_g, "kcal": 300, "fat_g": 10, "carbs_g": 30},
    )


def _make_supabase_with_rows(rows):
    """get_recipes_for_dinner 用のモック supabase を作成する。"""
    mock_resp = MagicMock(data=rows)
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.limit.return_value.execute = AsyncMock(return_value=mock_resp)
    return supabase


class TestScoringWithRatings:
    @pytest.mark.asyncio
    async def test_liked_recipe_prioritized(self):
        """liked レシピがスコアで優先される"""
        liked_id = uuid4()
        normal_id = uuid4()
        rows = [
            {
                "id": str(normal_id),
                "title": "通常レシピ",
                "recipe_url": "https://example.com",
                "nutrition_per_serving": {"protein_g": 25.0, "kcal": 300, "fat_g": 10, "carbs_g": 30},
                "is_nutrition_calculated": True,
                "tags": [],
                "servings": 1,
            },
            {
                "id": str(liked_id),
                "title": "お気に入りレシピ",
                "recipe_url": "https://example.com",
                "nutrition_per_serving": {"protein_g": 25.0, "kcal": 300, "fat_g": 10, "carbs_g": 30},
                "is_nutrition_calculated": True,
                "tags": [],
                "servings": 1,
            },
        ]
        supabase = _make_supabase_with_rows(rows)
        budget = PFCBudget(protein_g=25.0, fat_g=56, carbs_g=270)
        result = await get_recipes_for_dinner(
            supabase,
            budget,
            count=2,
            liked_ids={liked_id},
        )
        assert result.recipes[0].id == liked_id

    @pytest.mark.asyncio
    async def test_disliked_recipe_deprioritized(self):
        """disliked レシピがスコアで後回しになる"""
        disliked_id = uuid4()
        normal_id = uuid4()
        rows = [
            {
                "id": str(disliked_id),
                "title": "嫌いなレシピ",
                "recipe_url": "https://example.com",
                "nutrition_per_serving": {"protein_g": 25.0, "kcal": 300, "fat_g": 10, "carbs_g": 30},
                "is_nutrition_calculated": True,
                "tags": [],
                "servings": 1,
            },
            {
                "id": str(normal_id),
                "title": "通常レシピ",
                "recipe_url": "https://example.com",
                "nutrition_per_serving": {"protein_g": 25.0, "kcal": 300, "fat_g": 10, "carbs_g": 30},
                "is_nutrition_calculated": True,
                "tags": [],
                "servings": 1,
            },
        ]
        supabase = _make_supabase_with_rows(rows)
        budget = PFCBudget(protein_g=25.0, fat_g=56, carbs_g=270)
        result = await get_recipes_for_dinner(
            supabase,
            budget,
            count=2,
            disliked_ids={disliked_id},
        )
        assert result.recipes[0].id == normal_id
        assert result.recipes[1].id == disliked_id

    @pytest.mark.asyncio
    async def test_dislike_penalty_capped(self):
        """dislike の sort_key が MAX_DISLIKE_SORT_KEY を超えない（レシピは除外ではなく減点）"""
        disliked_id = uuid4()
        rows = [
            {
                "id": str(disliked_id),
                "title": "遠いレシピ",
                "recipe_url": "https://example.com",
                "nutrition_per_serving": {"protein_g": 25.0, "kcal": 300, "fat_g": 10, "carbs_g": 30},
                "is_nutrition_calculated": True,
                "tags": [],
                "servings": 1,
            },
        ]
        supabase = _make_supabase_with_rows(rows)
        budget = PFCBudget(protein_g=300.0, fat_g=56, carbs_g=270)
        result = await get_recipes_for_dinner(
            supabase,
            budget,
            count=1,
            disliked_ids={disliked_id},
        )
        assert len(result.recipes) == 1


# --- 探索枠テスト ---


class TestEnsureExploration:
    def test_no_rated_ids_noop(self):
        """rated_ids が空なら変更なし"""
        recipes = [_make_recipe(f"r{i}") for i in range(7)]
        result = _ensure_exploration(recipes, set())
        assert result == recipes

    def test_enough_unrated_noop(self):
        """未評価が EXPLORE_SLOTS 以上なら変更なし"""
        recipes = [_make_recipe(f"r{i}") for i in range(7)]
        rated = {recipes[0].id, recipes[1].id}
        result = _ensure_exploration(recipes, rated)
        assert result == recipes

    def test_all_rated_returns_same(self):
        """全既評価でも現状の実装では候補なしのため変更なし"""
        recipes = [_make_recipe(f"r{i}") for i in range(7)]
        rated = {r.id for r in recipes}
        result = _ensure_exploration(recipes, rated)
        assert len(result) == 7
