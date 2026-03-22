"""YouTube レシピ取込オーケストレーター

チャンネルから最新動画を取得し、レシピ情報を抽出するワークフローを統合する。
個別の責務は youtube_api / youtube_download / youtube_gemini に委譲。
"""

import asyncio
import logging
import tempfile
from pathlib import Path

import httpx
from app.data.food_master import STAPLE_SHORT_NAMES
from app.services.recipe_quality_gate import filter_meal_like_recipes_safe
from app.services.youtube_api import (
    DEFAULT_MAX_RESULTS,
    MAX_DAILY_VIDEOS,
    QuotaExceededError,
    fetch_channel_video_ids,
    fetch_channel_videos_by_query,
    resolve_channel_id,
)
from app.services.youtube_download import download_video_audio, download_video_lowres
from app.services.youtube_gemini import (
    _naturalize_transcript_for_recipe,
    adapt_recipe_to_staple,
    extract_recipe_from_media,
    extract_recipe_from_transcript_text,
)
from app.services.youtube_transcript_service import fetch_transcript
from app.utils.text_normalize import is_accompaniment_for_staple

logger = logging.getLogger(__name__)

NON_MEAL_TITLE_KEYWORDS = (
    "つけ汁",
    "つゆ",
    "タレ",
    "たれ",
    "かえし",
    "レシピ3選",
    "まとめ",
)


async def extract_recipe_with_fallback(video_id: str, tmp_dir: Path) -> dict | None:
    """音声 → Gemini 分析 → 信頼性ゲート。
    ゲート不合格（材料 0 件等）の場合のみ低解像度動画で再試行。
    """
    # 音声で試行
    audio_path = await download_video_audio(video_id, tmp_dir)
    if audio_path:
        result = await extract_recipe_from_media(audio_path)
        if result:
            return result
        logger.info("Audio extraction failed validation for %s, trying video fallback", video_id)

    # 動画フォールバック
    video_path = await download_video_lowres(video_id, tmp_dir)
    if video_path:
        result = await extract_recipe_from_media(video_path)
        if result:
            return result

    logger.warning("All extraction attempts failed for video %s", video_id)
    return None


# ---------------------------------------------------------------------------
# オーケストレーター（コスト制御付き）
# ---------------------------------------------------------------------------


async def fetch_youtube_recipes(
    http_client: httpx.AsyncClient,
    api_key: str,
    channel_handle: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    exclude_video_ids: list[str] | None = None,
    staple_name: str | None = None,
) -> tuple[list[dict], dict]:
    """チャンネルから最新動画を取得し、レシピ情報を抽出。

    Returns: (recipes, stats)
    """
    stats: dict = {
        "channel": channel_handle,
        "videos_found": 0,
        "videos_skipped_existing": 0,
        "videos_skipped_duration": 0,
        "videos_processed": 0,
        "extraction_success": 0,
        "extraction_failed": 0,
        "fallback_to_video": 0,
        "adaptation_attempted": 0,
        "adaptation_success": 0,
        "adaptation_failed": 0,
        "videos_skipped_staple_unmatched": 0,
    }
    exclude_set = set(exclude_video_ids) if exclude_video_ids else set()

    # 1. チャンネル解決
    try:
        channel_id = await resolve_channel_id(http_client, api_key, channel_handle)
    except QuotaExceededError:
        logger.warning("Quota exceeded during channel resolution")
        return [], stats

    if not channel_id:
        logger.warning("Could not resolve channel: %s", channel_handle)
        return [], stats

    # 2. 動画一覧取得
    try:
        videos = await fetch_channel_video_ids(http_client, api_key, channel_id, max_results)
    except QuotaExceededError:
        logger.warning("Quota exceeded during video list fetch")
        return [], stats

    stats["videos_found"] = len(videos)

    # 3. 既知 video_id を除外
    new_videos = []
    for v in videos:
        if v["video_id"] in exclude_set:
            stats["videos_skipped_existing"] += 1
        else:
            new_videos.append(v)

    # 4. 各動画を処理
    recipes: list[dict] = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        for v in new_videos:
            if stats["videos_processed"] >= MAX_DAILY_VIDEOS:
                logger.info("Daily video limit reached (%d)", MAX_DAILY_VIDEOS)
                break

            video_id = v["video_id"]
            stats["videos_processed"] += 1

            result = await extract_recipe_with_fallback(video_id, tmp_path)
            if not result:
                stats["extraction_failed"] += 1
                continue

            stats["extraction_success"] += 1
            if staple_name:
                stats["adaptation_attempted"] += 1
                adapted = await adapt_recipe_to_staple(result, staple_name)
                if adapted:
                    result = adapted
                    stats["adaptation_success"] += 1
                else:
                    stats["adaptation_failed"] += 1
                    stats["videos_skipped_staple_unmatched"] += 1
                    continue

            # 既存パイプライン互換の dict に変換
            channel_tag = channel_handle.lstrip("@")
            tags = ["YouTube", channel_tag] + (result.get("tags") or [])
            if staple_name:
                tags.append(f"staple:{staple_name}")
            recipe_dict = {
                "youtube_video_id": video_id,
                "recipe_source": "youtube",
                "title": result.get("title", v.get("title", "")),
                "description": "",
                "image_url": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                "recipe_url": f"https://www.youtube.com/watch?v={video_id}",
                "servings": result.get("servings", 2),
                "cooking_minutes": result.get("cooking_minutes"),
                "tags": tags,
                "ingredients": result.get("ingredients", []),
                "generated_steps": result.get("steps", []),
            }
            recipes.append(recipe_dict)

    if recipes:
        gate = await filter_meal_like_recipes_safe(recipes)
        filtered_count = len(gate.rejected)
        if filtered_count:
            logger.info("Quality gate filtered %d non-meal recipes", filtered_count)
            for r in gate.rejected:
                logger.info("  rejected: %s reason=%s", r["recipe"].get("title"), r.get("reason"))
        recipes = gate.accepted

    return recipes, stats


async def fetch_youtube_recipes_by_staple_from_channels(
    http_client: httpx.AsyncClient,
    api_key: str,
    channel_handles: list[str],
    staple_name: str,
    max_results_per_channel: int = DEFAULT_MAX_RESULTS,
    exclude_video_ids: list[str] | None = None,
    retry_attempts_per_video: int = 2,
    retry_wait_seconds: float = 2.0,
) -> tuple[list[dict], dict]:
    """事前定義チャンネル群から主食タイトル一致動画を取得し、字幕ベースでレシピ抽出する。"""
    stats: dict = {
        "channels": channel_handles,
        "staple_name": staple_name,
        "videos_found": 0,
        "videos_title_matched": 0,
        "videos_skipped_existing": 0,
        "videos_processed": 0,
        "transcript_success": 0,
        "transcript_failed": 0,
        "recipe_extract_success": 0,
        "recipe_extract_failed": 0,
        "videos_rejected_non_meal": 0,
        "recipes_filtered_accompaniment": 0,
        "video_retry_attempts": 0,
        "video_retry_recovered": 0,
        "per_channel": {},
    }
    staple_short_name = STAPLE_SHORT_NAMES.get(staple_name, "")
    recipes: list[dict] = []
    exclude_set = set(exclude_video_ids or [])

    for channel_handle in channel_handles:
        if stats["videos_processed"] >= MAX_DAILY_VIDEOS:
            break
        try:
            channel_id = await resolve_channel_id(http_client, api_key, channel_handle)
        except QuotaExceededError:
            logger.warning("Quota exceeded while resolving channel: %s", channel_handle)
            continue
        if not channel_id:
            continue

        try:
            videos = await fetch_channel_videos_by_query(
                http_client,
                api_key,
                channel_id,
                query=staple_name,
                max_results=max_results_per_channel,
            )
        except QuotaExceededError:
            logger.warning("Quota exceeded while fetching videos: %s", channel_handle)
            continue

        stats["videos_found"] += len(videos)
        title_matched = [v for v in videos if staple_name in (v.get("title") or "")]
        meal_matched = [
            v for v in title_matched if not any(kw in (v.get("title") or "") for kw in NON_MEAL_TITLE_KEYWORDS)
        ]
        stats["videos_title_matched"] += len(title_matched)
        stats["videos_rejected_non_meal"] += max(0, len(title_matched) - len(meal_matched))
        stats["per_channel"][channel_handle] = {
            "videos_found": len(videos),
            "title_matched": len(title_matched),
            "meal_matched": len(meal_matched),
        }

        for v in meal_matched:
            if stats["videos_processed"] >= MAX_DAILY_VIDEOS:
                break
            video_id = v["video_id"]
            if video_id in exclude_set:
                stats["videos_skipped_existing"] += 1
                continue

            stats["videos_processed"] += 1
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            recovered_by_retry = False
            processed_success = False

            for attempt in range(retry_attempts_per_video + 1):
                if attempt > 0:
                    stats["video_retry_attempts"] += 1
                    await asyncio.sleep(retry_wait_seconds * attempt)

                try:
                    transcript = await fetch_transcript(video_url, languages=["ja", "ja-JP", "en"])
                    stats["transcript_success"] += 1
                except Exception:
                    logger.exception("Failed to fetch transcript for %s (attempt %d)", video_url, attempt + 1)
                    if attempt == retry_attempts_per_video:
                        stats["transcript_failed"] += 1
                    continue

                normalized_text = await _naturalize_transcript_for_recipe(
                    transcript.get("text", ""),
                    bool(transcript.get("is_generated")),
                )

                result = await extract_recipe_from_transcript_text(
                    normalized_text,
                    video_title=v.get("title", ""),
                    staple_name=staple_name,
                )
                if not result:
                    logger.warning("Recipe extraction failed for %s (attempt %d)", video_url, attempt + 1)
                    if attempt == retry_attempts_per_video:
                        stats["recipe_extract_failed"] += 1
                    continue

                stats["recipe_extract_success"] += 1
                if attempt > 0:
                    recovered_by_retry = True

                # 付け合わせ除外: 主食短縮名が特定できる場合のみ適用
                recipe_title = result.get("title", v.get("title", ""))
                if staple_short_name and is_accompaniment_for_staple(recipe_title, staple_short_name):
                    logger.info("Filtered accompaniment recipe: %s", recipe_title)
                    stats["recipes_filtered_accompaniment"] += 1
                    processed_success = True
                    break

                channel_tag = channel_handle.lstrip("@")
                recipe_dict = {
                    "youtube_video_id": video_id,
                    "recipe_source": "youtube",
                    "title": result.get("title", v.get("title", "")),
                    "description": "",
                    "image_url": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                    "recipe_url": video_url,
                    "servings": result.get("servings", 2),
                    "cooking_minutes": result.get("cooking_minutes"),
                    "tags": ["YouTube", channel_tag, f"staple:{staple_name}"] + (result.get("tags") or []),
                    "ingredients": result.get("ingredients", []),
                    "generated_steps": result.get("steps", []),
                }
                recipes.append(recipe_dict)
                exclude_set.add(video_id)
                processed_success = True
                break

            if processed_success and recovered_by_retry:
                stats["video_retry_recovered"] += 1

    if recipes:
        gate = await filter_meal_like_recipes_safe(recipes)
        filtered_count = len(gate.rejected)
        if filtered_count:
            logger.info("Quality gate filtered %d non-meal recipes from staple channels", filtered_count)
            for r in gate.rejected:
                logger.info("  rejected: %s reason=%s", r["recipe"].get("title"), r.get("reason"))
            stats["recipes_filtered_quality_gate"] = filtered_count
        recipes = gate.accepted

    return recipes, stats


# ---------------------------------------------------------------------------
# TODO(remove by 2026-04-30): 旧 import 互換。直接 import に移行したら削除。
# 上部で既に import 済みの名前はここでは不要（そのまま公開される）。
# ---------------------------------------------------------------------------
from app.services.youtube_api import _is_probable_shorts as _is_probable_shorts  # noqa: E402, F401
from app.services.youtube_gemini import GEMINI_RETRY_WAIT as GEMINI_RETRY_WAIT  # noqa: E402, F401
from app.services.youtube_gemini import _parse_gemini_json as _parse_gemini_json  # noqa: E402, F401
from app.services.youtube_gemini import _validate_extracted_recipe as _validate_extracted_recipe  # noqa: E402, F401
