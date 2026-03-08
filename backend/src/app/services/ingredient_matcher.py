"""食材名マッチング + 栄養計算

レシピ食材を MEXT 食品成分データと紐付け、栄養価を算出する。
"""

import re
from typing import Any
from uuid import UUID

from supabase import AsyncClient

# 単位変換テーブル（食材名, 単位） → グラム
# 食材名が None の場合は汎用変換
UNIT_CONVERSIONS: dict[tuple[str | None, str], float] = {
    ("卵", "個"): 60,
    ("玉ねぎ", "個"): 200,
    ("じゃがいも", "個"): 150,
    ("にんじん", "本"): 150,
    ("豆腐", "丁"): 300,
    ("豆腐", "パック"): 300,
    (None, "大さじ"): 15,
    (None, "小さじ"): 5,
    (None, "カップ"): 200,
    (None, "cc"): 1,
    (None, "ml"): 1,
    (None, "g"): 1,
    (None, "kg"): 1000,
}

# confidence 閾値
CONFIDENCE_AUTO_MATCH = 0.6
CONFIDENCE_MANUAL_REVIEW = 0.3


def parse_ingredient_text(text: str) -> tuple[str, float | None]:
    """食材テキストを (名前, グラム数) にパースする。

    例: "鶏もも肉 200g" → ("鶏もも肉", 200.0)
         "卵 2個" → ("卵", 120.0)  ※ UNIT_CONVERSIONS で変換
         "塩コショウ 少々" → ("塩コショウ", None)
    """
    text = text.strip()
    # "名前 数値単位" パターン
    m = re.match(r"(.+?)\s+(\d+(?:\.\d+)?)\s*(g|kg|ml|cc|個|本|丁|パック|大さじ|小さじ|カップ|枚|切れ|束|袋)", text)
    if m:
        name = m.group(1).strip()
        amount = float(m.group(2))
        unit = m.group(3)
        grams = _convert_to_grams(name, amount, unit)
        return name, grams

    # "名前 数値" (単位なし → g と仮定)
    m2 = re.match(r"(.+?)\s+(\d+(?:\.\d+)?)$", text)
    if m2:
        name = m2.group(1).strip()
        return name, float(m2.group(2))

    # パースできない場合
    return text, None


def _convert_to_grams(name: str, amount: float, unit: str) -> float | None:
    """単位からグラムに変換する。"""
    # 食材固有の変換
    key = (name, unit)
    if key in UNIT_CONVERSIONS:
        return amount * UNIT_CONVERSIONS[key]

    # 汎用変換
    generic_key = (None, unit)
    if generic_key in UNIT_CONVERSIONS:
        return amount * UNIT_CONVERSIONS[generic_key]

    return None


async def match_ingredient(
    supabase: AsyncClient,
    ingredient_name: str,
) -> tuple[UUID | None, float]:
    """食材名を MEXT 食品 DB で検索し、(mext_food_id, confidence) を返す。

    trigram 類似度を使用してマッチングする。
    """
    response = await supabase.rpc(
        "similarity_search_mext_foods",
        {"search_name": ingredient_name, "threshold": CONFIDENCE_MANUAL_REVIEW},
    ).execute()

    rows: list[dict[str, Any]] = response.data or []
    if not rows:
        return None, 0.0

    best = rows[0]
    return best["id"], best["similarity"]


async def match_recipe_ingredients(
    supabase: AsyncClient,
    recipe_id: UUID,
    ingredients: list[dict],
) -> list[dict]:
    """レシピの全食材をマッチングして recipe_ingredients に保存する。"""
    results: list[dict] = []
    for ing in ingredients:
        name = ing.get("ingredient_name", "")
        amount_text = ing.get("amount_text")
        parsed_name, amount_g = parse_ingredient_text(f"{name} {amount_text}" if amount_text else name)

        mext_food_id, confidence = await match_ingredient(supabase, parsed_name)

        manual_review = CONFIDENCE_MANUAL_REVIEW <= confidence < CONFIDENCE_AUTO_MATCH
        record = {
            "recipe_id": str(recipe_id),
            "ingredient_name": name,
            "amount_text": amount_text,
            "amount_g": amount_g,
            "mext_food_id": str(mext_food_id) if mext_food_id else None,
            "match_confidence": confidence,
            "manual_review_needed": manual_review,
        }
        results.append(record)

    if results:
        await supabase.table("recipe_ingredients").insert(results).execute()

    return results


async def calculate_recipe_nutrition(supabase: AsyncClient, recipe_id: UUID) -> dict | None:
    """レシピの栄養価を計算する。

    confidence >= CONFIDENCE_AUTO_MATCH かつ amount_g が設定されている食材のみ集計。
    全食材が計算に使えない場合は None を返す。
    """
    resp = await (
        supabase.table("recipe_ingredients").select("*, mext_foods(*)").eq("recipe_id", str(recipe_id)).execute()
    )
    rows: list[dict[str, Any]] = resp.data or []

    total_kcal = 0.0
    total_protein = 0.0
    total_fat = 0.0
    total_carbs = 0.0
    has_valid = False
    all_matched = True

    for row in rows:
        confidence = row.get("match_confidence") or 0.0
        amount_g = row.get("amount_g")
        mext = row.get("mext_foods")

        if confidence < CONFIDENCE_AUTO_MATCH or not amount_g or not mext:
            all_matched = False
            continue

        has_valid = True
        ratio = amount_g / 100.0
        total_kcal += mext["kcal_per_100g"] * ratio
        total_protein += mext["protein_g_per_100g"] * ratio
        total_fat += mext["fat_g_per_100g"] * ratio
        total_carbs += mext["carbs_g_per_100g"] * ratio

    if not has_valid:
        return None

    nutrition = {
        "kcal": round(total_kcal, 1),
        "protein_g": round(total_protein, 1),
        "fat_g": round(total_fat, 1),
        "carbs_g": round(total_carbs, 1),
    }

    # レシピの栄養情報を更新
    await (
        supabase.table("recipes")
        .update(
            {
                "nutrition_per_serving": nutrition,
                "is_nutrition_calculated": all_matched,
            }
        )
        .eq("id", str(recipe_id))
        .execute()
    )

    return nutrition
