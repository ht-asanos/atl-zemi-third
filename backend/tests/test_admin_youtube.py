"""YouTube 管理エンドポイントのテスト。"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.models.food import NutritionStatus
from app.services.ingredient_matcher import NutritionResult
from postgrest.exceptions import APIError

ADMIN_USER_ID = uuid4()


def _mock_admin_deps():
    """管理者認証をモックするコンテキストマネージャのセット。"""
    return patch("app.routers.admin_youtube.get_admin_user_id", return_value=ADMIN_USER_ID)


@pytest.fixture
def mock_supabase():
    return MagicMock()


# --- extract ---


@pytest.mark.asyncio
async def test_youtube_extract_success(mock_supabase):
    """正常な URL でレシピ抽出が成功する。"""
    transcript_data = {
        "video_id": "dQw4w9WgXcQ",
        "language_code": "ja",
        "language": "日本語",
        "is_generated": False,
        "entries": [{"text": "鶏肉を切ります", "start": 0, "duration": 3}],
        "text": "鶏肉を切ります",
        "quality": {"quality_score": 80},
    }
    extracted_recipe = {
        "title": "鶏の照り焼き",
        "servings": 2,
        "cooking_minutes": 20,
        "ingredients": [
            {"ingredient_name": "鶏もも肉", "amount_text": "300g"},
            {"ingredient_name": "醤油", "amount_text": "大さじ2"},
        ],
        "steps": [
            {"step_no": 1, "text": "鶏肉を一口大に切る", "est_minutes": 3},
        ],
        "tags": ["鶏肉", "和食"],
    }

    with (
        _mock_admin_deps(),
        patch("app.routers.admin_youtube.extract_video_id", return_value="dQw4w9WgXcQ"),
        patch("app.routers.admin_youtube.fetch_transcript", return_value=transcript_data),
        patch("app.routers.admin_youtube.assess_transcript_quality", return_value={"quality_score": 80}),
        patch("app.routers.admin_youtube.extract_recipe_from_transcript_text", return_value=extracted_recipe),
    ):
        from app.routers.admin_youtube import youtube_extract
        from app.schemas.youtube_admin import YoutubeExtractRequest

        result = await youtube_extract(
            body=YoutubeExtractRequest(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            user_id=ADMIN_USER_ID,
            supabase=mock_supabase,
        )
        assert result.video_id == "dQw4w9WgXcQ"
        assert result.recipe_draft.title == "鶏の照り焼き"
        assert len(result.recipe_draft.ingredients) == 2
        assert len(result.recipe_draft.steps) == 1


@pytest.mark.asyncio
async def test_youtube_extract_invalid_url(mock_supabase):
    """無効な URL なら 422。"""
    from app.exceptions import AppException

    with (
        _mock_admin_deps(),
        patch("app.routers.admin_youtube.extract_video_id", return_value=None),
    ):
        from app.routers.admin_youtube import youtube_extract
        from app.schemas.youtube_admin import YoutubeExtractRequest

        with pytest.raises(AppException) as exc_info:
            await youtube_extract(
                body=YoutubeExtractRequest(url="https://invalid-url.com"),
                user_id=ADMIN_USER_ID,
                supabase=mock_supabase,
            )
        assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_youtube_extract_transcript_failure(mock_supabase):
    """字幕取得失敗なら 422。"""
    from app.exceptions import AppException

    with (
        _mock_admin_deps(),
        patch("app.routers.admin_youtube.extract_video_id", return_value="dQw4w9WgXcQ"),
        patch("app.routers.admin_youtube.fetch_transcript", side_effect=Exception("No transcript")),
    ):
        from app.routers.admin_youtube import youtube_extract
        from app.schemas.youtube_admin import YoutubeExtractRequest

        with pytest.raises(AppException) as exc_info:
            await youtube_extract(
                body=YoutubeExtractRequest(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
                user_id=ADMIN_USER_ID,
                supabase=mock_supabase,
            )
        assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_youtube_extract_recipe_extraction_failure(mock_supabase):
    """レシピ抽出失敗なら 422。"""
    from app.exceptions import AppException

    transcript_data = {
        "video_id": "dQw4w9WgXcQ",
        "language_code": "ja",
        "language": "日本語",
        "is_generated": False,
        "entries": [{"text": "テスト", "start": 0, "duration": 3}],
        "text": "テスト",
        "quality": {"quality_score": 50},
    }

    with (
        _mock_admin_deps(),
        patch("app.routers.admin_youtube.extract_video_id", return_value="dQw4w9WgXcQ"),
        patch("app.routers.admin_youtube.fetch_transcript", return_value=transcript_data),
        patch("app.routers.admin_youtube.assess_transcript_quality", return_value={"quality_score": 50}),
        patch("app.routers.admin_youtube.extract_recipe_from_transcript_text", return_value=None),
    ):
        from app.routers.admin_youtube import youtube_extract
        from app.schemas.youtube_admin import YoutubeExtractRequest

        with pytest.raises(AppException) as exc_info:
            await youtube_extract(
                body=YoutubeExtractRequest(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
                user_id=ADMIN_USER_ID,
                supabase=mock_supabase,
            )
        assert exc_info.value.status_code == 422


# --- register ---


@pytest.mark.asyncio
async def test_youtube_register_success(mock_supabase):
    """レシピ登録が成功し、match_recipe_ingredients が呼ばれること。"""
    recipe_id = uuid4()
    nutrition_result = NutritionResult(
        nutrition={"kcal": 350, "protein_g": 25, "fat_g": 10, "carbs_g": 30},
        status=NutritionStatus.ESTIMATED,
        matched_count=1,
        total_count=2,
    )

    from app.services.recipe_quality_gate import RecipeQualityGateResult

    accepted_gate = RecipeQualityGateResult(accepted=[{}], rejected=[])

    with (
        _mock_admin_deps(),
        patch("app.routers.admin_youtube.recipe_repo.upsert_recipe", return_value=recipe_id),
        patch("app.routers.admin_youtube.match_recipe_ingredients", return_value=[]) as mock_match,
        patch("app.routers.admin_youtube.calculate_recipe_nutrition", return_value=nutrition_result),
        patch(
            "app.routers.admin_youtube.filter_meal_like_recipes_safe",
            new=AsyncMock(return_value=accepted_gate),
        ),
    ):
        from app.routers.admin_youtube import youtube_register
        from app.schemas.youtube_admin import (
            RecipeDraft,
            RecipeDraftIngredient,
            RecipeDraftStep,
            YoutubeRegisterRequest,
        )

        body = YoutubeRegisterRequest(
            video_id="dQw4w9WgXcQ",
            recipe_data=RecipeDraft(
                title="テストレシピ",
                servings=2,
                cooking_minutes=15,
                ingredients=[
                    RecipeDraftIngredient(ingredient_name="鶏もも肉", amount_text="300g"),
                ],
                steps=[
                    RecipeDraftStep(step_no=1, text="鶏肉を切る", est_minutes=3),
                ],
                tags=["鶏肉"],
            ),
        )
        result = await youtube_register(body=body, user_id=ADMIN_USER_ID, supabase=mock_supabase)

        assert result.recipe_id == str(recipe_id)
        assert result.title == "テストレシピ"
        assert result.nutrition_status == "estimated"

        # match_recipe_ingredients が呼ばれたことを検証
        mock_match.assert_called_once()
        call_args = mock_match.call_args
        assert call_args[0][1] == recipe_id  # recipe_id


@pytest.mark.asyncio
async def test_youtube_register_maps_steps_to_generated_steps(mock_supabase):
    """register 時に steps が generated_steps にマッピングされ steps_status=generated になること。"""
    recipe_id = uuid4()
    nutrition_result = NutritionResult(
        nutrition=None,
        status=NutritionStatus.FAILED,
        matched_count=0,
        total_count=1,
    )

    upsert_call_data = {}

    async def capture_upsert(supabase, data):
        upsert_call_data.update(data)
        return recipe_id

    from app.services.recipe_quality_gate import RecipeQualityGateResult

    accepted_gate = RecipeQualityGateResult(accepted=[{}], rejected=[])

    with (
        _mock_admin_deps(),
        patch("app.routers.admin_youtube.recipe_repo.upsert_recipe", side_effect=capture_upsert),
        patch("app.routers.admin_youtube.match_recipe_ingredients", return_value=[]),
        patch("app.routers.admin_youtube.calculate_recipe_nutrition", return_value=nutrition_result),
        patch(
            "app.routers.admin_youtube.filter_meal_like_recipes_safe",
            new=AsyncMock(return_value=accepted_gate),
        ),
    ):
        from app.routers.admin_youtube import youtube_register
        from app.schemas.youtube_admin import (
            RecipeDraft,
            RecipeDraftIngredient,
            RecipeDraftStep,
            YoutubeRegisterRequest,
        )

        body = YoutubeRegisterRequest(
            video_id="test123abcd",
            recipe_data=RecipeDraft(
                title="手順テスト",
                ingredients=[RecipeDraftIngredient(ingredient_name="材料A")],
                steps=[
                    RecipeDraftStep(step_no=1, text="手順1", est_minutes=5),
                    RecipeDraftStep(step_no=2, text="手順2"),
                ],
            ),
        )
        await youtube_register(body=body, user_id=ADMIN_USER_ID, supabase=mock_supabase)

    assert upsert_call_data.get("steps_status") == "generated"
    assert len(upsert_call_data.get("generated_steps", [])) == 2
    assert upsert_call_data["generated_steps"][0]["text"] == "手順1"


# --- recipes list ---


@pytest.mark.asyncio
async def test_youtube_recipes_list_success(mock_supabase):
    """YouTube レシピ一覧が正常に返ること。"""
    mock_response = MagicMock()
    mock_response.data = [
        {
            "id": str(uuid4()),
            "title": "テストレシピ",
            "youtube_video_id": "abc123",
            "recipe_source": "youtube",
            "nutrition_status": "estimated",
            "steps_status": "generated",
            "created_at": "2026-03-19T00:00:00+00:00",
        }
    ]
    mock_response.count = 1

    chain = mock_supabase.table.return_value.select.return_value
    chain.eq.return_value.order.return_value.range.return_value.execute = AsyncMock(return_value=mock_response)

    with _mock_admin_deps():
        from app.routers.admin_youtube import list_youtube_recipes

        result = await list_youtube_recipes(page=1, per_page=20, user_id=ADMIN_USER_ID, supabase=mock_supabase)
        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].youtube_video_id == "abc123"


@pytest.mark.asyncio
async def test_youtube_recipes_list_migration_fallback(mock_supabase):
    """migration 014 未適用時のフォールバック。"""
    api_error = APIError({"message": "column recipe_source does not exist", "code": "42703", "details": "", "hint": ""})

    fallback_response = MagicMock()
    fallback_response.data = [
        {
            "id": str(uuid4()),
            "title": "YouTube レシピ",
            "recipe_url": "https://www.youtube.com/watch?v=test123",
            "nutrition_status": "calculated",
            "steps_status": "pending",
            "created_at": "2026-03-18T00:00:00+00:00",
        }
    ]
    fallback_response.count = 1

    # 1回目の呼び出しで APIError、2回目(フォールバック)で成功
    chain1 = mock_supabase.table.return_value.select.return_value
    chain1.eq.return_value.order.return_value.range.return_value.execute = AsyncMock(side_effect=api_error)
    chain1.ilike.return_value.order.return_value.range.return_value.execute = AsyncMock(return_value=fallback_response)

    with _mock_admin_deps():
        from app.routers.admin_youtube import list_youtube_recipes

        result = await list_youtube_recipes(page=1, per_page=20, user_id=ADMIN_USER_ID, supabase=mock_supabase)
        assert result.total == 1
        assert result.items[0].title == "YouTube レシピ"


# --- Gemini quality gate: register ---


@pytest.mark.asyncio
async def test_youtube_register_blocks_non_meal(mock_supabase):
    """非食事レシピは品質ゲートで 422 エラーになる。"""
    from app.exceptions import AppException
    from app.services.recipe_quality_gate import RecipeQualityGateResult

    rejected_result = RecipeQualityGateResult(
        accepted=[],
        rejected=[{"recipe": {"title": "うどんのつけ汁"}, "reason": "sauce only"}],
    )

    with (
        _mock_admin_deps(),
        patch(
            "app.routers.admin_youtube.filter_meal_like_recipes_safe",
            new=AsyncMock(return_value=rejected_result),
        ),
    ):
        from app.routers.admin_youtube import youtube_register
        from app.schemas.youtube_admin import (
            RecipeDraft,
            RecipeDraftIngredient,
            RecipeDraftStep,
            YoutubeRegisterRequest,
        )

        body = YoutubeRegisterRequest(
            video_id="test123",
            recipe_data=RecipeDraft(
                title="うどんのつけ汁",
                servings=2,
                cooking_minutes=5,
                ingredients=[RecipeDraftIngredient(ingredient_name="醤油", amount_text="大さじ2")],
                steps=[RecipeDraftStep(step_no=1, text="混ぜる", est_minutes=1)],
                tags=[],
            ),
        )

        with pytest.raises(AppException) as exc_info:
            await youtube_register(body=body, user_id=ADMIN_USER_ID, supabase=mock_supabase)

        assert exc_info.value.status_code == 422
        assert "sauce only" in exc_info.value.detail


@pytest.mark.asyncio
async def test_youtube_batch_adapt_filters_non_meal(mock_supabase):
    """batch-adapt で品質ゲートが非食事レシピを filtered_non_meal にする。"""
    from app.services.recipe_quality_gate import RecipeQualityGateResult

    accepted_gate = RecipeQualityGateResult(
        accepted=[{"recipe": {"title": "うどんの作り方"}}],
        rejected=[],
    )
    rejected_gate = RecipeQualityGateResult(
        accepted=[],
        rejected=[{"recipe": {"title": "うどんのつけ汁"}, "reason": "sauce only"}],
    )

    mock_supabase.table.return_value.select.return_value.eq.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[])
    )

    with (
        _mock_admin_deps(),
        patch("app.routers.admin_youtube.settings") as mock_settings,
        patch("app.routers.admin_youtube.resolve_channel_id", return_value="UC_test"),
        patch(
            "app.routers.admin_youtube.fetch_channel_videos_by_query",
            return_value=[{"video_id": "vid1", "title": "うどんの作り方"}],
        ),
        patch(
            "app.routers.admin_youtube.fetch_transcript",
            return_value={"text": "テスト", "is_generated": False},
        ),
        patch(
            "app.routers.admin_youtube.extract_recipe_from_transcript_text",
            return_value={
                "title": "うどんの作り方",
                "servings": 2,
                "cooking_minutes": 10,
                "ingredients": [{"ingredient_name": "うどん", "amount_text": "1玉"}],
                "steps": [],
                "tags": [],
            },
        ),
        patch(
            "app.routers.admin_youtube.adapt_recipe_to_staple",
            return_value={
                "title": "うどんの作り方",
                "servings": 2,
                "ingredients": [{"ingredient_name": "うどん", "amount_text": "1玉"}],
                "steps": [],
            },
        ),
        patch("app.routers.admin_youtube.is_accompaniment_for_staple", return_value=False),
        patch(
            "app.routers.admin_youtube.filter_meal_like_recipes_safe",
            new=AsyncMock(side_effect=[accepted_gate, rejected_gate]),
        ),
    ):
        mock_settings.youtube_api_key = "fake_key"

        from app.routers.admin_youtube import youtube_batch_adapt
        from app.schemas.youtube_admin import BatchAdaptRequest

        body = BatchAdaptRequest(
            channel_handle="@TestChannel",
            source_query="うどん",
            target_staple="冷凍うどん",
            max_results=1,
        )

        result = await youtube_batch_adapt(body=body, user_id=ADMIN_USER_ID, supabase=mock_supabase)

    filtered = [r for r in result.results if r.status == "filtered_non_meal"]
    assert len(filtered) == 1
    assert result.skipped >= 1


@pytest.mark.asyncio
async def test_youtube_batch_adapt_filters_source_non_meal_before_adaptation(mock_supabase):
    """元動画の抽出結果が非食事なら adapt 前に除外する。"""
    from app.services.recipe_quality_gate import RecipeQualityGateResult

    rejected_gate = RecipeQualityGateResult(
        accepted=[],
        rejected=[{"recipe": {"title": "絶品つけダレ"}, "reason": "sauce only"}],
    )

    mock_supabase.table.return_value.select.return_value.eq.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[])
    )

    with (
        _mock_admin_deps(),
        patch("app.routers.admin_youtube.settings") as mock_settings,
        patch("app.routers.admin_youtube.resolve_channel_id", return_value="UC_test"),
        patch(
            "app.routers.admin_youtube.fetch_channel_videos_by_query",
            return_value=[{"video_id": "vid1", "title": "【パスタ世界一が作る！】絶品パスタソース"}],
        ),
        patch(
            "app.routers.admin_youtube.fetch_transcript",
            return_value={"text": "テスト", "is_generated": False},
        ),
        patch(
            "app.routers.admin_youtube.extract_recipe_from_transcript_text",
            return_value={
                "title": "絶品つけダレ",
                "servings": 2,
                "cooking_minutes": 10,
                "ingredients": [{"ingredient_name": "トマト", "amount_text": "1個"}],
                "steps": [],
                "tags": [],
            },
        ),
        patch(
            "app.routers.admin_youtube.filter_meal_like_recipes_safe",
            new=AsyncMock(return_value=rejected_gate),
        ),
        patch("app.routers.admin_youtube.adapt_recipe_to_staple", new=AsyncMock()) as mock_adapt,
    ):
        mock_settings.youtube_api_key = "fake_key"

        from app.routers.admin_youtube import youtube_batch_adapt
        from app.schemas.youtube_admin import BatchAdaptRequest

        body = BatchAdaptRequest(
            channel_handle="@TestChannel",
            source_query="パスタ",
            target_staple="冷凍うどん",
            max_results=1,
        )

        result = await youtube_batch_adapt(body=body, user_id=ADMIN_USER_ID, supabase=mock_supabase)

    assert result.results[0].status == "filtered_non_meal"
    assert result.skipped == 1
    mock_adapt.assert_not_called()


@pytest.mark.asyncio
async def test_youtube_batch_adapt_filters_source_mismatch_before_extraction(mock_supabase):
    """パスタ指定でも元動画タイトルが非パスタなら抽出前に除外する。"""
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[])
    )

    with (
        _mock_admin_deps(),
        patch("app.routers.admin_youtube.settings") as mock_settings,
        patch("app.routers.admin_youtube.resolve_channel_id", return_value="UC_test"),
        patch(
            "app.routers.admin_youtube.fetch_channel_videos_by_query",
            return_value=[{"video_id": "vid1", "title": "笠原流【クラムチャウダー】"}],
        ),
        patch("app.routers.admin_youtube.fetch_transcript", new=AsyncMock()) as mock_transcript,
        patch("app.routers.admin_youtube.extract_recipe_from_transcript_text", new=AsyncMock()) as mock_extract,
        patch("app.routers.admin_youtube.adapt_recipe_to_staple", new=AsyncMock()) as mock_adapt,
    ):
        mock_settings.youtube_api_key = "fake_key"

        from app.routers.admin_youtube import youtube_batch_adapt
        from app.schemas.youtube_admin import BatchAdaptRequest

        body = BatchAdaptRequest(
            channel_handle="@TestChannel",
            source_query="パスタ",
            target_staple="冷凍うどん",
            max_results=1,
        )

        result = await youtube_batch_adapt(body=body, user_id=ADMIN_USER_ID, supabase=mock_supabase)

    assert result.results[0].status == "filtered_source_mismatch"
    assert result.skipped == 1
    mock_transcript.assert_not_called()
    mock_extract.assert_not_called()
    mock_adapt.assert_not_called()


@pytest.mark.asyncio
async def test_youtube_batch_adapt_filters_branded_non_pasta_title(mock_supabase):
    """先頭の肩書きにしかパスタ語がない動画は source mismatch にする。"""
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[])
    )

    with (
        _mock_admin_deps(),
        patch("app.routers.admin_youtube.settings") as mock_settings,
        patch("app.routers.admin_youtube.resolve_channel_id", return_value="UC_test"),
        patch(
            "app.routers.admin_youtube.fetch_channel_videos_by_query",
            return_value=[{"video_id": "vid1", "title": "【パスタ世界一が作る！】イタリア式 激旨チキンカツ！"}],
        ),
        patch("app.routers.admin_youtube.fetch_transcript", new=AsyncMock()) as mock_transcript,
    ):
        mock_settings.youtube_api_key = "fake_key"

        from app.routers.admin_youtube import youtube_batch_adapt
        from app.schemas.youtube_admin import BatchAdaptRequest

        body = BatchAdaptRequest(
            channel_handle="@TestChannel",
            source_query="パスタ",
            target_staple="冷凍うどん",
            max_results=1,
        )

        result = await youtube_batch_adapt(body=body, user_id=ADMIN_USER_ID, supabase=mock_supabase)

    assert result.results[0].status == "filtered_source_mismatch"
    assert result.skipped == 1
    mock_transcript.assert_not_called()


@pytest.mark.asyncio
async def test_youtube_batch_adapt_allows_matching_pasta_title(mock_supabase):
    """元動画タイトルがパスタ系なら source mismatch で弾かれない。"""
    from app.services.recipe_quality_gate import RecipeQualityGateResult

    accepted_gate = RecipeQualityGateResult(
        accepted=[{"title": "春菊と長ねぎのクリームうどん"}],
        rejected=[],
    )
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[])
    )

    with (
        _mock_admin_deps(),
        patch("app.routers.admin_youtube.settings") as mock_settings,
        patch("app.routers.admin_youtube.resolve_channel_id", return_value="UC_test"),
        patch(
            "app.routers.admin_youtube.fetch_channel_videos_by_query",
            return_value=[{"video_id": "vid1", "title": "春菊と長ねぎのクリームパスタ"}],
        ),
        patch(
            "app.routers.admin_youtube.fetch_transcript",
            return_value={"text": "テスト", "is_generated": False},
        ),
        patch(
            "app.routers.admin_youtube.extract_recipe_from_transcript_text",
            return_value={
                "title": "春菊と長ねぎのクリームパスタ",
                "servings": 2,
                "cooking_minutes": 10,
                "ingredients": [{"ingredient_name": "パスタ", "amount_text": "100g"}],
                "steps": [],
                "tags": [],
            },
        ),
        patch(
            "app.routers.admin_youtube.adapt_recipe_to_staple",
            return_value={
                "title": "春菊と長ねぎのクリームうどん",
                "servings": 2,
                "ingredients": [{"ingredient_name": "うどん", "amount_text": "1玉"}],
                "steps": [],
            },
        ),
        patch("app.routers.admin_youtube.is_accompaniment_for_staple", return_value=False),
        patch(
            "app.routers.admin_youtube.filter_meal_like_recipes_safe",
            new=AsyncMock(side_effect=[accepted_gate, accepted_gate]),
        ),
        patch("app.routers.admin_youtube.recipe_repo.upsert_recipe", return_value=uuid4()),
        patch("app.routers.admin_youtube.match_recipe_ingredients", return_value=[]),
        patch(
            "app.routers.admin_youtube.calculate_recipe_nutrition",
            return_value=NutritionResult(
                nutrition=None,
                status=NutritionStatus.FAILED,
                matched_count=0,
                total_count=1,
            ),
        ),
    ):
        mock_settings.youtube_api_key = "fake_key"

        from app.routers.admin_youtube import youtube_batch_adapt
        from app.schemas.youtube_admin import BatchAdaptRequest

        body = BatchAdaptRequest(
            channel_handle="@TestChannel",
            source_query="パスタ",
            target_staple="冷凍うどん",
            max_results=1,
        )

        result = await youtube_batch_adapt(body=body, user_id=ADMIN_USER_ID, supabase=mock_supabase)

    assert result.succeeded == 1
    assert result.results[0].status == "success"
