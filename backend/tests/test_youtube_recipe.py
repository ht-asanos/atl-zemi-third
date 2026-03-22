"""YouTube レシピ取込のテスト（正常系・信頼性ゲート・異常系）"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from app.services.youtube_recipe import (
    _parse_gemini_json,
    _validate_extracted_recipe,
    adapt_recipe_to_staple,
    extract_recipe_from_media,
    extract_recipe_with_fallback,
    fetch_channel_video_ids,
    fetch_channel_videos_by_query,
    fetch_youtube_recipes,
    resolve_channel_id,
)

# ---------------------------------------------------------------------------
# テストデータ
# ---------------------------------------------------------------------------

VALID_RECIPE = {
    "title": "親子丼",
    "servings": 2,
    "cooking_minutes": 15,
    "ingredients": [
        {"ingredient_name": "鶏もも肉", "amount_text": "300g"},
        {"ingredient_name": "玉ねぎ", "amount_text": "1/2個"},
        {"ingredient_name": "卵", "amount_text": "3個"},
        {"ingredient_name": "醤油", "amount_text": "大さじ2"},
        {"ingredient_name": "みりん", "amount_text": "大さじ1"},
    ],
    "steps": [
        {"step_no": 1, "text": "鶏肉を一口大に切る", "est_minutes": 3},
        {"step_no": 2, "text": "玉ねぎを薄切りにする", "est_minutes": 2},
        {"step_no": 3, "text": "フライパンで鶏肉を炒める", "est_minutes": 5},
    ],
    "tags": ["鶏肉", "和食", "丼"],
}


def _yt_channels_response(channel_id: str) -> dict:
    return {"items": [{"id": channel_id}]}


def _yt_search_channel_response(channel_id: str) -> dict:
    return {"items": [{"snippet": {"channelId": channel_id}}]}


def _yt_search_videos_response(video_ids: list[str]) -> dict:
    items = []
    for vid in video_ids:
        items.append(
            {
                "id": {"videoId": vid},
                "snippet": {"title": f"Video {vid}", "publishedAt": "2024-01-01T00:00:00Z"},
            }
        )
    return {"items": items}


def _mock_httpx_response(status_code: int, json_data: dict) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=json_data,
        request=httpx.Request("GET", "https://example.com"),
    )


# ---------------------------------------------------------------------------
# 正常系: チャンネル解決
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_channel_id_by_handle():
    """channels.list(forHandle) 成功パス"""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_httpx_response(200, _yt_channels_response("UC_test123")))

    result = await resolve_channel_id(client, "fake_key", "@Kurashiru")
    assert result == "UC_test123"


@pytest.mark.asyncio
async def test_resolve_channel_id_fallback_to_search():
    """forHandle 失敗 → search.list フォールバック"""
    empty_response = _mock_httpx_response(200, {"items": []})
    search_response = _mock_httpx_response(200, _yt_search_channel_response("UC_fallback456"))

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=[empty_response, search_response])

    result = await resolve_channel_id(client, "fake_key", "@Kurashiru")
    assert result == "UC_fallback456"


@pytest.mark.asyncio
async def test_resolve_channel_id_both_fail():
    """両方失敗で None 返却"""
    empty = _mock_httpx_response(200, {"items": []})

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=empty)

    result = await resolve_channel_id(client, "fake_key", "@Unknown")
    assert result is None


# ---------------------------------------------------------------------------
# 正常系: 動画一覧取得
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_channel_video_ids():
    """search.list レスポンスパース"""
    resp_data = _yt_search_videos_response(["vid1", "vid2", "vid3"])
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_httpx_response(200, resp_data))

    result = await fetch_channel_video_ids(client, "fake_key", "UC_test123", max_results=3)
    assert len(result) == 3
    assert result[0]["video_id"] == "vid1"
    assert result[1]["video_id"] == "vid2"
    assert "title" in result[0]
    assert "published_at" in result[0]


@pytest.mark.asyncio
async def test_fetch_channel_video_ids_skips_shorts():
    """#shorts を含む動画は候補から除外する。"""
    resp_data = {
        "items": [
            {
                "id": {"videoId": "vid_short"},
                "snippet": {"title": "【Shorts】3分うどん", "publishedAt": "2024-01-01T00:00:00Z"},
            },
            {
                "id": {"videoId": "vid_normal"},
                "snippet": {"title": "10分で作る肉うどん", "publishedAt": "2024-01-02T00:00:00Z"},
            },
        ]
    }
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_httpx_response(200, resp_data))

    result = await fetch_channel_video_ids(client, "fake_key", "UC_test123", max_results=5)
    assert [r["video_id"] for r in result] == ["vid_normal"]


@pytest.mark.asyncio
async def test_fetch_channel_videos_by_query_skips_shorts():
    """query 検索でも Shorts を除外する。"""
    resp_data = {
        "items": [
            {
                "id": {"videoId": "vid1"},
                "snippet": {"title": "パスタ #shorts", "publishedAt": "2024-01-01T00:00:00Z"},
            },
            {
                "id": {"videoId": "vid2"},
                "snippet": {"title": "本格パスタ", "publishedAt": "2024-01-02T00:00:00Z"},
            },
        ]
    }
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_httpx_response(200, resp_data))

    result = await fetch_channel_videos_by_query(
        client,
        "fake_key",
        "UC_test123",
        query="パスタ",
        max_results=10,
    )
    assert [r["video_id"] for r in result] == ["vid2"]


# ---------------------------------------------------------------------------
# 正常系: JSON パース・信頼性ゲート
# ---------------------------------------------------------------------------


def test_extract_recipe_json_parsing():
    """Gemini レスポンスからの JSON 抽出"""
    text = f"```json\n{json.dumps(VALID_RECIPE, ensure_ascii=False)}\n```"
    result = _parse_gemini_json(text)
    assert result is not None
    assert result["title"] == "親子丼"
    assert len(result["ingredients"]) == 5


def test_extract_recipe_json_no_codeblock():
    """コードブロックなしの生 JSON"""
    text = json.dumps(VALID_RECIPE, ensure_ascii=False)
    result = _parse_gemini_json(text)
    assert result is not None
    assert result["title"] == "親子丼"


def test_extract_recipe_ingredients_format():
    """抽出された ingredients が既存パイプライン互換"""
    for ing in VALID_RECIPE["ingredients"]:
        assert "ingredient_name" in ing
        assert isinstance(ing["ingredient_name"], str)
        assert len(ing["ingredient_name"]) > 0


# ---------------------------------------------------------------------------
# 正常系: レシピソースフィールド
# ---------------------------------------------------------------------------


def test_recipe_source_field():
    """YouTube レシピは recipe_source='youtube'"""
    recipe_dict = {
        "youtube_video_id": "abc123",
        "recipe_source": "youtube",
        "title": "テスト",
        "recipe_url": "https://www.youtube.com/watch?v=abc123",
    }
    assert recipe_dict["recipe_source"] == "youtube"


def test_existing_recipes_default_source():
    """既存レシピは recipe_source='rakuten'"""
    recipe_dict = {
        "rakuten_recipe_id": 12345,
        "title": "テスト",
        "recipe_url": "https://recipe.rakuten.co.jp/test",
    }
    assert recipe_dict.get("recipe_source", "rakuten") == "rakuten"


# ---------------------------------------------------------------------------
# 正常系: 主食適応
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_adapt_recipe_to_staple_success():
    """主食適応で ingredients に主食が含まれるレシピを返す。"""
    adapted = {
        **VALID_RECIPE,
        "title": "親子うどん",
        "ingredients": VALID_RECIPE["ingredients"] + [{"ingredient_name": "うどん", "amount_text": "2玉"}],
    }

    mock_client = MagicMock()
    resp = MagicMock()
    resp.text = json.dumps(adapted, ensure_ascii=False)
    mock_client.models.generate_content.return_value = resp

    with patch("app.services.youtube_gemini.genai.Client", return_value=mock_client):
        result = await adapt_recipe_to_staple(VALID_RECIPE, "うどん")

    assert result is not None
    assert any(i["ingredient_name"] == "うどん" for i in result["ingredients"])


@pytest.mark.asyncio
async def test_adapt_recipe_to_staple_fail_when_no_staple():
    """主食が反映されない出力は破棄される。"""
    mock_client = MagicMock()
    resp = MagicMock()
    resp.text = json.dumps(VALID_RECIPE, ensure_ascii=False)
    mock_client.models.generate_content.return_value = resp

    with patch("app.services.youtube_gemini.genai.Client", return_value=mock_client):
        with patch("app.services.youtube_gemini.GEMINI_RETRY_WAIT", 0.01):
            result = await adapt_recipe_to_staple(VALID_RECIPE, "うどん")

    assert result is None


# ---------------------------------------------------------------------------
# 信頼性ゲート
# ---------------------------------------------------------------------------


def test_validate_empty_ingredients_rejected():
    """ingredients=[] → 破棄"""
    data = {**VALID_RECIPE, "ingredients": []}
    assert _validate_extracted_recipe(data) is False


def test_validate_empty_title_rejected():
    """title="" → 破棄"""
    data = {**VALID_RECIPE, "title": ""}
    assert _validate_extracted_recipe(data) is False


def test_validate_no_steps_rejected():
    """steps=[] → 破棄"""
    data = {**VALID_RECIPE, "steps": []}
    assert _validate_extracted_recipe(data) is False


def test_validate_valid_recipe_accepted():
    """正常データ → 通過"""
    assert _validate_extracted_recipe(VALID_RECIPE) is True


def test_validate_ingredient_empty_name_rejected():
    """ingredient_name が空の食材 → 破棄"""
    data = {
        **VALID_RECIPE,
        "ingredients": [{"ingredient_name": "", "amount_text": "100g"}],
    }
    assert _validate_extracted_recipe(data) is False


def test_validate_step_empty_text_rejected():
    """step.text が空 → 破棄"""
    data = {
        **VALID_RECIPE,
        "steps": [{"step_no": 1, "text": ""}],
    }
    assert _validate_extracted_recipe(data) is False


def test_validate_none_title_rejected():
    """title=None → 破棄"""
    data = {**VALID_RECIPE, "title": None}
    assert _validate_extracted_recipe(data) is False


# ---------------------------------------------------------------------------
# 異常系: Gemini リトライ
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gemini_broken_json_retry():
    """壊れた JSON → リトライ → 成功"""
    valid_json = json.dumps(VALID_RECIPE, ensure_ascii=False)

    mock_file = MagicMock()
    mock_file.state.name = "ACTIVE"
    mock_file.name = "files/test"

    mock_client = MagicMock()
    mock_client.files.upload.return_value = mock_file
    mock_client.files.get.return_value = mock_file
    mock_client.files.delete.return_value = None

    # 1回目: 壊れた JSON、2回目: 正常
    broken_resp = MagicMock()
    broken_resp.text = "{ broken json"
    valid_resp = MagicMock()
    valid_resp.text = valid_json
    mock_client.models.generate_content.side_effect = [broken_resp, valid_resp]

    with patch("app.services.youtube_gemini.genai.Client", return_value=mock_client):
        with patch("app.services.youtube_gemini.GEMINI_RETRY_WAIT", 0.01):
            result = await extract_recipe_from_media(Path("/tmp/test.m4a"))

    assert result is not None
    assert result["title"] == "親子丼"
    assert mock_client.models.generate_content.call_count == 2


@pytest.mark.asyncio
async def test_gemini_all_retries_failed():
    """全リトライ失敗 → None 返却"""
    mock_file = MagicMock()
    mock_file.state.name = "ACTIVE"
    mock_file.name = "files/test"

    mock_client = MagicMock()
    mock_client.files.upload.return_value = mock_file
    mock_client.files.get.return_value = mock_file
    mock_client.files.delete.return_value = None

    broken_resp = MagicMock()
    broken_resp.text = "not json at all"
    mock_client.models.generate_content.return_value = broken_resp

    with patch("app.services.youtube_gemini.genai.Client", return_value=mock_client):
        with patch("app.services.youtube_gemini.GEMINI_RETRY_WAIT", 0.01):
            result = await extract_recipe_from_media(Path("/tmp/test.m4a"))

    assert result is None


@pytest.mark.asyncio
async def test_gemini_file_cleanup():
    """処理後にアップロードファイル削除される"""
    valid_json = json.dumps(VALID_RECIPE, ensure_ascii=False)

    mock_file = MagicMock()
    mock_file.state.name = "ACTIVE"
    mock_file.name = "files/test123"

    mock_client = MagicMock()
    mock_client.files.upload.return_value = mock_file
    mock_client.files.get.return_value = mock_file
    mock_client.files.delete.return_value = None

    valid_resp = MagicMock()
    valid_resp.text = valid_json
    mock_client.models.generate_content.return_value = valid_resp

    with patch("app.services.youtube_gemini.genai.Client", return_value=mock_client):
        await extract_recipe_from_media(Path("/tmp/test.m4a"))

    mock_client.files.delete.assert_called_once_with(name="files/test123")


# ---------------------------------------------------------------------------
# 異常系: yt-dlp
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ytdlp_failure_continues_next():
    """yt-dlp 失敗 → 次の動画へ継続"""
    client = AsyncMock(spec=httpx.AsyncClient)

    # チャンネル解決成功
    client.get = AsyncMock(
        side_effect=[
            _mock_httpx_response(200, _yt_channels_response("UC_test")),
            _mock_httpx_response(200, _yt_search_videos_response(["vid1", "vid2"])),
        ]
    )

    # extract_recipe_with_fallback: vid1 失敗, vid2 成功
    async def mock_extract(video_id, tmp_dir):
        if video_id == "vid1":
            return None  # 失敗
        return VALID_RECIPE

    with patch("app.services.youtube_recipe.extract_recipe_with_fallback", side_effect=mock_extract):
        recipes, stats = await fetch_youtube_recipes(client, "fake_key", "@Test", max_results=2)

    assert len(recipes) == 1
    assert stats["extraction_success"] == 1
    assert stats["extraction_failed"] == 1


# ---------------------------------------------------------------------------
# 異常系: quota 超過
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quota_exceeded_graceful_stop():
    """403 エラー → 処理済み分を返却して停止"""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=_mock_httpx_response(403, {"error": {"code": 403}}))

    recipes, stats = await fetch_youtube_recipes(client, "fake_key", "@Test", max_results=5)
    assert len(recipes) == 0
    assert stats["videos_found"] == 0


# ---------------------------------------------------------------------------
# 異常系: フォールバック
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audio_fallback_to_video():
    """音声抽出で信頼性ゲート不合格 → 動画フォールバック"""
    # download_video_audio → ファイルあり
    # extract_recipe_from_media(audio) → None (ゲート不合格)
    # download_video_lowres → ファイルあり
    # extract_recipe_from_media(video) → 成功

    call_count = {"extract": 0}

    async def mock_download_audio(vid, out):
        return Path("/tmp/fake_audio.m4a")

    async def mock_download_video(vid, out):
        return Path("/tmp/fake_video.mp4")

    async def mock_extract(media_path):
        call_count["extract"] += 1
        if call_count["extract"] == 1:
            return None  # 音声: ゲート不合格
        return VALID_RECIPE  # 動画: 成功

    with (
        patch("app.services.youtube_recipe.download_video_audio", side_effect=mock_download_audio),
        patch("app.services.youtube_recipe.download_video_lowres", side_effect=mock_download_video),
        patch("app.services.youtube_recipe.extract_recipe_from_media", side_effect=mock_extract),
    ):
        result = await extract_recipe_with_fallback("test_vid", Path("/tmp"))

    assert result is not None
    assert result["title"] == "親子丼"
    assert call_count["extract"] == 2


# ---------------------------------------------------------------------------
# オーケストレーター: 統合テスト
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_youtube_recipes_full_flow():
    """正常フロー全体（チャンネル解決→動画取得→抽出→結果返却）"""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(
        side_effect=[
            _mock_httpx_response(200, _yt_channels_response("UC_kurashiru")),
            _mock_httpx_response(200, _yt_search_videos_response(["vid_a", "vid_b"])),
        ]
    )

    async def mock_extract(video_id, tmp_dir):
        return VALID_RECIPE

    with patch("app.services.youtube_recipe.extract_recipe_with_fallback", side_effect=mock_extract):
        recipes, stats = await fetch_youtube_recipes(client, "fake_key", "@Kurashiru", max_results=2)

    assert len(recipes) == 2
    assert stats["extraction_success"] == 2
    assert stats["extraction_failed"] == 0
    assert stats["channel"] == "@Kurashiru"

    # 返却形式チェック
    r = recipes[0]
    assert r["recipe_source"] == "youtube"
    assert r["youtube_video_id"] == "vid_a"
    assert "YouTube" in r["tags"]
    assert "Kurashiru" in r["tags"]
    assert r["recipe_url"].startswith("https://www.youtube.com/watch?v=")
    assert len(r["ingredients"]) == 5


@pytest.mark.asyncio
async def test_fetch_youtube_recipes_exclude_existing():
    """既知 video_id はスキップされる"""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(
        side_effect=[
            _mock_httpx_response(200, _yt_channels_response("UC_test")),
            _mock_httpx_response(200, _yt_search_videos_response(["vid1", "vid2", "vid3"])),
        ]
    )

    async def mock_extract(video_id, tmp_dir):
        return VALID_RECIPE

    with patch("app.services.youtube_recipe.extract_recipe_with_fallback", side_effect=mock_extract):
        recipes, stats = await fetch_youtube_recipes(
            client,
            "fake_key",
            "@Test",
            max_results=3,
            exclude_video_ids=["vid1", "vid3"],
        )

    assert len(recipes) == 1
    assert recipes[0]["youtube_video_id"] == "vid2"
    assert stats["videos_skipped_existing"] == 2
    assert stats["videos_processed"] == 1


@pytest.mark.asyncio
async def test_fetch_youtube_recipes_with_staple_adaptation():
    """staple_name 指定時に主食適応が呼ばれ、タグに残る。"""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(
        side_effect=[
            _mock_httpx_response(200, _yt_channels_response("UC_test")),
            _mock_httpx_response(200, _yt_search_videos_response(["vid1"])),
        ]
    )

    adapted = {
        **VALID_RECIPE,
        "title": "親子うどん",
        "ingredients": VALID_RECIPE["ingredients"] + [{"ingredient_name": "うどん", "amount_text": "2玉"}],
        "steps": VALID_RECIPE["steps"],
    }

    with (
        patch("app.services.youtube_recipe.extract_recipe_with_fallback", new=AsyncMock(return_value=VALID_RECIPE)),
        patch("app.services.youtube_recipe.adapt_recipe_to_staple", new=AsyncMock(return_value=adapted)),
    ):
        recipes, stats = await fetch_youtube_recipes(
            client,
            "fake_key",
            "@Test",
            max_results=1,
            staple_name="うどん",
        )

    assert len(recipes) == 1
    assert "staple:うどん" in recipes[0]["tags"]
    assert stats["adaptation_attempted"] == 1
    assert stats["adaptation_success"] == 1
    assert stats["adaptation_failed"] == 0


@pytest.mark.asyncio
async def test_fetch_youtube_recipes_with_staple_adaptation_failed_skips_recipe():
    """主食適応に失敗した動画は登録対象からスキップする。"""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(
        side_effect=[
            _mock_httpx_response(200, _yt_channels_response("UC_test")),
            _mock_httpx_response(200, _yt_search_videos_response(["vid1"])),
        ]
    )

    with (
        patch("app.services.youtube_recipe.extract_recipe_with_fallback", new=AsyncMock(return_value=VALID_RECIPE)),
        patch("app.services.youtube_recipe.adapt_recipe_to_staple", new=AsyncMock(return_value=None)),
    ):
        recipes, stats = await fetch_youtube_recipes(
            client,
            "fake_key",
            "@Test",
            max_results=1,
            staple_name="うどん",
        )

    assert recipes == []
    assert stats["adaptation_attempted"] == 1
    assert stats["adaptation_success"] == 0
    assert stats["adaptation_failed"] == 1
    assert stats["videos_skipped_staple_unmatched"] == 1


# ---------------------------------------------------------------------------
# バッチ Gemini ゲートテスト
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_youtube_recipes_batch_filters_non_meal():
    """収集後のバッチ判定で非食事レシピが除外される。"""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(
        side_effect=[
            _mock_httpx_response(200, _yt_channels_response("UC_test")),
            _mock_httpx_response(200, _yt_search_videos_response(["vid1", "vid2"])),
        ]
    )

    non_meal_recipe = dict(VALID_RECIPE)
    non_meal_recipe["title"] = "うどんのつけ汁"

    call_count = 0

    async def _extract_side_effect(video_id, tmp_dir):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return VALID_RECIPE
        return non_meal_recipe

    gate_result_mock = MagicMock()
    gate_result_mock.accepted = [{"title": "親子丼", "youtube_video_id": "vid1"}]
    gate_result_mock.rejected = [{"recipe": {"title": "うどんのつけ汁"}, "reason": "sauce only"}]

    with (
        patch(
            "app.services.youtube_recipe.extract_recipe_with_fallback",
            new=AsyncMock(side_effect=_extract_side_effect),
        ),
        patch(
            "app.services.youtube_recipe.filter_meal_like_recipes_safe",
            new=AsyncMock(return_value=gate_result_mock),
        ),
    ):
        recipes, stats = await fetch_youtube_recipes(
            client,
            "fake_key",
            "@Test",
            max_results=2,
        )

    assert len(recipes) == 1
    assert recipes[0]["title"] == "親子丼"


@pytest.mark.asyncio
async def test_fetch_youtube_recipes_batch_no_filter_when_no_recipes():
    """レシピが0件のときはゲートを呼ばない（エラーなし）。"""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(
        side_effect=[
            _mock_httpx_response(200, _yt_channels_response("UC_test")),
            _mock_httpx_response(200, _yt_search_videos_response(["vid1"])),
        ]
    )

    with (
        patch("app.services.youtube_recipe.extract_recipe_with_fallback", new=AsyncMock(return_value=None)),
        patch("app.services.youtube_recipe.filter_meal_like_recipes_safe") as mock_gate,
    ):
        recipes, stats = await fetch_youtube_recipes(
            client,
            "fake_key",
            "@Test",
            max_results=1,
        )

    assert recipes == []
    mock_gate.assert_not_called()
