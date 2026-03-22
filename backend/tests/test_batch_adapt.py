"""POST /admin/youtube/batch-adapt テスト"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.data.food_master import STAPLE_TAG_MAP
from app.models.food import NutritionStatus
from app.models.recipe import Recipe
from app.repositories.recipe_repo import _matches_staple_filter
from app.schemas.youtube_admin import BatchAdaptRequest

# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------

ADMIN_USER_ID = uuid4()


def _mock_admin_deps():
    return patch("app.routers.admin_youtube.get_admin_user_id", return_value=ADMIN_USER_ID)


def _make_video(video_id: str, title: str) -> dict:
    return {"video_id": video_id, "title": title, "published_at": "2026-01-01T00:00:00Z"}


def _make_extracted_recipe() -> dict:
    return {
        "title": "明太パスタ",
        "servings": 2,
        "cooking_minutes": 15,
        "ingredients": [
            {"ingredient_name": "パスタ", "amount_text": "200g"},
            {"ingredient_name": "明太子", "amount_text": "1腹"},
        ],
        "steps": [{"step_no": 1, "text": "パスタを茹でる", "est_minutes": 10}],
        "tags": ["パスタ", "和風"],
    }


def _make_adapted_recipe() -> dict:
    return {
        "title": "明太うどん",
        "servings": 2,
        "cooking_minutes": 10,
        "ingredients": [
            {"ingredient_name": "うどん", "amount_text": "2玉"},
            {"ingredient_name": "明太子", "amount_text": "1腹"},
        ],
        "steps": [{"step_no": 1, "text": "うどんを茹でる", "est_minutes": 5}],
        "tags": ["うどん", "和風"],
    }


def _mock_supabase_no_existing():
    """既存レシピなしの Supabase モック。"""
    mock_sb = MagicMock()
    mock_select = MagicMock()
    mock_eq = MagicMock()
    mock_eq.execute = AsyncMock(return_value=MagicMock(data=[]))
    mock_select.eq = MagicMock(return_value=mock_eq)
    mock_sb.table.return_value.select = MagicMock(return_value=mock_select)
    return mock_sb


def _base_mocks():
    """全外部呼び出しをモックするコンテキストマネージャをまとめて返す。"""
    return {
        "resolve": patch("app.routers.admin_youtube.resolve_channel_id"),
        "fetch_videos": patch("app.routers.admin_youtube.fetch_channel_videos_by_query"),
        "transcript": patch("app.routers.admin_youtube.fetch_transcript"),
        "naturalize": patch("app.routers.admin_youtube.naturalize_auto_transcript"),
        "extract": patch("app.routers.admin_youtube.extract_recipe_from_transcript_text"),
        "adapt": patch("app.routers.admin_youtube.adapt_recipe_to_staple"),
        "upsert": patch("app.routers.admin_youtube.recipe_repo.upsert_recipe"),
        "match": patch("app.routers.admin_youtube.match_recipe_ingredients"),
        "nutrition": patch("app.routers.admin_youtube.calculate_recipe_nutrition"),
        "sleep": patch("app.routers.admin_youtube.asyncio.sleep", new_callable=AsyncMock),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_max_results_over_10():
    """max_results > 10 → AppException(422)。"""
    from app.exceptions import AppException
    from app.routers.admin_youtube import youtube_batch_adapt

    mock_sb = _mock_supabase_no_existing()
    body = BatchAdaptRequest(
        channel_handle="@yugetube2020",
        source_query="パスタ",
        target_staple="冷凍うどん",
        max_results=11,
    )
    with _mock_admin_deps():
        with pytest.raises(AppException) as exc_info:
            await youtube_batch_adapt(body=body, user_id=ADMIN_USER_ID, supabase=mock_sb)
        assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_unknown_target_staple():
    """不明な target_staple → AppException(422)。"""
    from app.exceptions import AppException
    from app.routers.admin_youtube import youtube_batch_adapt

    mock_sb = _mock_supabase_no_existing()
    body = BatchAdaptRequest(
        channel_handle="@yugetube2020",
        source_query="パスタ",
        target_staple="そば",
        max_results=3,
    )
    with _mock_admin_deps():
        with pytest.raises(AppException) as exc_info:
            await youtube_batch_adapt(body=body, user_id=ADMIN_USER_ID, supabase=mock_sb)
        assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_normal_flow_2_success_1_fail():
    """正常系: 3動画中 2成功 1失敗。"""
    from app.routers.admin_youtube import youtube_batch_adapt

    mock_sb = _mock_supabase_no_existing()
    mocks = _base_mocks()

    with (
        _mock_admin_deps(),
        mocks["resolve"] as m_resolve,
        mocks["fetch_videos"] as m_videos,
        mocks["transcript"] as m_transcript,
        mocks["naturalize"],
        mocks["extract"] as m_extract,
        mocks["adapt"] as m_adapt,
        mocks["upsert"] as m_upsert,
        mocks["match"] as m_match,
        mocks["nutrition"] as m_nutrition,
        mocks["sleep"],
    ):
        m_resolve.return_value = "UC_FAKE_CHANNEL"
        m_videos.return_value = [
            _make_video("aaaaaaaaaaa", "明太パスタ"),
            _make_video("bbbbbbbbbbb", "ナポリタン"),
            _make_video("ccccccccccc", "カルボナーラ"),
        ]

        async def _transcript_side_effect(url, **kwargs):
            if "bbbbbbbbbbb" in url:
                raise RuntimeError("no transcript")
            return {"text": "テスト字幕", "is_generated": False}

        m_transcript.side_effect = _transcript_side_effect
        m_extract.return_value = _make_extracted_recipe()
        m_adapt.return_value = _make_adapted_recipe()
        m_upsert.side_effect = [uuid4(), uuid4()]
        m_match.return_value = None
        m_nutrition.return_value = MagicMock(status=NutritionStatus.CALCULATED)

        body = BatchAdaptRequest(
            channel_handle="@yugetube2020",
            source_query="パスタ",
            target_staple="冷凍うどん",
            max_results=3,
        )
        result = await youtube_batch_adapt(body=body, user_id=ADMIN_USER_ID, supabase=mock_sb)

    assert result.succeeded == 2
    assert result.failed == 1
    assert result.videos_processed == 3
    assert len(result.results) == 3

    statuses = {r.video_id: r.status for r in result.results}
    assert statuses["aaaaaaaaaaa"] == "success"
    assert statuses["bbbbbbbbbbb"] == "no_transcript"
    assert statuses["ccccccccccc"] == "success"


@pytest.mark.asyncio
async def test_tags_contain_udon_and_arrange():
    """成功レシピのタグに 'うどん' と 'アレンジ:パスタ→うどん' が含まれること。"""
    from app.routers.admin_youtube import youtube_batch_adapt

    mock_sb = _mock_supabase_no_existing()
    mocks = _base_mocks()

    with (
        _mock_admin_deps(),
        mocks["resolve"] as m_resolve,
        mocks["fetch_videos"] as m_videos,
        mocks["transcript"] as m_transcript,
        mocks["naturalize"],
        mocks["extract"] as m_extract,
        mocks["adapt"] as m_adapt,
        mocks["upsert"] as m_upsert,
        mocks["match"] as m_match,
        mocks["nutrition"] as m_nutrition,
        mocks["sleep"],
    ):
        m_resolve.return_value = "UC_FAKE"
        m_videos.return_value = [_make_video("aaaaaaaaaaa", "明太パスタ")]
        m_transcript.return_value = {"text": "テスト", "is_generated": False}
        m_extract.return_value = _make_extracted_recipe()
        m_adapt.return_value = _make_adapted_recipe()
        m_upsert.return_value = uuid4()
        m_match.return_value = None
        m_nutrition.return_value = MagicMock(status=NutritionStatus.CALCULATED)

        body = BatchAdaptRequest(
            channel_handle="@yugetube2020",
            source_query="パスタ",
            target_staple="冷凍うどん",
        )
        await youtube_batch_adapt(body=body, user_id=ADMIN_USER_ID, supabase=mock_sb)

    call_args = m_upsert.call_args
    recipe_dict = call_args[0][1]  # (supabase, recipe_dict)
    tags = recipe_dict["tags"]
    assert "うどん" in tags
    assert "アレンジ:パスタ→うどん" in tags
    assert "staple:冷凍うどん" in tags
    assert "YouTube" in tags


@pytest.mark.asyncio
async def test_skips_existing_video_ids():
    """既存 video_id がスキップされること。"""
    from app.routers.admin_youtube import youtube_batch_adapt

    # Supabase mock: existing_vid が既に登録済み
    mock_sb = MagicMock()
    mock_select = MagicMock()
    mock_eq = MagicMock()
    mock_eq.execute = AsyncMock(return_value=MagicMock(data=[{"youtube_video_id": "eeeeeeeeeee"}]))
    mock_select.eq = MagicMock(return_value=mock_eq)
    mock_sb.table.return_value.select = MagicMock(return_value=mock_select)

    mocks = _base_mocks()
    with (
        _mock_admin_deps(),
        mocks["resolve"] as m_resolve,
        mocks["fetch_videos"] as m_videos,
        mocks["transcript"] as m_transcript,
        mocks["naturalize"],
        mocks["extract"] as m_extract,
        mocks["adapt"] as m_adapt,
        mocks["upsert"] as m_upsert,
        mocks["match"] as m_match,
        mocks["nutrition"] as m_nutrition,
        mocks["sleep"],
    ):
        m_resolve.return_value = "UC_FAKE"
        m_videos.return_value = [
            _make_video("eeeeeeeeeee", "既存パスタ"),
            _make_video("nnnnnnnnnnn", "新しいパスタ"),
        ]
        m_transcript.return_value = {"text": "テスト", "is_generated": False}
        m_extract.return_value = _make_extracted_recipe()
        m_adapt.return_value = _make_adapted_recipe()
        m_upsert.return_value = uuid4()
        m_match.return_value = None
        m_nutrition.return_value = MagicMock(status=NutritionStatus.CALCULATED)

        body = BatchAdaptRequest(
            channel_handle="@yugetube2020",
            source_query="パスタ",
            target_staple="冷凍うどん",
            max_results=3,
        )
        result = await youtube_batch_adapt(body=body, user_id=ADMIN_USER_ID, supabase=mock_sb)

    assert result.skipped == 1
    assert result.succeeded == 1
    statuses = {r.video_id: r.status for r in result.results}
    assert statuses["eeeeeeeeeee"] == "skipped_existing"
    assert statuses["nnnnnnnnnnn"] == "success"


def test_staple_filter_matches_adapted_recipe():
    """アレンジ済みレシピのタグが _matches_staple_filter で True になること。"""
    tags = ["YouTube", "yugetube2020", "うどん", "アレンジ:パスタ→うどん", "staple:冷凍うどん"]
    recipe = Recipe(
        id=uuid4(),
        title="明太うどん",
        recipe_url="https://www.youtube.com/watch?v=test",
        tags=tags,
    )
    staple_tags = STAPLE_TAG_MAP["冷凍うどん"]
    assert _matches_staple_filter(recipe, staple_tags, None) is True


@pytest.mark.asyncio
async def test_extract_called_with_empty_staple_name():
    """extract_recipe_from_transcript_text が staple_name='' で呼ばれること（レビュー #4）。"""
    from app.routers.admin_youtube import youtube_batch_adapt

    mock_sb = _mock_supabase_no_existing()
    mocks = _base_mocks()

    with (
        _mock_admin_deps(),
        mocks["resolve"] as m_resolve,
        mocks["fetch_videos"] as m_videos,
        mocks["transcript"] as m_transcript,
        mocks["naturalize"],
        mocks["extract"] as m_extract,
        mocks["adapt"] as m_adapt,
        mocks["upsert"] as m_upsert,
        mocks["match"] as m_match,
        mocks["nutrition"] as m_nutrition,
        mocks["sleep"],
    ):
        m_resolve.return_value = "UC_FAKE"
        m_videos.return_value = [_make_video("aaaaaaaaaaa", "パスタ")]
        m_transcript.return_value = {"text": "テスト", "is_generated": False}
        m_extract.return_value = _make_extracted_recipe()
        m_adapt.return_value = _make_adapted_recipe()
        m_upsert.return_value = uuid4()
        m_match.return_value = None
        m_nutrition.return_value = MagicMock(status=NutritionStatus.CALCULATED)

        body = BatchAdaptRequest(
            channel_handle="@yugetube2020",
            source_query="パスタ",
            target_staple="冷凍うどん",
        )
        await youtube_batch_adapt(body=body, user_id=ADMIN_USER_ID, supabase=mock_sb)

    # staple_name="" で呼ばれたことを確認
    m_extract.assert_called_once()
    _, kwargs = m_extract.call_args
    assert kwargs.get("staple_name") == ""


@pytest.mark.asyncio
async def test_migration_014_fallback():
    """migration 014 未適用時の重複チェックが recipe_url フォールバックで動作すること。"""
    from app.routers.admin_youtube import youtube_batch_adapt
    from postgrest.exceptions import APIError

    mock_sb = MagicMock()

    def _mock_select(columns):
        mock_chain = MagicMock()
        if "youtube_video_id" in columns:
            mock_eq = MagicMock()
            mock_eq.execute = AsyncMock(side_effect=APIError({"message": "column youtube_video_id does not exist"}))
            mock_chain.eq = MagicMock(return_value=mock_eq)
        else:
            mock_ilike = MagicMock()
            mock_ilike.execute = AsyncMock(
                return_value=MagicMock(data=[{"recipe_url": "https://www.youtube.com/watch?v=aaaaaaaaaaa"}])
            )
            mock_chain.ilike = MagicMock(return_value=mock_ilike)
        return mock_chain

    mock_sb.table.return_value.select = _mock_select

    mocks = _base_mocks()
    with (
        _mock_admin_deps(),
        mocks["resolve"] as m_resolve,
        mocks["fetch_videos"] as m_videos,
        mocks["transcript"],
        mocks["naturalize"],
        mocks["extract"],
        mocks["adapt"],
        mocks["upsert"],
        mocks["match"],
        mocks["nutrition"],
        mocks["sleep"],
    ):
        m_resolve.return_value = "UC_FAKE"
        m_videos.return_value = [_make_video("aaaaaaaaaaa", "パスタ")]

        body = BatchAdaptRequest(
            channel_handle="@yugetube2020",
            source_query="パスタ",
            target_staple="冷凍うどん",
            max_results=1,
        )
        result = await youtube_batch_adapt(body=body, user_id=ADMIN_USER_ID, supabase=mock_sb)

    # vid1 は既存 URL にマッチするのでスキップされるべき
    assert result.skipped == 1
    statuses = {r.video_id: r.status for r in result.results}
    assert statuses["aaaaaaaaaaa"] == "skipped_existing"
