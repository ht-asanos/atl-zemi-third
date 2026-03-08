"""MEXT スクレイパーのユニットテスト（HTML パースロジック）"""

from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from app.services.mext_scraper import _extract_item_nos, _parse_float, parse_food_detail

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestParseFloat:
    def test_normal_number(self):
        assert _parse_float("17.3") == 17.3

    def test_integer(self):
        assert _parse_float("253") == 253.0

    def test_trace(self):
        assert _parse_float("Tr") == 0.0

    def test_dash(self):
        assert _parse_float("-") == 0.0

    def test_parenthesized(self):
        assert _parse_float("(0)") == 0.0

    def test_empty(self):
        assert _parse_float("") == 0.0

    def test_parenthesized_value(self):
        assert _parse_float("(3.5)") == 3.5


class TestParseFoodDetail:
    def test_parse_chicken_thigh(self):
        html = (FIXTURES_DIR / "mext_detail.html").read_text()
        food = parse_food_detail(html, "11_01088_7")

        assert food is not None
        assert food.mext_food_id == "11_01088_7"
        assert "鶏もも肉" in food.name
        assert food.category_code == "11"
        assert food.category_name == "肉類"
        assert food.kcal_per_100g == 253.0
        assert food.protein_g_per_100g == 17.3
        assert food.fat_g_per_100g == 19.1
        assert food.carbs_g_per_100g == 0.0
        assert food.fiber_g_per_100g == 0.0
        assert food.sodium_mg_per_100g == 63.0
        assert food.calcium_mg_per_100g == 5.0
        assert food.iron_mg_per_100g == 0.6

    def test_parse_invalid_html(self):
        food = parse_food_detail("<html><body></body></html>", "00_00000_0")
        assert food is None

    def test_category_extraction(self):
        html = (FIXTURES_DIR / "mext_detail.html").read_text()
        food = parse_food_detail(html, "01_00001_0")
        assert food is not None
        assert food.category_code == "01"
        assert food.category_name == "穀類"


class TestExtractItemNos:
    def test_extracts_items(self):
        html = """
        <html><body>
        <a href="/details/details.pl?ITEM_NO=11_01088_7">鶏もも肉</a>
        <a href="/details/details.pl?ITEM_NO=11_01089_7">鶏むね肉</a>
        <a href="/other">その他</a>
        </body></html>
        """
        result = _extract_item_nos(html)
        assert result == ["11_01088_7", "11_01089_7"]

    def test_empty_html(self):
        assert _extract_item_nos("<html><body></body></html>") == []

    def test_no_matching_links(self):
        html = '<html><body><a href="/other">link</a></body></html>'
        assert _extract_item_nos(html) == []


class TestSearchFoodsByName:
    @pytest.mark.asyncio
    async def test_returns_empty_on_http_error(self):
        from app.services.mext_scraper import search_foods_by_name

        mock_response = AsyncMock()
        mock_response.status_code = 500

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await search_foods_by_name(mock_client, "鶏肉")
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_no_results(self):
        from app.services.mext_scraper import search_foods_by_name

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>No results</body></html>"

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await search_foods_by_name(mock_client, "存在しない食品")
        assert result == []

    @pytest.mark.asyncio
    async def test_respects_max_results(self):
        from app.services.mext_scraper import search_foods_by_name

        search_html = """
        <html><body>
        <a href="/details/details.pl?ITEM_NO=01_001">A</a>
        <a href="/details/details.pl?ITEM_NO=01_002">B</a>
        <a href="/details/details.pl?ITEM_NO=01_003">C</a>
        </body></html>
        """
        detail_html = (FIXTURES_DIR / "mext_detail.html").read_text()

        mock_client = AsyncMock(spec=httpx.AsyncClient)

        search_resp = AsyncMock()
        search_resp.status_code = 200
        search_resp.text = search_html

        detail_resp = AsyncMock()
        detail_resp.status_code = 200
        detail_resp.text = detail_html

        mock_client.get = AsyncMock(side_effect=[search_resp, detail_resp])

        result = await search_foods_by_name(mock_client, "テスト", max_results=1)
        assert len(result) <= 1

    @pytest.mark.asyncio
    async def test_returns_empty_on_timeout(self):
        from app.services.mext_scraper import search_foods_by_name

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        result = await search_foods_by_name(mock_client, "テスト")
        assert result == []
