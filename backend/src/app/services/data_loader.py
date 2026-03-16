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
from app.services.gemini_display_name import generate_display_names
from app.services.ingredient_matcher import calculate_recipe_nutrition, match_recipe_ingredients
from app.services.mext_scraper import bulk_scrape_category
from app.services.rakuten_recipe import (
    build_category_index,
    fetch_category_list,
    fetch_multiple_categories,
    find_category_ids_by_keywords,
)
from app.services.recipe_quality_gate import filter_meal_like_recipes
from app.services.recipe_refresh import (
    backfill_missing_normalized_ingredients,
    backfill_unmatched_ingredients,
    refresh_stale_recipes,
)

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
        fetched_recipes = await fetch_multiple_categories(
            http_client, settings.rakuten_app_id, settings.rakuten_access_key, RAKUTEN_CATEGORY_IDS
        )
        gate = await filter_meal_like_recipes(fetched_recipes)
        recipes = gate.accepted
        print(f"  取得 {len(fetched_recipes)} 件 / 採用 {len(recipes)} 件 / 除外 {len(gate.rejected)} 件")
        if gate.rejected:
            sample = ", ".join(x["recipe"].get("title", "?") for x in gate.rejected[:5])
            print(f"  除外例: {sample}")

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
        normalized = await backfill_missing_normalized_ingredients(supabase, http_client)
        print(
            "正規化材料補完:"
            f" names={normalized['normalized_names']},"
            f" added_foods={normalized['added_foods']},"
            f" missing={len(normalized['missing_names'])},"
            f" errors={len(normalized['errors'])}"
        )
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


async def cmd_fetch_recipes_by_keyword():
    """キーワード一致カテゴリから楽天レシピを取得して投入する。"""
    if not settings.rakuten_app_id:
        print("ERROR: RAKUTEN_APP_ID is not set")
        sys.exit(1)
    if not settings.rakuten_access_key:
        print("ERROR: RAKUTEN_ACCESS_KEY is not set")
        sys.exit(1)

    if len(sys.argv) < 3:
        print(
            "Usage: python -m app.services.data_loader "
            "fetch-recipes-by-keyword <keyword1,keyword2,...> [max_categories]"
        )
        sys.exit(1)

    keywords = [x.strip() for x in sys.argv[2].split(",") if x.strip()]
    max_categories = int(sys.argv[3]) if len(sys.argv) >= 4 else 20
    if not keywords:
        print("ERROR: keywords are empty")
        sys.exit(1)

    supabase = await _get_service_client()
    async with httpx.AsyncClient(timeout=30.0, verify=False) as http_client:
        categories = await fetch_category_list(http_client, settings.rakuten_app_id, settings.rakuten_access_key)
        category_index = build_category_index(categories)
        category_ids = find_category_ids_by_keywords(category_index, keywords, max_categories=max_categories)

        if not category_ids:
            print(f"カテゴリ抽出0件 keywords={keywords}")
            return

        print(f"抽出カテゴリ数: {len(category_ids)}")
        print("category_ids:", ", ".join(category_ids))

        fetched_recipes = await fetch_multiple_categories(
            http_client, settings.rakuten_app_id, settings.rakuten_access_key, category_ids
        )
        gate = await filter_meal_like_recipes(fetched_recipes)
        recipes = gate.accepted
        print(f"取得 {len(fetched_recipes)} 件 / 採用 {len(recipes)} 件 / 除外 {len(gate.rejected)} 件")
        if gate.rejected:
            sample = ", ".join(x["recipe"].get("title", "?") for x in gate.rejected[:10])
            print(f"除外例: {sample}")

        recipe_ids = []
        for r in recipes:
            rid = await recipe_repo.upsert_recipe(supabase, r)
            recipe_ids.append(rid)

        for i, (rid, r) in enumerate(zip(recipe_ids, recipes, strict=True)):
            ingredients = r.get("ingredients", [])
            if ingredients:
                await match_recipe_ingredients(supabase, rid, ingredients)
                await calculate_recipe_nutrition(supabase, rid)
            if (i + 1) % 10 == 0:
                print(f"  {i + 1}/{len(recipe_ids)} 完了")

        print(f"投入完了: recipes={len(recipe_ids)}")


async def cmd_update_display_names():
    """既存レコードの display_name を Gemini で一括生成する。"""
    supabase = await _get_service_client()

    total_updated = 0
    while True:
        foods = await mext_food_repo.get_foods_without_display_name(supabase, limit=200)
        if not foods:
            break

        print(f"  {len(foods)} 件の未処理レコードを取得")
        raw_names = [f.name for f in foods]
        display_names = await generate_display_names(raw_names)

        updates: list[tuple] = []
        for food, dn in zip(foods, display_names, strict=True):
            if dn is not None and food.id is not None:
                updates.append((food.id, dn))

        if updates:
            count = await mext_food_repo.update_display_names(supabase, updates)
            total_updated += count
            print(f"  → {count} 件更新 (累計: {total_updated})")
        else:
            print("  → 有効な display_name なし、スキップ")
            # None のままのレコードが残り続けるので無限ループを防ぐ
            break

    print(f"display_name 更新完了: 合計 {total_updated} 件")


async def cmd_prune_non_meal_recipes():
    """既存 recipes を品質ゲートで再判定し、非食事レシピを削除する。"""
    supabase = await _get_service_client()

    resp = await supabase.table("recipes").select("id,title,description,tags").execute()
    rows = resp.data or []
    if not rows:
        print("recipes が存在しません")
        return

    ing_resp = await supabase.table("recipe_ingredients").select("recipe_id,ingredient_name").execute()
    ing_rows = ing_resp.data or []
    ing_map: dict[str, list[dict]] = {}
    for row in ing_rows:
        rid = row.get("recipe_id")
        if not rid:
            continue
        ing_map.setdefault(rid, []).append({"ingredient_name": row.get("ingredient_name", ""), "amount_text": None})

    recipes = []
    for r in rows:
        recipes.append(
            {
                "id": r.get("id"),
                "title": r.get("title", ""),
                "description": r.get("description", ""),
                "tags": r.get("tags") or [],
                "ingredients": ing_map.get(r.get("id"), []),
            }
        )

    gate = await filter_meal_like_recipes(recipes)
    reject_ids = [x["recipe"].get("id") for x in gate.rejected if x["recipe"].get("id")]
    reject_ids = [x for x in reject_ids if x]

    print(f"総レシピ: {len(recipes)} / 除外候補: {len(reject_ids)}")
    if gate.rejected:
        sample = ", ".join(x["recipe"].get("title", "?") for x in gate.rejected[:10])
        print(f"除外例: {sample}")
    if not reject_ids:
        print("削除対象なし")
        return

    await supabase.table("recipe_ingredients").delete().in_("recipe_id", reject_ids).execute()
    await supabase.table("recipes").delete().in_("id", reject_ids).execute()
    print(f"非食事レシピを削除: {len(reject_ids)} 件")


async def cmd_normalize_ingredient_backfill():
    """正規化した材料名のうち、mext_foods 未登録項目を補完する。"""
    supabase = await _get_service_client()
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        result = await backfill_missing_normalized_ingredients(supabase, http_client)

    print(f"正規化名: {result['normalized_names']}")
    print(f"追加食品: {result['added_foods']}")
    print(f"未取得名: {len(result['missing_names'])}")
    if result["missing_names"]:
        print("未取得サンプル:", ", ".join(result["missing_names"][:20]))
    if result["errors"]:
        print("エラー:", result["errors"])


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python -m app.services.data_loader "
            "<init|backfill|refresh-recipes|fetch-recipes-by-keyword|update-display-names|"
            "prune-non-meal-recipes|normalize-ingredient-backfill>"
        )
        sys.exit(1)

    command = sys.argv[1]
    commands = {
        "init": cmd_init,
        "backfill": cmd_backfill,
        "refresh-recipes": cmd_refresh_recipes,
        "fetch-recipes-by-keyword": cmd_fetch_recipes_by_keyword,
        "update-display-names": cmd_update_display_names,
        "prune-non-meal-recipes": cmd_prune_non_meal_recipes,
        "normalize-ingredient-backfill": cmd_normalize_ingredient_backfill,
    }

    if command not in commands:
        print(f"Unknown command: {command}")
        print(f"Available: {', '.join(commands)}")
        sys.exit(1)

    asyncio.run(commands[command]())


if __name__ == "__main__":
    main()
