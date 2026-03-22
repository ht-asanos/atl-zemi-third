"""Gemini MEXT マッチングサービスのテスト"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.gemini_mext_matcher import (
    BATCH_SIZE,
    GEMINI_MATCH_CONFIDENCE,
    _extract_json_array,
    gemini_match_batch,
)


class TestExtractJsonArray:
    def test_plain_json(self):
        text = '[{"selected_id": "abc", "reason": "test"}]'
        result = _extract_json_array(text)
        assert result == [{"selected_id": "abc", "reason": "test"}]

    def test_markdown_fences(self):
        text = '```json\n[{"selected_id": "abc", "reason": "test"}]\n```'
        result = _extract_json_array(text)
        assert result == [{"selected_id": "abc", "reason": "test"}]

    def test_markdown_fences_no_lang(self):
        text = '```\n[{"selected_id": "abc", "reason": "test"}]\n```'
        result = _extract_json_array(text)
        assert result == [{"selected_id": "abc", "reason": "test"}]

    def test_no_array(self):
        result = _extract_json_array("no array here")
        assert result is None

    def test_invalid_json(self):
        result = _extract_json_array("[invalid json}")
        assert result is None

    def test_empty_array(self):
        result = _extract_json_array("[]")
        assert result == []

    def test_text_before_and_after_array(self):
        text = 'Here is the result:\n[{"selected_id": "xyz", "reason": "ok"}]\nDone.'
        result = _extract_json_array(text)
        assert result == [{"selected_id": "xyz", "reason": "ok"}]


class TestGeminiMatchBatch:
    @pytest.mark.asyncio
    async def test_graceful_without_api_key(self):
        """API key なし → 全て confidence=0.0 で返す"""
        items = [("チキン", [{"id": "uuid-1", "name": "にわとり もも 皮つき"}])]
        with patch("app.services.gemini_mext_matcher.settings") as mock_settings:
            mock_settings.google_api_key = ""
            results = await gemini_match_batch(items)
        assert len(results) == 1
        assert results[0].mext_food_id is None
        assert results[0].confidence == 0.0
        assert results[0].ingredient_name == "チキン"

    @pytest.mark.asyncio
    async def test_empty_items(self):
        """空リスト → 空リストを返す"""
        results = await gemini_match_batch([])
        assert results == []

    @pytest.mark.asyncio
    async def test_batch_selects_correct_candidate(self):
        """Gemini が正しい候補 ID を選択する"""
        items = [("チキン", [{"id": "uuid-chicken", "name": "にわとり もも 皮つき"}])]
        mock_response = MagicMock()
        mock_response.text = '[{"selected_id": "uuid-chicken", "reason": "チキン=にわとり"}]'

        with (
            patch("app.services.gemini_mext_matcher.settings") as mock_settings,
            patch("app.services.gemini_mext_matcher.genai") as mock_genai,
        ):
            mock_settings.google_api_key = "test-key"
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

            results = await gemini_match_batch(items)

        assert len(results) == 1
        assert results[0].mext_food_id == "uuid-chicken"
        assert results[0].mext_food_name == "にわとり もも 皮つき"
        assert results[0].confidence == GEMINI_MATCH_CONFIDENCE

    @pytest.mark.asyncio
    async def test_batch_no_match_returns_none(self):
        """Gemini が 'none' を返した場合、confidence=0.0"""
        items = [("謎の食材", [{"id": "uuid-1", "name": "なんか食品"}])]
        mock_response = MagicMock()
        mock_response.text = '[{"selected_id": "none", "reason": "not found"}]'

        with (
            patch("app.services.gemini_mext_matcher.settings") as mock_settings,
            patch("app.services.gemini_mext_matcher.genai") as mock_genai,
        ):
            mock_settings.google_api_key = "test-key"
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

            results = await gemini_match_batch(items)

        assert len(results) == 1
        assert results[0].mext_food_id is None
        assert results[0].confidence == 0.0

    @pytest.mark.asyncio
    async def test_invalid_selected_id_rejected(self):
        """候補にない ID（幻覚）は reject → mext_food_id=None"""
        items = [("チキン", [{"id": "uuid-chicken", "name": "にわとり"}])]
        mock_response = MagicMock()
        mock_response.text = '[{"selected_id": "uuid-fake-hallucinated", "reason": "hallucinated"}]'

        with (
            patch("app.services.gemini_mext_matcher.settings") as mock_settings,
            patch("app.services.gemini_mext_matcher.genai") as mock_genai,
        ):
            mock_settings.google_api_key = "test-key"
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

            results = await gemini_match_batch(items)

        assert results[0].mext_food_id is None
        assert results[0].confidence == 0.0

    @pytest.mark.asyncio
    async def test_batch_splits_at_batch_size(self):
        """60 件 → BATCH_SIZE=30 で 2 回の API 呼び出し"""
        items = [(f"食材{i}", [{"id": f"uuid-{i}", "name": f"MEXT食品{i}"}]) for i in range(60)]

        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.text = json.dumps([{"selected_id": "none", "reason": "test"}] * BATCH_SIZE)
            return resp

        with (
            patch("app.services.gemini_mext_matcher.settings") as mock_settings,
            patch("app.services.gemini_mext_matcher.genai") as mock_genai,
            patch("app.services.gemini_mext_matcher.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_settings.google_api_key = "test-key"
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.aio.models.generate_content = mock_generate

            results = await gemini_match_batch(items)

        assert len(results) == 60
        assert call_count == 2  # 60 / BATCH_SIZE(30) = 2

    @pytest.mark.asyncio
    async def test_api_failure_returns_none(self):
        """API 例外時はフォールバック（confidence=0.0）"""
        items = [("食材X", [{"id": "uuid-x", "name": "MEXT X"}])]

        with (
            patch("app.services.gemini_mext_matcher.settings") as mock_settings,
            patch("app.services.gemini_mext_matcher.genai") as mock_genai,
            patch("app.services.gemini_mext_matcher.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_settings.google_api_key = "test-key"
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.aio.models.generate_content = AsyncMock(side_effect=Exception("API error"))

            results = await gemini_match_batch(items)

        assert len(results) == 1
        assert results[0].mext_food_id is None
        assert results[0].confidence == 0.0

    @pytest.mark.asyncio
    async def test_json_parse_with_markdown_fences(self):
        """```json ラッパーがあっても正しくパースできる"""
        items = [("食材Y", [{"id": "uuid-y", "name": "MEXT Y"}])]
        mock_response = MagicMock()
        mock_response.text = '```json\n[{"selected_id": "uuid-y", "reason": "match"}]\n```'

        with (
            patch("app.services.gemini_mext_matcher.settings") as mock_settings,
            patch("app.services.gemini_mext_matcher.genai") as mock_genai,
        ):
            mock_settings.google_api_key = "test-key"
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

            results = await gemini_match_batch(items)

        assert results[0].mext_food_id == "uuid-y"
        assert results[0].confidence == GEMINI_MATCH_CONFIDENCE
