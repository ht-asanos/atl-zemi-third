"""gemini_display_name サービスのテスト。"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.gemini_display_name import _validate_display_name, generate_display_names

# --- _validate_display_name 単体テスト ---


class TestValidateDisplayName:
    def test_valid_short_name(self):
        assert _validate_display_name("鶏もも肉", "肉類/＜鶏肉＞/もも/皮つき/生") == "鶏もも肉"

    def test_strips_whitespace(self):
        assert _validate_display_name("  鶏もも肉  ", "original") == "鶏もも肉"

    def test_normalizes_whitespace(self):
        assert _validate_display_name("鶏　もも肉", "original") == "鶏 もも肉"

    def test_empty_string_returns_none(self):
        assert _validate_display_name("", "original") is None

    def test_too_long_returns_none(self):
        long_name = "あ" * 41
        assert _validate_display_name(long_name, "original") is None

    def test_exactly_40_chars_is_valid(self):
        name = "あ" * 40
        assert _validate_display_name(name, "original") == name

    def test_forbidden_slash(self):
        assert _validate_display_name("穀類/米", "original") is None

    def test_forbidden_table_number(self):
        assert _validate_display_name("米 - 01.一般成分表", "original") is None

    def test_forbidden_ippan_seibun(self):
        assert _validate_display_name("米 一般成分表", "original") is None

    def test_forbidden_vitamin(self):
        assert _validate_display_name("米 ビタミン類", "original") is None

    def test_same_as_original_returns_none(self):
        assert _validate_display_name("same name", "same name") is None

    def test_whitespace_only_returns_none(self):
        assert _validate_display_name("   ", "original") is None


# --- generate_display_names テスト ---


def _make_mock_response(output_list: list[str]) -> MagicMock:
    """Gemini APIレスポンスのモックを作成する。"""
    resp = MagicMock()
    resp.text = json.dumps(output_list, ensure_ascii=False)
    return resp


@pytest.fixture()
def mock_settings():
    with patch("app.services.gemini_display_name.settings") as mock:
        mock.google_api_key = "test-key"
        yield mock


@pytest.fixture()
def mock_genai_client():
    with patch("app.services.gemini_display_name.genai.Client") as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        yield client


class TestGenerateDisplayNames:
    async def test_normal_response(self, mock_settings, mock_genai_client):
        """正常なJSON応答のパース + バリデーション検証。"""
        input_names = [
            "肉類/＜鶏肉＞/もも/皮つき/生 - 01.一般成分表-無機質-ビタミン類",
            "調味料及び香辛料類/＜調味料類＞/しょうゆ - 01.一般成分表-無機質-ビタミン類",
        ]
        output_names = ["鶏もも肉", "しょうゆ"]

        mock_genai_client.aio.models.generate_content = AsyncMock(return_value=_make_mock_response(output_names))

        results = await generate_display_names(input_names)
        assert results == ["鶏もも肉", "しょうゆ"]

    async def test_validation_failure_returns_none(self, mock_settings, mock_genai_client):
        """バリデーション失敗ケース → None。"""
        input_names = ["original1", "original2", "original3"]
        # 1つ目: 長すぎ, 2つ目: 禁止パターン, 3つ目: 正常
        output_names = ["あ" * 41, "穀類/米", "短い名前"]

        mock_genai_client.aio.models.generate_content = AsyncMock(return_value=_make_mock_response(output_names))

        results = await generate_display_names(input_names)
        assert results == [None, None, "短い名前"]

    async def test_invalid_json_returns_all_none(self, mock_settings, mock_genai_client):
        """不正JSON時のフォールバック。"""
        resp = MagicMock()
        resp.text = "これはJSONではありません"
        mock_genai_client.aio.models.generate_content = AsyncMock(return_value=resp)

        results = await generate_display_names(["name1", "name2"])
        assert results == [None, None]

    async def test_api_exception_returns_all_none(self, mock_settings, mock_genai_client):
        """API例外時のフォールバック。"""
        mock_genai_client.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("API error"))

        results = await generate_display_names(["name1", "name2"])
        assert results == [None, None]

    async def test_length_mismatch_returns_all_none(self, mock_settings, mock_genai_client):
        """応答配列長が入力と不一致 → 全て None。"""
        output_names = ["名前1"]  # 入力は2件だが出力は1件
        mock_genai_client.aio.models.generate_content = AsyncMock(return_value=_make_mock_response(output_names))

        results = await generate_display_names(["name1", "name2"])
        assert results == [None, None]

    async def test_batch_splitting(self, mock_settings, mock_genai_client):
        """バッチ分割の検証（120件→50/50/20の3バッチ）。"""
        batch_sizes = [50, 50, 20]
        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            size = batch_sizes[call_count]
            call_count += 1
            return _make_mock_response([f"表示名{i}" for i in range(size)])

        mock_genai_client.aio.models.generate_content = AsyncMock(side_effect=mock_generate)

        input_names = [f"食品{i}" for i in range(120)]
        results = await generate_display_names(input_names, batch_size=50)

        assert call_count == 3
        assert len(results) == 120
        # 全て None でない（元名と異なるので valid）
        assert all(r is not None for r in results)

    async def test_empty_input(self, mock_settings, mock_genai_client):
        """空リスト入力。"""
        results = await generate_display_names([])
        assert results == []

    async def test_no_api_key(self, mock_genai_client):
        """API キー未設定。"""
        with patch("app.services.gemini_display_name.settings") as mock:
            mock.google_api_key = ""
            results = await generate_display_names(["name1"])
            assert results == [None]
