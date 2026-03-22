"""管理者用エンドポイント — YouTube レシピ管理"""

import asyncio
import logging
import re
from uuid import UUID

import httpx
from app.config import settings
from app.data.food_master import STAPLE_SHORT_NAMES, STAPLE_TAG_MAP
from app.dependencies.auth import get_admin_user_id
from app.dependencies.supabase_client import get_service_supabase
from app.exceptions import AppException, ErrorCode
from app.repositories import recipe_repo
from app.schemas.youtube_admin import (
    BatchAdaptRequest,
    BatchAdaptResponse,
    BatchAdaptVideoResult,
    RecipeDraft,
    YoutubeExtractRequest,
    YoutubeExtractResponse,
    YoutubeRecipeItem,
    YoutubeRecipeListResponse,
    YoutubeRegisterRequest,
    YoutubeRegisterResponse,
)
from app.services.ingredient_matcher import calculate_recipe_nutrition, match_recipe_ingredients
from app.services.recipe_quality_gate import filter_meal_like_recipes_safe
from app.services.youtube_api import fetch_channel_videos_by_query, resolve_channel_id
from app.services.youtube_gemini import adapt_recipe_to_staple, extract_recipe_from_transcript_text
from app.services.youtube_recipe import NON_MEAL_TITLE_KEYWORDS
from app.services.youtube_transcript_service import (
    assess_transcript_quality,
    extract_video_id,
    fetch_transcript,
    naturalize_auto_transcript,
)
from app.utils.text_normalize import is_accompaniment_for_staple
from fastapi import APIRouter, Depends, Query
from postgrest.exceptions import APIError

from supabase import AsyncClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

SOURCE_QUERY_TITLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "パスタ": (
        "パスタ",
        "スパゲティ",
        "スパゲッティ",
        "ペンネ",
        "マカロニ",
        "ラザニア",
        "ナポリタン",
        "カルボナーラ",
        "ペペロンチーノ",
    ),
}


def _title_matches_source_query(video_title: str, source_query: str) -> bool:
    title = (video_title or "").strip()
    query = (source_query or "").strip()
    if not title or not query:
        return False

    # 先頭の装飾・肩書きだけで source query に一致している誤判定を避ける。
    title = re.sub(r"^\s*[【\[].*?[】\]]\s*", "", title)

    keywords = SOURCE_QUERY_TITLE_KEYWORDS.get(query)
    if keywords:
        return any(keyword in title for keyword in keywords)
    return query in title


@router.post("/youtube/extract", response_model=YoutubeExtractResponse)
async def youtube_extract(
    body: YoutubeExtractRequest,
    user_id: UUID = Depends(get_admin_user_id),
    supabase: AsyncClient = Depends(get_service_supabase),
) -> YoutubeExtractResponse:
    """YouTube URL から字幕を取得し、レシピを抽出する。"""
    video_id = extract_video_id(body.url)
    if not video_id:
        raise AppException(ErrorCode.VALIDATION_ERROR, 422, "無効な YouTube URL です")

    try:
        transcript = await fetch_transcript(body.url)
    except Exception as e:
        logger.warning("Transcript fetch failed for %s: %s", body.url, e)
        raise AppException(ErrorCode.VALIDATION_ERROR, 422, f"字幕の取得に失敗しました: {e}") from e

    entries = transcript.get("entries", [])
    quality = assess_transcript_quality(entries)
    text = transcript.get("text", "")

    # 自動字幕なら自然化
    if transcript.get("is_generated"):
        try:
            text = await naturalize_auto_transcript(text)
        except Exception:
            logger.warning("Transcript naturalization failed, using raw text")

    # Gemini でレシピ抽出
    video_title = transcript.get("language", "") or ""
    recipe_data = await extract_recipe_from_transcript_text(
        text,
        video_title=video_title,
        staple_name=body.staple_name or "",
    )
    if not recipe_data:
        raise AppException(
            ErrorCode.VALIDATION_ERROR, 422, "レシピの抽出に失敗しました。字幕の内容がレシピとして認識できません。"
        )

    draft = RecipeDraft(
        title=recipe_data.get("title", ""),
        servings=recipe_data.get("servings", 2),
        cooking_minutes=recipe_data.get("cooking_minutes"),
        ingredients=[
            {"ingredient_name": ing.get("ingredient_name", ""), "amount_text": ing.get("amount_text")}
            for ing in recipe_data.get("ingredients", [])
        ],
        steps=[
            {
                "step_no": step.get("step_no", idx + 1),
                "text": step.get("text", ""),
                "est_minutes": step.get("est_minutes"),
            }
            for idx, step in enumerate(recipe_data.get("steps", []))
        ],
        tags=recipe_data.get("tags", []),
    )

    return YoutubeExtractResponse(
        video_id=video_id,
        video_title=recipe_data.get("title", ""),
        transcript_quality=quality,
        recipe_draft=draft,
    )


@router.post("/youtube/register", response_model=YoutubeRegisterResponse)
async def youtube_register(
    body: YoutubeRegisterRequest,
    user_id: UUID = Depends(get_admin_user_id),
    supabase: AsyncClient = Depends(get_service_supabase),
) -> YoutubeRegisterResponse:
    """抽出・編集済みレシピを DB に登録する。"""
    recipe_dict = {
        "youtube_video_id": body.video_id,
        "recipe_source": "youtube",
        "title": body.recipe_data.title,
        "image_url": f"https://img.youtube.com/vi/{body.video_id}/maxresdefault.jpg",
        "recipe_url": f"https://www.youtube.com/watch?v={body.video_id}",
        "servings": body.recipe_data.servings,
        "cooking_minutes": body.recipe_data.cooking_minutes,
        "tags": body.recipe_data.tags,
        "generated_steps": [s.model_dump() for s in body.recipe_data.steps],
        "steps_status": "generated",
        "ingredients": [ing.model_dump() for ing in body.recipe_data.ingredients],
    }

    gate = await filter_meal_like_recipes_safe([recipe_dict])
    if gate.rejected:
        reason = gate.rejected[0].get("reason", "not_meal_like")
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            422,
            f"このレシピは食事として成立しないと判定されました: {reason}",
        )

    recipe_id = await recipe_repo.upsert_recipe(supabase, recipe_dict)

    # 食材マッチング
    ingredients_for_match = [ing.model_dump() for ing in body.recipe_data.ingredients]
    await match_recipe_ingredients(supabase, recipe_id, ingredients_for_match)

    # 栄養計算
    nutrition_result = await calculate_recipe_nutrition(supabase, recipe_id)

    return YoutubeRegisterResponse(
        recipe_id=str(recipe_id),
        title=body.recipe_data.title,
        nutrition_status=nutrition_result.status.value,
    )


@router.get("/youtube/recipes", response_model=YoutubeRecipeListResponse)
async def list_youtube_recipes(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user_id: UUID = Depends(get_admin_user_id),
    supabase: AsyncClient = Depends(get_service_supabase),
) -> YoutubeRecipeListResponse:
    """登録済み YouTube レシピ一覧を取得する。"""
    start = (page - 1) * per_page
    end = start + per_page - 1

    try:
        response = await (
            supabase.table("recipes")
            .select(
                "id, title, youtube_video_id, recipe_source, nutrition_status, steps_status, created_at",
                count="exact",
            )
            .eq("recipe_source", "youtube")
            .order("created_at", desc=True)
            .range(start, end)
            .execute()
        )
    except APIError:
        # migration 014 未適用 → recipe_url で YouTube を判定
        response = await (
            supabase.table("recipes")
            .select("id, title, recipe_url, nutrition_status, steps_status, created_at", count="exact")
            .ilike("recipe_url", "%youtube.com%")
            .order("created_at", desc=True)
            .range(start, end)
            .execute()
        )

    rows = response.data or []
    total = response.count or 0

    items = []
    for row in rows:
        items.append(
            YoutubeRecipeItem(
                id=row["id"],
                title=row.get("title", ""),
                youtube_video_id=row.get("youtube_video_id"),
                nutrition_status=row.get("nutrition_status"),
                steps_status=row.get("steps_status"),
                created_at=row.get("created_at"),
            )
        )

    return YoutubeRecipeListResponse(items=items, total=total, page=page, per_page=per_page)


BATCH_ADAPT_INTER_VIDEO_DELAY = 2.0


@router.post("/youtube/batch-adapt", response_model=BatchAdaptResponse)
async def youtube_batch_adapt(
    body: BatchAdaptRequest,
    user_id: UUID = Depends(get_admin_user_id),
    supabase: AsyncClient = Depends(get_service_supabase),
) -> BatchAdaptResponse:
    """チャンネルのレシピ動画を別の主食にアレンジして一括登録する。"""
    # --- バリデーション ---
    if body.max_results > 10:
        raise AppException(ErrorCode.VALIDATION_ERROR, 422, "max_results は 10 以下にしてください")
    if body.target_staple not in STAPLE_TAG_MAP:
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            422,
            f"不明な target_staple: {body.target_staple}（有効値: {', '.join(STAPLE_TAG_MAP.keys())}）",
        )

    short_staple = STAPLE_SHORT_NAMES.get(body.target_staple, body.target_staple)
    channel_tag = body.channel_handle.lstrip("@")

    # --- 既存 video_id を取得して重複スキップ ---
    existing_ids: set[str] = set()
    try:
        resp = await supabase.table("recipes").select("youtube_video_id").eq("recipe_source", "youtube").execute()
        existing_ids = {r["youtube_video_id"] for r in (resp.data or []) if r.get("youtube_video_id")}
    except APIError:
        # migration 014 未適用フォールバック
        resp = await supabase.table("recipes").select("recipe_url").ilike("recipe_url", "%youtube.com%").execute()
        for r in resp.data or []:
            url = r.get("recipe_url", "")
            vid = extract_video_id(url)
            if vid:
                existing_ids.add(vid)

    # --- チャンネル解決 + 動画取得 ---
    async with httpx.AsyncClient() as http_client:
        channel_id = await resolve_channel_id(http_client, settings.youtube_api_key, body.channel_handle)
        if not channel_id:
            raise AppException(ErrorCode.VALIDATION_ERROR, 422, f"チャンネルが見つかりません: {body.channel_handle}")

        videos = await fetch_channel_videos_by_query(
            http_client, settings.youtube_api_key, channel_id, query=body.source_query, max_results=25
        )

    # NON_MEAL フィルタ
    videos = [v for v in videos if not any(kw in (v.get("title") or "") for kw in NON_MEAL_TITLE_KEYWORDS)]

    results: list[BatchAdaptVideoResult] = []
    succeeded = 0
    failed = 0
    skipped = 0
    processed = 0

    for v in videos:
        if processed >= body.max_results:
            break

        video_id = v["video_id"]
        video_title = v.get("title", "")

        if not _title_matches_source_query(video_title, body.source_query):
            results.append(
                BatchAdaptVideoResult(
                    video_id=video_id,
                    video_title=video_title,
                    status="filtered_source_mismatch",
                )
            )
            skipped += 1
            continue

        # 重複スキップ
        if video_id in existing_ids:
            results.append(BatchAdaptVideoResult(video_id=video_id, video_title=video_title, status="skipped_existing"))
            skipped += 1
            continue

        processed += 1

        # Gemini レートリミット対策
        if processed > 1:
            await asyncio.sleep(BATCH_ADAPT_INTER_VIDEO_DELAY)

        # 1. 字幕取得
        try:
            transcript = await fetch_transcript(f"https://www.youtube.com/watch?v={video_id}")
        except Exception as e:
            logger.warning("Transcript fetch failed for %s: %s", video_id, e)
            results.append(
                BatchAdaptVideoResult(video_id=video_id, video_title=video_title, status="no_transcript", error=str(e))
            )
            failed += 1
            continue

        text = transcript.get("text", "")

        # 自動字幕なら自然化
        if transcript.get("is_generated"):
            try:
                text = await naturalize_auto_transcript(text)
            except Exception:
                logger.warning("Transcript naturalization failed for %s, using raw text", video_id)

        # 2. レシピ抽出（制約なし: レビュー #4）
        extracted = await extract_recipe_from_transcript_text(text, video_title=video_title, staple_name="")
        if not extracted:
            results.append(
                BatchAdaptVideoResult(
                    video_id=video_id, video_title=video_title, status="extraction_failed", error="レシピ抽出に失敗"
                )
            )
            failed += 1
            continue

        source_gate_recipe = {
            "title": extracted.get("title", video_title),
            "description": "",
            "tags": extracted.get("tags", []),
            "ingredients": extracted.get("ingredients", []),
        }
        source_gate = await filter_meal_like_recipes_safe([source_gate_recipe])
        if source_gate.rejected:
            logger.info(
                "Quality gate filtered source recipe before adaptation: %s reason=%s",
                source_gate_recipe["title"],
                source_gate.rejected[0].get("reason", "not_meal_like"),
            )
            results.append(
                BatchAdaptVideoResult(
                    video_id=video_id,
                    video_title=video_title,
                    status="filtered_non_meal",
                )
            )
            skipped += 1
            continue

        # 3. 主食アレンジ
        adapted = await adapt_recipe_to_staple(extracted, short_staple)
        if not adapted:
            results.append(
                BatchAdaptVideoResult(
                    video_id=video_id, video_title=video_title, status="adaptation_failed", error="主食アレンジに失敗"
                )
            )
            failed += 1
            continue

        # 付け合わせ除外: adapt 後のタイトルで判定
        adapted_title = adapted.get("title", video_title)
        if is_accompaniment_for_staple(adapted_title, short_staple):
            logger.info("Filtered accompaniment recipe after adaptation: %s", adapted_title)
            results.append(
                BatchAdaptVideoResult(video_id=video_id, video_title=video_title, status="filtered_accompaniment")
            )
            skipped += 1
            continue

        # 4. Gemini 品質ゲート（非食事レシピを除外）
        recipe_dict_for_gate = {
            "title": adapted.get("title", video_title),
            "description": "",
            "tags": [short_staple],
            "ingredients": adapted.get("ingredients", []),
        }
        gate = await filter_meal_like_recipes_safe([recipe_dict_for_gate])
        if gate.rejected:
            gate_reason = gate.rejected[0].get("reason", "not_meal_like")
            logger.info("Quality gate filtered non-meal recipe: %s reason=%s", adapted_title, gate_reason)
            results.append(
                BatchAdaptVideoResult(video_id=video_id, video_title=video_title, status="filtered_non_meal")
            )
            skipped += 1
            continue

        # 5. DB 登録
        try:
            recipe_dict = {
                "youtube_video_id": video_id,
                "recipe_source": "youtube",
                "title": adapted.get("title", video_title),
                "description": f"{channel_tag}の{body.source_query}レシピを{short_staple}にアレンジ",
                "image_url": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                "recipe_url": f"https://www.youtube.com/watch?v={video_id}",
                "servings": adapted.get("servings", 2),
                "cooking_minutes": adapted.get("cooking_minutes"),
                "tags": [
                    "YouTube",
                    channel_tag,
                    short_staple,
                    f"アレンジ:{body.source_query}→{short_staple}",
                    f"staple:{body.target_staple}",
                ],
                "ingredients": adapted.get("ingredients", []),
                "generated_steps": adapted.get("steps", []),
                "steps_status": "generated",
            }

            recipe_id = await recipe_repo.upsert_recipe(supabase, recipe_dict)

            # 食材マッチング + 栄養計算
            ingredients_for_match = adapted.get("ingredients", [])
            await match_recipe_ingredients(supabase, recipe_id, ingredients_for_match)
            await calculate_recipe_nutrition(supabase, recipe_id)

            existing_ids.add(video_id)
            results.append(
                BatchAdaptVideoResult(
                    video_id=video_id,
                    video_title=video_title,
                    status="success",
                    recipe_id=str(recipe_id),
                    recipe_title=adapted.get("title", video_title),
                )
            )
            succeeded += 1
        except Exception as e:
            logger.exception("Registration failed for %s", video_id)
            results.append(
                BatchAdaptVideoResult(
                    video_id=video_id,
                    video_title=video_title,
                    status="registration_failed",
                    error=str(e),
                )
            )
            failed += 1

    return BatchAdaptResponse(
        channel_handle=body.channel_handle,
        source_query=body.source_query,
        target_staple=body.target_staple,
        videos_found=len(videos),
        videos_processed=processed,
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
        results=results,
    )
