"""YouTube 操作 CLI コマンド"""

import sys

import httpx
from app.config import settings
from app.repositories import recipe_repo
from app.services.cli._shared import _get_service_client
from app.services.ingredient_matcher import calculate_recipe_nutrition, match_recipe_ingredients
from app.services.training_progression_service import ingest_training_progressions
from app.services.youtube_recipe import fetch_youtube_recipes, fetch_youtube_recipes_by_staple_from_channels
from app.services.youtube_transcript_service import fetch_transcript, naturalize_auto_transcript
from postgrest.exceptions import APIError


async def cmd_fetch_youtube_recipes():
    """YouTube 動画からレシピを取得・登録する（字幕ベース抽出が主経路）。"""
    if len(sys.argv) < 3:
        print(
            "Usage: python -m app.services.data_loader fetch-youtube-recipes "
            "<staple_name> [max_results_per_channel] [@channel1,@channel2,...]"
        )
        sys.exit(1)

    staple_name = sys.argv[2].strip()
    max_results_per_channel = int(sys.argv[3]) if len(sys.argv) >= 4 and sys.argv[3].isdigit() else 10
    if len(sys.argv) >= 5:
        channel_handles = [x.strip() for x in sys.argv[4].split(",") if x.strip()]
    else:
        channel_handles = [x.strip() for x in settings.youtube_recipe_channels.split(",") if x.strip()]

    if not settings.youtube_api_key:
        print("ERROR: YOUTUBE_API_KEY is not set")
        sys.exit(1)
    if not settings.google_api_key:
        print("ERROR: GOOGLE_API_KEY is not set (needed for Gemini)")
        sys.exit(1)

    supabase = await _get_service_client()

    # 既存 YouTube レシピの video_id を取得（重複スキップ用）
    # 014 マイグレーション未適用時はフォールバックして継続する。
    try:
        existing = (
            await supabase.table("recipes").select("youtube_video_id").not_.is_("youtube_video_id", "null").execute()
        )
        exclude_ids = [r["youtube_video_id"] for r in (existing.data or [])]
    except APIError as e:
        message = str(getattr(e, "message", "") or "")
        if "youtube_video_id" in message:
            print("WARN: recipes.youtube_video_id が未作成です（014 migration 未適用）。重複スキップなしで続行します。")
            exclude_ids = []
        else:
            raise

    if staple_name:
        async with httpx.AsyncClient(timeout=60.0) as http_client:
            recipes, stats = await fetch_youtube_recipes_by_staple_from_channels(
                http_client,
                settings.youtube_api_key,
                channel_handles=channel_handles,
                staple_name=staple_name,
                max_results_per_channel=max_results_per_channel,
                exclude_video_ids=exclude_ids,
            )
    else:
        # 互換モード（従来）: チャンネル先頭1件を対象
        channel_handle = channel_handles[0] if channel_handles else "@Kurashiru"
        async with httpx.AsyncClient(timeout=60.0) as http_client:
            recipes, stats = await fetch_youtube_recipes(
                http_client,
                settings.youtube_api_key,
                channel_handle,
                max_results=max_results_per_channel,
                exclude_video_ids=exclude_ids,
                staple_name=staple_name,
            )

    print(f"取得結果: {stats}")

    # 既存パイプライン: upsert → 食材マッチング → 栄養計算
    for i, r in enumerate(recipes):
        rid = await recipe_repo.upsert_recipe(supabase, r)
        ingredients = r.get("ingredients", [])
        if ingredients:
            await match_recipe_ingredients(supabase, rid, ingredients)
            await calculate_recipe_nutrition(supabase, rid)
        print(f"  {i + 1}/{len(recipes)}: {r['title']}")

    print(f"完了: {len(recipes)} レシピ登録")


async def cmd_check_youtube_transcript():
    """YouTube 字幕を1本取得し、品質チェックする。自動字幕なら Gemini で自然化する。"""
    if len(sys.argv) < 3:
        print("Usage: python -m app.services.data_loader check-youtube-transcript <video_url_or_id> [lang1,lang2,...]")
        sys.exit(1)

    video_ref = sys.argv[2].strip()
    langs = [x.strip() for x in sys.argv[3].split(",")] if len(sys.argv) >= 4 else ["ja", "ja-JP", "en"]

    result = await fetch_transcript(video_ref, languages=langs)
    print(
        "字幕取得:"
        f" video_id={result['video_id']},"
        f" lang={result['language_code']},"
        f" generated={result['is_generated']},"
        f" segments={result['quality']['segment_count']},"
        f" quality={result['quality']['quality_score']}"
    )
    if result["quality"]["notes"]:
        print("品質メモ:", ", ".join(result["quality"]["notes"]))

    text = result["text"]
    if result["is_generated"]:
        if not settings.google_api_key:
            print("WARN: 自動字幕だが GOOGLE_API_KEY 未設定のため自然化をスキップします。")
        else:
            print("自動字幕を Gemini で自然化中...")
            naturalized = await naturalize_auto_transcript(text)
            print("--- Naturalized Transcript (head) ---")
            print(naturalized[:2000])
            print("--- End ---")
            return

    print("--- Transcript (head) ---")
    print(text[:2000])
    print("--- End ---")


async def cmd_ingest_training_progressions():
    if len(sys.argv) < 3:
        print(
            "Usage: python -m app.services.data_loader ingest-training-progressions "
            "<@channel_handle> [title_keyword] [max_results]"
        )
        sys.exit(1)

    channel_handle = sys.argv[2].strip()
    title_keyword = sys.argv[3].strip() if len(sys.argv) >= 4 else "ができるなら"
    max_results = int(sys.argv[4]) if len(sys.argv) >= 5 and sys.argv[4].isdigit() else 25

    if not settings.youtube_api_key:
        print("ERROR: YOUTUBE_API_KEY is not set")
        sys.exit(1)
    if not settings.google_api_key:
        print("ERROR: GOOGLE_API_KEY is not set")
        sys.exit(1)

    supabase = await _get_service_client()
    async with httpx.AsyncClient(timeout=60.0) as http_client:
        results, stats = await ingest_training_progressions(
            supabase,
            http_client=http_client,
            api_key=settings.youtube_api_key,
            channel_handle=channel_handle,
            title_keyword=title_keyword,
            max_results=max_results,
        )

    print(
        f"training progression ingest: videos_scanned={stats.videos_scanned} "
        f"title_matched={stats.videos_title_matched} "
        f"videos_found={stats.videos_found} "
        f"transcripts_fetched={stats.transcripts_fetched} "
        f"transcripts_naturalized={stats.transcripts_naturalized} "
        f"videos_processed={stats.videos_processed} "
        f"videos_with_edges={stats.videos_with_edges} "
        f"edges_created={stats.edges_created}"
    )
    for result in results:
        print(f"- {result.video_title} [{result.status}] edges={result.edges_created} source_id={result.source_id}")
