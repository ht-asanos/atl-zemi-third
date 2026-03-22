"""レシピ管理 CLI コマンド"""

import json
import sys
from uuid import UUID

from app.config import settings
from app.repositories import recipe_repo
from app.services.cli._shared import _external_http_client, _get_service_client
from app.services.ingredient_matcher import calculate_recipe_nutrition, match_recipe_ingredients
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


async def cmd_backfill():
    """未マッチ食材の補完ジョブ"""
    supabase = await _get_service_client()
    async with _external_http_client() as http_client:
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
    async with _external_http_client() as http_client:
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
    async with _external_http_client() as http_client:
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
        # 主食指定なし取込のため is_accompaniment_for_staple() は不適用（Gemini ゲートでカバー）
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


async def cmd_prune_non_meal_recipes(*, execute: bool = False):
    """既存 recipes を品質ゲートで再判定し、非食事レシピを削除する。

    デフォルトは dry-run（削除候補をリスト表示のみ）。
    --execute フラグで実削除。削除前に prune_candidates.json を出力（rollback 用）。
    """
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
    for x in gate.rejected:
        print(f"  - {x['recipe'].get('title', '?')} (reason={x.get('reason', '?')})")

    if not reject_ids:
        print("削除対象なし")
        return

    # rollback 用 JSON 出力
    output_path = "prune_candidates.json"
    with open(output_path, "w") as f:
        json.dump(
            [{"id": x["recipe"].get("id"), "title": x["recipe"].get("title")} for x in gate.rejected],
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"削除候補を {output_path} に出力しました")

    if not execute:
        print("\n[dry-run] 実際の削除は --execute オプションで実行してください")
        return

    await supabase.table("recipe_ingredients").delete().in_("recipe_id", reject_ids).execute()
    await supabase.table("recipes").delete().in_("id", reject_ids).execute()
    print(f"非食事レシピを削除: {len(reject_ids)} 件")


async def cmd_repair_youtube_nutrition():
    """既存 YouTube レシピの材料マッチング・栄養計算を再実行する。"""
    supabase = await _get_service_client()

    recipes_resp = await (
        supabase.table("recipes")
        .select("id, title, recipe_url, nutrition_per_serving")
        .ilike("recipe_url", "%youtube%")
        .execute()
    )
    recipes = recipes_resp.data or []
    if not recipes:
        print("YouTube レシピがありません")
        return

    repaired = 0
    failed = 0
    matched_any = 0
    nutrition_ready = 0

    for i, r in enumerate(recipes, start=1):
        rid = r["id"]
        title = r.get("title", "")
        try:
            ing_resp = (
                await supabase.table("recipe_ingredients")
                .select("ingredient_name, amount_text")
                .eq("recipe_id", rid)
                .execute()
            )
            raw_ings = ing_resp.data or []
            if not raw_ings:
                print(f"{i}/{len(recipes)} SKIP(no ingredients): {title}")
                continue

            # 再マッチング用の入力整形
            ingredients = [
                {
                    "ingredient_name": ing.get("ingredient_name", ""),
                    "amount_text": ing.get("amount_text"),
                }
                for ing in raw_ings
                if ing.get("ingredient_name")
            ]
            if not ingredients:
                print(f"{i}/{len(recipes)} SKIP(no valid ingredients): {title}")
                continue

            # 既存行を置き換えてマッチング
            await supabase.table("recipe_ingredients").delete().eq("recipe_id", rid).execute()
            matched = await match_recipe_ingredients(supabase, UUID(rid), ingredients)
            nut = await calculate_recipe_nutrition(supabase, UUID(rid))

            repaired += 1
            if any(m.get("mext_food_id") for m in matched):
                matched_any += 1
            if nut.nutrition is not None:
                nutrition_ready += 1
            print(
                f"{i}/{len(recipes)} OK: {title} "
                f"(matched={nut.matched_count}/{nut.total_count}, status={nut.status.value})"
            )
        except Exception:
            failed += 1
            print(f"{i}/{len(recipes)} ERROR: {title}")

    print(
        "完了:"
        f" repaired={repaired}, failed={failed},"
        f" matched_any={matched_any}, nutrition_ready={nutrition_ready}"
    )


async def cmd_rebuild_recipe_ingredients():
    """既存 recipe_ingredients を材料名+分量でユニーク化して再構築する。"""
    supabase = await _get_service_client()

    recipes_resp = await supabase.table("recipes").select("id, title").execute()
    recipes = recipes_resp.data or []
    if not recipes:
        print("recipes が存在しません")
        return

    rebuilt = 0
    skipped = 0
    failed = 0

    for i, recipe in enumerate(recipes, start=1):
        rid = recipe["id"]
        title = recipe.get("title", "")
        try:
            ing_resp = (
                await supabase.table("recipe_ingredients")
                .select("ingredient_name, amount_text")
                .eq("recipe_id", rid)
                .execute()
            )
            raw_ings = ing_resp.data or []
            if not raw_ings:
                skipped += 1
                print(f"{i}/{len(recipes)} SKIP(no ingredients): {title}")
                continue

            deduped: list[dict[str, str | None]] = []
            seen: set[tuple[str, str | None]] = set()
            for ing in raw_ings:
                ingredient_name = (ing.get("ingredient_name") or "").strip()
                amount_text = ing.get("amount_text")
                key = (ingredient_name, amount_text)
                if not ingredient_name or key in seen:
                    continue
                seen.add(key)
                deduped.append(
                    {
                        "ingredient_name": ingredient_name,
                        "amount_text": amount_text,
                    }
                )

            if not deduped:
                skipped += 1
                print(f"{i}/{len(recipes)} SKIP(no deduped ingredients): {title}")
                continue

            matched = await match_recipe_ingredients(supabase, UUID(rid), deduped)
            nut = await calculate_recipe_nutrition(supabase, UUID(rid))
            rebuilt += 1
            print(
                f"{i}/{len(recipes)} OK: {title} "
                "(ingredients="
                f"{len(deduped)}, matched={nut.matched_count}/{nut.total_count}, "
                f"status={nut.status.value})"
            )
            if not matched:
                print(f"  WARN: no matched rows after rebuild: {title}")
        except Exception:
            failed += 1
            print(f"{i}/{len(recipes)} ERROR: {title}")

    print("完了:" f" rebuilt={rebuilt}, skipped={skipped}, failed={failed}")


async def cmd_normalize_ingredient_backfill():
    """正規化した材料名のうち、mext_foods 未登録項目を補完する。"""
    supabase = await _get_service_client()
    async with _external_http_client() as http_client:
        result = await backfill_missing_normalized_ingredients(supabase, http_client)

    print(f"正規化名: {result['normalized_names']}")
    print(f"追加食品: {result['added_foods']}")
    print(f"未取得名: {len(result['missing_names'])}")
    if result["missing_names"]:
        print("未取得サンプル:", ", ".join(result["missing_names"][:20]))
    if result["errors"]:
        print("エラー:", result["errors"])
