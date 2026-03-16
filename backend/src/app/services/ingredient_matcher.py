"""食材名マッチング + 栄養計算

レシピ食材を MEXT 食品成分データと紐付け、栄養価を算出する。
"""

import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.models.food import NutritionStatus
from app.repositories import mext_food_repo
from postgrest.exceptions import APIError

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
DEFAULT_INGREDIENT_AMOUNT_G = 100.0

# 楽天ランキングAPIは分量を持たないケースが多いため、最低限の推定グラムを使う。
_LIGHT_INGREDIENT_KEYWORDS = (
    "塩",
    "こしょう",
    "胡椒",
    "しょうゆ",
    "醤油",
    "みそ",
    "味噌",
    "みりん",
    "酢",
    "砂糖",
    "だし",
    "コンソメ",
    "鶏ガラ",
    "顆粒",
    "めんつゆ",
    "ソース",
    "ケチャップ",
)
_OIL_KEYWORDS = ("油", "オイル", "ごま油", "オリーブ")


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


def estimate_amount_g(ingredient_name: str) -> float:
    """分量不明時の簡易推定グラムを返す。"""
    name = ingredient_name.strip()
    if any(keyword in name for keyword in _LIGHT_INGREDIENT_KEYWORDS):
        return 10.0
    if any(keyword in name for keyword in _OIL_KEYWORDS):
        return 12.0
    return DEFAULT_INGREDIENT_AMOUNT_G


async def match_ingredient(
    supabase: AsyncClient,
    ingredient_name: str,
) -> tuple[UUID | None, float]:
    """食材名を MEXT 食品 DB で検索し、(mext_food_id, confidence) を返す。

    trigram 類似度を使用してマッチングする。
    """
    try:
        response = await supabase.rpc(
            "similarity_search_mext_foods",
            {"search_name": ingredient_name, "threshold": CONFIDENCE_MANUAL_REVIEW},
        ).execute()
    except APIError as e:
        # ローカル環境で RPC 未適用の場合のフォールバック
        if "similarity_search_mext_foods" not in str(e):
            raise
        candidates = await mext_food_repo.search_by_name(supabase, ingredient_name, limit=5)
        if not candidates:
            return None, 0.0
        best = candidates[0]
        # シンプルな近似 confidence。厳しめに手動レビュー寄りに倒す。
        confidence = 0.6 if ingredient_name in best.name else 0.4
        return best.id, confidence

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


@dataclass
class NutritionResult:
    nutrition: dict | None
    status: NutritionStatus
    matched_count: int
    total_count: int


async def calculate_recipe_nutrition(supabase: AsyncClient, recipe_id: UUID) -> NutritionResult:
    """レシピの栄養価を計算する。

    confidence >= CONFIDENCE_AUTO_MATCH かつ amount_g が設定されている食材のみ集計。
    全食材が計算に使えない場合は FAILED を返す。
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
    matched_count = 0
    total_count = len(rows)

    for row in rows:
        confidence = row.get("match_confidence") or 0.0
        amount_g = row.get("amount_g")
        mext = row.get("mext_foods")
        ingredient_id = row.get("id")

        ingredient_kcal = None
        ingredient_protein = None
        ingredient_fat = None
        ingredient_carbs = None

        if mext:
            effective_amount_g = amount_g if amount_g is not None else estimate_amount_g(row.get("ingredient_name", ""))
            ratio = effective_amount_g / 100.0
            ingredient_kcal = round(mext["kcal_per_100g"] * ratio, 1)
            ingredient_protein = round(mext["protein_g_per_100g"] * ratio, 1)
            ingredient_fat = round(mext["fat_g_per_100g"] * ratio, 1)
            ingredient_carbs = round(mext["carbs_g_per_100g"] * ratio, 1)

            # 各食材の栄養を recipe_ingredients に保持する
            if ingredient_id:
                await (
                    supabase.table("recipe_ingredients")
                    .update(
                        {
                            "amount_g": effective_amount_g,
                            "kcal": ingredient_kcal,
                            "protein_g": ingredient_protein,
                            "fat_g": ingredient_fat,
                            "carbs_g": ingredient_carbs,
                        }
                    )
                    .eq("id", str(ingredient_id))
                    .execute()
                )

        if confidence < CONFIDENCE_AUTO_MATCH or ingredient_kcal is None:
            all_matched = False
            continue

        has_valid = True
        matched_count += 1
        total_kcal += ingredient_kcal
        total_protein += ingredient_protein or 0.0
        total_fat += ingredient_fat or 0.0
        total_carbs += ingredient_carbs or 0.0

    # Determine status
    if not has_valid:
        nutrition_status = NutritionStatus.FAILED
    elif all_matched:
        nutrition_status = NutritionStatus.CALCULATED
    else:
        nutrition_status = NutritionStatus.ESTIMATED

    nutrition = None
    if has_valid:
        nutrition = {
            "kcal": round(total_kcal, 1),
            "protein_g": round(total_protein, 1),
            "fat_g": round(total_fat, 1),
            "carbs_g": round(total_carbs, 1),
        }

    # レシピの栄養情報を更新
    update_data: dict[str, Any] = {
        "is_nutrition_calculated": all_matched,
        "nutrition_status": nutrition_status.value,
    }
    if nutrition is not None:
        update_data["nutrition_per_serving"] = nutrition

    await supabase.table("recipes").update(update_data).eq("id", str(recipe_id)).execute()

    return NutritionResult(
        nutrition=nutrition,
        status=nutrition_status,
        matched_count=matched_count,
        total_count=total_count,
    )
