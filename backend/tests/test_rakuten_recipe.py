"""楽天レシピ API クライアントのテスト（JSON パース）"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.services.rakuten_recipe import (
    _parse_minutes,
    fetch_category_list,
    fetch_category_ranking,
    parse_ranking_recipes,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestParseMinutes:
    def test_about_30_min(self):
        assert _parse_minutes("約30分") == 30

    def test_about_10_min(self):
        assert _parse_minutes("約10分") == 10

    def test_none(self):
        assert _parse_minutes(None) is None

    def test_no_number(self):
        assert _parse_minutes("すぐ") is None


class TestParseRankingRecipes:
    def setup_method(self):
        raw = json.loads((FIXTURES_DIR / "rakuten_ranking.json").read_text())
        self.recipes = parse_ranking_recipes(raw["result"])

    def test_parse_count(self):
        assert len(self.recipes) == 2

    def test_first_recipe(self):
        r = self.recipes[0]
        assert r["rakuten_recipe_id"] == 1234567
        assert r["title"] == "簡単！鶏もも肉の照り焼き"
        assert r["recipe_url"] == "https://recipe.rakuten.co.jp/recipe/1234567/"
        assert r["servings"] == 2
        assert r["cost_estimate"] == "300円前後"
        assert r["cooking_minutes"] == 30
        assert "鶏肉" in r["tags"]

    def test_ingredients_parsed(self):
        r = self.recipes[0]
        assert len(r["ingredients"]) == 5
        assert r["ingredients"][0]["ingredient_name"] == "鶏もも肉 300g"

    def test_second_recipe(self):
        r = self.recipes[1]
        assert r["rakuten_recipe_id"] == 2345678
        assert r["cooking_minutes"] == 10
        assert r["servings"] == 1


@pytest.mark.asyncio
async def test_fetch_category_list_uses_access_key_in_query_param():
    captured: dict = {}

    class DummyClient:
        async def get(self, url, params=None, headers=None):
            captured["url"] = url
            captured["params"] = params
            captured["headers"] = headers
            return SimpleNamespace(
                raise_for_status=lambda: None,
                json=lambda: {"result": {"large": [{"categoryId": "30"}], "medium": [], "small": []}},
            )

    rows = await fetch_category_list(DummyClient(), "app_id_123", "access_key_456")

    assert len(rows) == 1
    assert captured["params"]["applicationId"] == "app_id_123"
    assert captured["params"]["accessKey"] == "access_key_456"
    assert captured["headers"] is None


@pytest.mark.asyncio
async def test_fetch_category_ranking_uses_access_key_in_query_param():
    captured: dict = {}

    class DummyClient:
        async def get(self, url, params=None, headers=None):
            captured["url"] = url
            captured["params"] = params
            captured["headers"] = headers
            return SimpleNamespace(
                raise_for_status=lambda: None,
                json=lambda: {"result": [{"recipeId": 1}]},
            )

    rows = await fetch_category_ranking(DummyClient(), "app_id_123", "access_key_456", "10-275")

    assert len(rows) == 1
    assert captured["params"]["applicationId"] == "app_id_123"
    assert captured["params"]["accessKey"] == "access_key_456"
    assert captured["params"]["categoryId"] == "10-275"
    assert captured["headers"] is None
