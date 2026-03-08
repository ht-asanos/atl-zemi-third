"""タグ抽出サービスのテスト (OpenAI モック)"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.tag_extractor import extract_tags


def _mock_response(content: str):
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.fixture
def mock_settings():
    with patch("app.services.tag_extractor.settings") as s:
        s.openai_api_key = "test-key"
        s.openai_model = "gpt-4o-mini"
        yield s


class TestExtractTags:
    @pytest.mark.asyncio
    async def test_success(self, mock_settings) -> None:
        with patch("app.services.tag_extractor.AsyncOpenAI") as mock_cls:
            client = AsyncMock()
            client.chat.completions.create = AsyncMock(return_value=_mock_response('["too_hard", "bored_staple"]'))
            mock_cls.return_value = client

            result = await extract_tags("トレーニングがきつすぎた。主食に飽きた。")

        assert result.status == "success"
        assert set(result.tags) == {"too_hard", "bored_staple"}

    @pytest.mark.asyncio
    async def test_unknown_tags_filtered(self, mock_settings) -> None:
        with patch("app.services.tag_extractor.AsyncOpenAI") as mock_cls:
            client = AsyncMock()
            client.chat.completions.create = AsyncMock(return_value=_mock_response('["too_hard", "unknown_tag"]'))
            mock_cls.return_value = client

            result = await extract_tags("きつい")

        assert result.status == "success"
        assert result.tags == ["too_hard"]

    @pytest.mark.asyncio
    async def test_empty_response(self, mock_settings) -> None:
        with patch("app.services.tag_extractor.AsyncOpenAI") as mock_cls:
            client = AsyncMock()
            client.chat.completions.create = AsyncMock(return_value=_mock_response("[]"))
            mock_cls.return_value = client

            result = await extract_tags("特に問題ない")

        assert result.status == "success"
        assert result.tags == []

    @pytest.mark.asyncio
    async def test_retry_then_success(self, mock_settings) -> None:
        with (
            patch("app.services.tag_extractor.AsyncOpenAI") as mock_cls,
            patch("app.services.tag_extractor.asyncio.sleep", new_callable=AsyncMock),
        ):
            client = AsyncMock()
            client.chat.completions.create = AsyncMock(
                side_effect=[
                    Exception("API error"),
                    _mock_response('["forearm_sore"]'),
                ]
            )
            mock_cls.return_value = client

            result = await extract_tags("前腕が痛い")

        assert result.status == "success"
        assert result.tags == ["forearm_sore"]

    @pytest.mark.asyncio
    async def test_all_retries_fail(self, mock_settings) -> None:
        with (
            patch("app.services.tag_extractor.AsyncOpenAI") as mock_cls,
            patch("app.services.tag_extractor.asyncio.sleep", new_callable=AsyncMock),
        ):
            client = AsyncMock()
            client.chat.completions.create = AsyncMock(side_effect=Exception("API error"))
            mock_cls.return_value = client

            result = await extract_tags("テスト")

        assert result.status == "failed"
        assert result.tags == []

    @pytest.mark.asyncio
    async def test_no_api_key(self) -> None:
        with patch("app.services.tag_extractor.settings") as s:
            s.openai_api_key = ""

            result = await extract_tags("テスト")

        assert result.status == "failed"
        assert result.tags == []
