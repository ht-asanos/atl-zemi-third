from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.recipe_quality_gate import filter_meal_like_recipes


def _sample_recipe(title: str, ingredients: list[str] | None = None) -> dict:
    return {
        "title": title,
        "description": "",
        "tags": ["うどん"],
        "ingredients": [{"ingredient_name": x, "amount_text": None} for x in (ingredients or [])],
    }


@pytest.mark.asyncio
async def test_filter_meal_like_recipes_accepts_and_rejects():
    recipes = [
        _sample_recipe("ぽっかぽか♪鍋焼きうどん", ["うどん", "卵"]),
        _sample_recipe("本格派☆ざるうどんのつけつゆ", ["めんつゆ", "水"]),
    ]

    mocked_resp = MagicMock()
    mocked_resp.text = '[{"is_meal": true, "reason":"main dish"}, {"is_meal": false, "reason":"sauce only"}]'

    with patch("app.services.recipe_quality_gate.settings") as mock_settings:
        mock_settings.google_api_key = "dummy"
        with patch("app.services.recipe_quality_gate.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.aio.models.generate_content = AsyncMock(return_value=mocked_resp)
            mock_client_cls.return_value = mock_client

            result = await filter_meal_like_recipes(recipes, batch_size=10)

    assert len(result.accepted) == 1
    assert result.accepted[0]["title"] == "ぽっかぽか♪鍋焼きうどん"
    assert len(result.rejected) == 1
    assert result.rejected[0]["recipe"]["title"] == "本格派☆ざるうどんのつけつゆ"


@pytest.mark.asyncio
async def test_filter_meal_like_recipes_rejects_on_llm_failure():
    recipes = [_sample_recipe("鍋焼きうどん"), _sample_recipe("つけつゆ")]
    with patch("app.services.recipe_quality_gate.settings") as mock_settings:
        mock_settings.google_api_key = "dummy"
        with patch("app.services.recipe_quality_gate.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("timeout"))
            mock_client_cls.return_value = mock_client

            result = await filter_meal_like_recipes(recipes, batch_size=10)

    assert len(result.accepted) == 0
    assert len(result.rejected) == 2
    assert all("reason" in x for x in result.rejected)


@pytest.mark.asyncio
async def test_filter_meal_like_recipes_rejects_when_missing_key():
    recipes = [_sample_recipe("鍋焼きうどん")]
    with patch("app.services.recipe_quality_gate.settings") as mock_settings:
        mock_settings.google_api_key = ""
        result = await filter_meal_like_recipes(recipes)

    assert len(result.accepted) == 0
    assert len(result.rejected) == 1
    assert result.rejected[0]["reason"] == "missing_google_api_key"
