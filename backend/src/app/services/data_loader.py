"""データ投入・定期更新 CLI

使用方法:
    uv run python -m app.services.data_loader init
    uv run python -m app.services.data_loader backfill
    uv run python -m app.services.data_loader refresh-recipes
"""

import asyncio
import sys

import httpx
from app.config import settings
from app.repositories import mext_food_repo, recipe_repo
from app.services.ingredient_matcher import calculate_recipe_nutrition, match_recipe_ingredients
from app.services.mext_scraper import bulk_scrape_category
from app.services.rakuten_recipe import fetch_multiple_categories
from app.services.recipe_refresh import backfill_unmatched_ingredients, refresh_stale_recipes

from supabase import acreate_client

# 優先カテゴリ
PRIORITY_CATEGORIES = ["01", "04", "06", "08", "09", "10", "11", "12", "13"]

# 楽天レシピの対象カテゴリ（小カテゴリ）
RAKUTEN_CATEGORY_IDS = [
    "30-300",  # ご飯もの
    "15-138",  # クリーム系パスタ
    "10-277",  # 鶏肉
    "10-276",  # 豚肉
    "32-343",  # 焼き魚
    "33-353",  # だし巻き卵・卵焼き
    "35-471",  # 木綿豆腐
    "18-417",  # 大根サラダ
    "17-169",  # 野菜スープ
]


async def _get_service_client():
    """service-role key を使った AsyncClient を作成する。"""
    if not settings.supabase_service_role_key:
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY is not set")
        sys.exit(1)
    return await acreate_client(settings.supabase_url, settings.supabase_service_role_key)


async def cmd_init():
    """初期投入: MEXT スクレイピング → 楽天レシピ取得 → 食材マッチング → 栄養計算"""
    supabase = await _get_service_client()

    # 1. MEXT 食品データのスクレイピング
    print("=== MEXT 食品データ取得 ===")
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        total_foods = 0
        for cat_code in PRIORITY_CATEGORIES:
            print(f"  カテゴリ {cat_code} をスクレイピング中...")
            foods = await bulk_scrape_category(http_client, cat_code)
            if foods:
                count = await mext_food_repo.upsert_foods(supabase, foods)
                total_foods += count
                print(f"    → {count} 件 upsert")
            else:
                print("    → 0 件")
        print(f"MEXT 合計: {total_foods} 件")

    # 2. 楽天レシピ取得
    if not settings.rakuten_app_id:
        print("WARN: RAKUTEN_APP_ID is not set, skipping recipe fetch")
        return
    if not settings.rakuten_access_key:
        print("WARN: RAKUTEN_ACCESS_KEY is not set, skipping recipe fetch")
        return

    print("\n=== 楽天レシピ取得 ===")
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        recipes = await fetch_multiple_categories(
            http_client, settings.rakuten_app_id, settings.rakuten_access_key, RAKUTEN_CATEGORY_IDS
        )
        print(f"  {len(recipes)} レシピ取得")

        # レシピを DB に保存
        recipe_ids = []
        for r in recipes:
            rid = await recipe_repo.upsert_recipe(supabase, r)
            recipe_ids.append(rid)
        print(f"  {len(recipe_ids)} レシピ保存")

    # 3. 食材マッチング + 栄養計算
    print("\n=== 食材マッチング + 栄養計算 ===")
    for i, (rid, r) in enumerate(zip(recipe_ids, recipes, strict=True)):
        ingredients = r.get("ingredients", [])
        if ingredients:
            await match_recipe_ingredients(supabase, rid, ingredients)
            await calculate_recipe_nutrition(supabase, rid)
        if (i + 1) % 10 == 0:
            print(f"  {i + 1}/{len(recipe_ids)} 完了")
    print(f"  全 {len(recipe_ids)} レシピの処理完了")


async def cmd_backfill():
    """未マッチ食材の補完ジョブ"""
    supabase = await _get_service_client()
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        result = await backfill_unmatched_ingredients(supabase, http_client)
    print(f"未マッチ: {result.unmatched_before} → 補完後マッチ: {result.matched_after}")
    print(f"スクレイピング食品: {result.scraped_foods}, 残り未マッチ: {result.still_unmatched}")
    if result.errors:
        print(f"エラー: {result.errors}")


async def cmd_refresh_recipes():
    """楽天レシピの定期更新（fetched_at が 7 日超のカテゴリを再取得）"""
    if not settings.rakuten_app_id:
        print("ERROR: RAKUTEN_APP_ID is not set")
        sys.exit(1)
    if not settings.rakuten_access_key:
        print("ERROR: RAKUTEN_ACCESS_KEY is not set")
        sys.exit(1)

    supabase = await _get_service_client()
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        result = await refresh_stale_recipes(
            supabase,
            http_client,
            settings.rakuten_app_id,
            settings.rakuten_access_key,
        )
    print(f"チェック: {result.categories_checked}, 更新: {result.categories_refreshed}")
    print(f"レシピ更新: {result.recipes_updated}")
    if result.errors:
        print(f"エラー: {result.errors}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m app.services.data_loader <init|backfill|refresh-recipes>")
        sys.exit(1)

    command = sys.argv[1]
    commands = {
        "init": cmd_init,
        "backfill": cmd_backfill,
        "refresh-recipes": cmd_refresh_recipes,
    }

    if command not in commands:
        print(f"Unknown command: {command}")
        print(f"Available: {', '.join(commands)}")
        sys.exit(1)

    asyncio.run(commands[command]())


if __name__ == "__main__":
    main()
