"""MEXT データ操作 CLI コマンド"""

import sys
from pathlib import Path

from app.repositories import mext_food_repo
from app.services.cli._shared import _external_http_client, _get_service_client
from app.services.gemini_display_name import generate_display_names
from app.services.mext_excel_loader import load_foods_from_excel
from app.services.mext_scraper import bulk_scrape_category

# 優先カテゴリ
PRIORITY_CATEGORIES = ["01", "04", "06", "08", "09", "10", "11", "12", "13"]


async def cmd_init():
    """初期投入: MEXT スクレイピング → 楽天レシピ取得 → 食材マッチング → 栄養計算"""
    from app.config import settings
    from app.repositories import recipe_repo
    from app.services.ingredient_matcher import calculate_recipe_nutrition, match_recipe_ingredients
    from app.services.rakuten_recipe import fetch_multiple_categories
    from app.services.recipe_quality_gate import filter_meal_like_recipes

    supabase = await _get_service_client()

    # 1. MEXT 食品データのスクレイピング
    print("=== MEXT 食品データ取得 ===")
    async with _external_http_client() as http_client:
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
    from app.services.cli.recipe_commands import RAKUTEN_CATEGORY_IDS

    async with _external_http_client() as http_client:
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


async def cmd_load_mext_excel():
    """MEXT 食品成分 Excel を一括登録する（ファイル or ディレクトリ）。"""
    if len(sys.argv) < 3:
        print("Usage: python -m app.services.data_loader load-mext-excel <excel_path_or_dir>")
        sys.exit(1)

    input_path = Path(sys.argv[2])
    if not input_path.exists():
        print(f"ERROR: path not found: {input_path}")
        sys.exit(1)

    excel_paths = [input_path] if input_path.is_file() else sorted(input_path.glob("*.xlsx"))
    if not excel_paths:
        print(f"ERROR: no .xlsx files found under: {input_path}")
        sys.exit(1)

    all_foods = []
    total_skipped = 0
    total_zero_kcal = 0
    fallback_cols: set[str] = set()

    for p in excel_paths:
        foods, stats = load_foods_from_excel(p)
        all_foods.extend(foods)
        total_skipped += stats["skipped"]
        total_zero_kcal += stats["zero_kcal"]
        fallback_cols.update(stats["fallback_cols"])

    # mext_food_id 重複時は最後の定義で上書き（ファイル名順）。
    dedup: dict[str, object] = {}
    for f in all_foods:
        dedup[f.mext_food_id] = f
    foods = list(dedup.values())

    print(
        f"Parsed files={len(excel_paths)}, foods={len(foods)} "
        f"(raw_rows={len(all_foods)}, skipped={total_skipped}, zero_kcal={total_zero_kcal})"
    )
    if fallback_cols:
        print(f"WARNING: Fallback columns used: {sorted(fallback_cols)}")

    supabase = await _get_service_client()
    print("Replacing mext_foods (clear existing mappings -> reload from Excel)...")
    # 全置換モード:
    # 1) 既存の紐付けを外す（FK制約回避）
    await (
        supabase.table("recipe_ingredients")
        .update(
            {
                "mext_food_id": None,
                "match_confidence": None,
                "manual_review_needed": True,
            }
        )
        .not_.is_("mext_food_id", "null")
        .execute()
    )
    # 2) mext_foods を全削除
    await supabase.table("mext_foods").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    # 3) Excel から再投入
    count = await mext_food_repo.upsert_foods(supabase, foods)
    print(f"Reloaded mext_foods: {count}")

    # 4) ingredient_mext_cache を明示的にクリア
    # ON DELETE CASCADE により mext_foods 行削除時に cache 行も消えるが、
    # 全削除→再投入の場合は明示的 TRUNCATE が確実。
    from app.repositories import ingredient_cache_repo

    await ingredient_cache_repo.clear_all(supabase)
    print("ingredient_mext_cache cleared after mext_foods reload")
