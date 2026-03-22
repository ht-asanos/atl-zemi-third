"""食材名マッチング + 栄養計算

レシピ食材を MEXT 食品成分データと紐付け、栄養価を算出する。

マッチング戦略:
1. キャッシュ確認 (ingredient_mext_cache)
2. trigram 類似度検索 (confidence >= 0.6 で自動採用)
3. Gemini フォールバック (match_recipe_ingredients のバッチ処理のみ)
"""

import logging
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.config import settings
from app.models.food import NutritionStatus
from app.repositories import ingredient_cache_repo, mext_food_repo
from app.services.gemini_mext_matcher import gemini_match_batch
from app.services.shopping_normalizer import _preclean, clean_ingredient_name
from postgrest.exceptions import APIError

from supabase import AsyncClient

logger = logging.getLogger(__name__)

# --- Unit Conversion ---

# 単位変換テーブル（食材名, 単位） → グラム
# 食材名が None の場合は汎用変換
UNIT_CONVERSIONS: dict[tuple[str | None, str], float] = {
    ("卵", "個"): 60,
    ("玉ねぎ", "個"): 200,
    ("じゃがいも", "個"): 150,
    ("にんじん", "本"): 150,
    ("豆腐", "丁"): 300,
    ("豆腐", "パック"): 300,
    (None, "カップ"): 200,
    (None, "cc"): 1,
    (None, "ml"): 1,
    (None, "g"): 1,
    (None, "kg"): 1000,
    ("鶏もも肉", "枚"): 250,
    ("鶏むね肉", "枚"): 250,
    ("鶏胸肉", "枚"): 250,
    ("ささみ", "本"): 50,
    ("鶏ささみ", "本"): 50,
    ("長ねぎ", "本"): 100,
    ("ねぎ", "本"): 100,
    ("きゅうり", "本"): 100,
    ("なす", "本"): 80,
    ("ナス", "本"): 80,
    ("大根", "cm"): 30,
    ("しょうが", "かけ"): 15,
    ("生姜", "かけ"): 15,
    ("にんにく", "かけ"): 5,
    ("にんにく", "片"): 5,
    ("ニンニク", "かけ"): 5,
    ("ニンニク", "片"): 5,
    ("ベーコン", "枚"): 18,
    ("ハム", "枚"): 10,
    ("チーズ", "枚"): 18,
    ("餅", "個"): 50,
    ("バター", "かけ"): 10,
    ("たまご", "個"): 60,
    ("玉子", "個"): 60,
    ("トマト", "個"): 150,
    ("ピーマン", "個"): 30,
    ("パプリカ", "個"): 150,
    ("キャベツ", "玉"): 1000,
    ("レタス", "玉"): 300,
    ("白菜", "枚"): 80,
    (None, "少々"): 2,
    (None, "ひとつまみ"): 1,
}

# 計量スプーン換算（大さじ基準、g）
# 食材別の密度差を大まかに反映する。
_SPOON_TABLESPOON_G: list[tuple[tuple[str, ...], float]] = [
    (("しょうゆ", "醤油", "みりん", "酒", "酢", "めんつゆ", "つゆ"), 15.0),
    (("油", "オイル", "ごま油", "オリーブ"), 12.0),
    (("塩", "食塩"), 18.0),
    (("砂糖", "上白糖"), 9.0),
    (("味噌", "みそ"), 18.0),
    (("小麦粉", "薄力粉", "強力粉", "片栗粉", "でん粉"), 9.0),
]

_UNIT_NAME_ALIASES: dict[str, str] = {
    "たまねぎ": "玉ねぎ",
    "タマネギ": "玉ねぎ",
    "ねぎ": "長ねぎ",
    "ネギ": "長ねぎ",
    "にんにく": "ニンニク",
}

# --- MEXT Matching ---

MEXT_SYNONYM_MAP: dict[str, str] = {
    "たまご": "鶏卵",
    "タマゴ": "鶏卵",
    "玉子": "鶏卵",
    "卵": "鶏卵",
    "溶き卵": "鶏卵",
    "ゆで卵": "鶏卵",
    # MEXT raw 名寄せ（実データは「にわとり」「ぶた」表記が多い）
    "鶏もも肉": "にわとり もも 皮つき",
    "鶏むね肉": "にわとり むね 皮つき",
    "鶏胸肉": "にわとり むね 皮つき",
    "ささみ": "にわとり ささみ",
    "鶏ささみ": "にわとり ささみ",
    "鶏ひき肉": "にわとり ひき肉",
    "豚バラ肉": "ぶた ばら 脂身つき",
    "豚バラ": "ぶた ばら 脂身つき",
    "豚こま切れ肉": "ぶた もも 脂身つき",
    "豚こま": "ぶた もも 脂身つき",
    "豚ロース": "ぶた ロース 脂身つき",
    "豚ひき肉": "ぶた ひき肉",
    "合いびき肉": "合いびき肉",
    "合挽き肉": "合いびき肉",
    "牛こま切れ肉": "うし もも 脂身つき",
    "牛薄切り肉": "うし もも 脂身つき",
    "手羽先": "にわとり 手羽先 皮つき",
    "手羽元": "にわとり 手羽元 皮つき",
    "豚肩ロース": "ぶた かたロース 脂身つき",
    "牛ひき肉": "うし ひき肉",
    "ウインナー": "ウインナーソーセージ",
    "ウィンナー": "ウインナーソーセージ",
    "ソーセージ": "ウインナーソーセージ",
    "ハム": "ロースハム",
    "ツナ": "まぐろ 缶詰 水煮",
    "ツナ缶": "まぐろ 缶詰 水煮",
    "かまぼこ": "蒸しかまぼこ",
    "カマボコ": "蒸しかまぼこ",
    "竹輪": "焼きちくわ",
    "ちくわ": "焼きちくわ",
    "豆腐": "木綿豆腐",
    "厚揚げ": "生揚げ",
    "鮭": "しろさけ 生",
    "サバ": "まさば 生",
    "エビ": "くるまえび 生",
    "いか": "するめいか 生",
    "じゃがいも": "じゃがいも 塊茎",
    "ジャガイモ": "じゃがいも 塊茎",
    "玉ねぎ": "たまねぎ りん茎",
    "たまねぎ": "たまねぎ りん茎",
    "タマネギ": "たまねぎ りん茎",
    "にんじん": "にんじん 根",
    "ニンジン": "にんじん 根",
    "人参": "にんじん 根",
    "大根": "だいこん 根",
    "キャベツ": "キャベツ 結球葉",
    "白菜": "はくさい 結球葉",
    "ほうれん草": "ほうれんそう 葉",
    "長ねぎ": "根深ねぎ 葉",
    "ネギ": "ねぎ 葉",
    "ねぎ": "ねぎ 葉",
    "もやし": "りょくとうもやし",
    "しめじ": "ぶなしめじ",
    "えのき": "えのきたけ",
    "なす": "なす 果実",
    "ナス": "なす 果実",
    "きゅうり": "きゅうり 果実",
    "トマト": "トマト 果実",
    "ミニトマト": "ミニトマト 果実",
    "ピーマン": "ピーマン 果実",
    "小松菜": "こまつな 葉",
    "ブロッコリー": "ブロッコリー 花序",
    "アスパラガス": "アスパラガス 若茎",
    "かぼちゃ": "西洋かぼちゃ 果実",
    "れんこん": "れんこん 根茎",
    "しょうが": "しょうが 根茎",
    "生姜": "しょうが 根茎",
    "にんにく": "にんにく りん茎",
    "ニンニク": "にんにく りん茎",
    "しょうゆ": "こいくちしょうゆ",
    "醤油": "こいくちしょうゆ",
    "みそ": "米みそ 淡色辛みそ",
    "味噌": "米みそ 淡色辛みそ",
    "みりん": "本みりん",
    "砂糖": "上白糖",
    "塩": "食塩",
    "酢": "穀物酢",
    "バター": "有塩バター",
    "マヨネーズ": "マヨネーズ 全卵型",
    "ごま油": "ごま油",
    "オリーブオイル": "オリーブ油",
    "サラダ油": "調合油",
    "片栗粉": "じゃがいもでん粉",
    "小麦粉": "薄力粉",
    "牛乳": "普通牛乳",
    "チーズ": "プロセスチーズ",
    "ポン酢": "ぽん酢しょうゆ",
    "ぽんず": "ぽん酢しょうゆ",
    "ポン酢しょうゆ": "ぽん酢しょうゆ",
    "めんつゆ": "めんつゆ ストレート",
    "ケチャップ": "トマトケチャップ",
    "コンソメ": "固形コンソメ",
    "鶏ガラスープの素": "鶏がらだし",
    "オイスターソース": "オイスターソース",
    "豆板醤": "豆板醤",
    "ラー油": "ラー油",
    "ご飯": "精白米 うるち米",
    "白米": "精白米 うるち米",
    "米": "精白米 うるち米",
    "うどん": "うどん ゆで",
    "冷凍うどん": "うどん ゆで",
    "ゆでうどん": "うどん ゆで",
    "長ネギ": "根深ねぎ 葉",
    "舞茸": "まいたけ 生",
    "胡椒": "こしょう",
    "黒胡椒": "こしょう 黒",
    "鰹節": "かつお節",
    "かつおぶし": "かつお節",
    "白だし": "だししょうゆ",
    "だし汁": "かつおだし",
    "粉チーズ": "チーズ パルメザン",
    "そうめん": "そうめん ゆで",
    "そば": "そば ゆで",
    "中華麺": "中華めん ゆで",
    "食パン": "食パン",
    "パスタ": "マカロニ・スパゲッティ 乾",
    "スパゲッティ": "マカロニ・スパゲッティ 乾",
}

# confidence 閾値
CONFIDENCE_AUTO_MATCH = 0.6
CONFIDENCE_MANUAL_REVIEW = 0.3
DEFAULT_INGREDIENT_AMOUNT_G = 100.0

# 栄養的に無視できる食材（水・塩コショウなど）— マッチ不要だが coverage を下げない
NEGLIGIBLE_INGREDIENTS: set[str] = {
    "水",
    "お湯",
    "氷",
    "塩コショウ",
    "塩胡椒",
    "塩こしょう",
}

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
    units = r"(g|kg|ml|cc|個|本|丁|パック|大さじ|小さじ|カップ|枚|切れ|束|袋|cm|かけ|片|玉|少々|ひとつまみ)"
    text = re.sub(r"\s+", " ", text)
    # "名前 1/2個" パターン
    m = re.match(rf"(.+?)\s+(\d+)/(\d+)\s*{units}", text)
    if m:
        name = m.group(1).strip()
        amount = float(m.group(2)) / float(m.group(3))
        grams = _convert_to_grams(name, amount, m.group(4))
        return name, grams

    # "名前 1と1/2本" パターン
    m = re.match(rf"(.+?)\s+(\d+)と(\d+)/(\d+)\s*{units}", text)
    if m:
        name = m.group(1).strip()
        amount = float(m.group(2)) + float(m.group(3)) / float(m.group(4))
        grams = _convert_to_grams(name, amount, m.group(5))
        return name, grams

    # "名前 数値単位" パターン
    m = re.match(rf"(.+?)\s+(\d+(?:\.\d+)?)\s*{units}", text)
    if m:
        name = m.group(1).strip()
        amount = float(m.group(2))
        unit = m.group(3)
        grams = _convert_to_grams(name, amount, unit)
        return name, grams

    # "名前 各大さじ2" / "名前 大さじ2"（単位+数値）
    m = re.match(rf"(.+?)\s+(?:各)?\s*{units}\s*(\d+(?:\.\d+)?)", text)
    if m:
        name = m.group(1).strip()
        unit = m.group(2)
        amount = float(m.group(3))
        grams = _convert_to_grams(name, amount, unit)
        return name, grams

    # "名前 少々" / "名前 ひとつまみ"
    m = re.match(rf"(.+?)\s*{units}$", text)
    if m and m.group(2) in {"少々", "ひとつまみ"}:
        name = m.group(1).strip()
        grams = _convert_to_grams(name, 1.0, m.group(2))
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
    normalized_name = name.strip()
    normalized_name = _UNIT_NAME_ALIASES.get(normalized_name, normalized_name)

    # スプーン系は食材に応じた密度で換算
    if unit in {"大さじ", "小さじ"}:
        spoon_g = _tablespoon_grams_for_ingredient(normalized_name)
        if spoon_g is not None:
            if unit == "小さじ":
                spoon_g /= 3.0
            result = amount * spoon_g
            return result if result > 0 else None

    # 食材固有の変換
    key = (normalized_name, unit)
    if key in UNIT_CONVERSIONS:
        result = amount * UNIT_CONVERSIONS[key]
        return result if result > 0 else None

    # 汎用変換
    generic_key = (None, unit)
    if generic_key in UNIT_CONVERSIONS:
        result = amount * UNIT_CONVERSIONS[generic_key]
        return result if result > 0 else None

    return None


def _tablespoon_grams_for_ingredient(name: str) -> float:
    for keywords, grams in _SPOON_TABLESPOON_G:
        if any(k in name for k in keywords):
            return grams
    return 15.0


def _normalize_for_mext(name: str) -> tuple[str, bool]:
    """食材名を MEXT マッチング向けに正規化する。

    Returns: (正規化名, 同義語辞書ヒットしたか)
    """
    pre = _preclean(name)
    cleaned = clean_ingredient_name(pre if pre else name.strip())
    mapped = MEXT_SYNONYM_MAP.get(cleaned)
    if mapped is not None:
        return mapped, True
    return cleaned, False


def estimate_amount_g(ingredient_name: str) -> float:
    """分量不明時の簡易推定グラムを返す。"""
    name = ingredient_name.strip()
    if any(keyword in name for keyword in _LIGHT_INGREDIENT_KEYWORDS):
        return 10.0
    if any(keyword in name for keyword in _OIL_KEYWORDS):
        return 12.0
    return DEFAULT_INGREDIENT_AMOUNT_G


async def _trigram_match(
    supabase: AsyncClient,
    normalized_name: str,
    synonym_hit: bool,
) -> tuple[UUID | None, float, list[dict[str, Any]]]:
    """trigram 検索を実行し、(best_id, confidence, all_candidates) を返す。"""
    try:
        response = await supabase.rpc(
            "similarity_search_mext_foods",
            {"search_name": normalized_name, "threshold": CONFIDENCE_MANUAL_REVIEW},
        ).execute()
    except APIError as e:
        # ローカル環境で RPC 未適用の場合のフォールバック
        if "similarity_search_mext_foods" not in str(e):
            raise
        candidates = await mext_food_repo.search_by_name(supabase, normalized_name, limit=5)
        if not candidates:
            return None, 0.0, []
        best = candidates[0]
        # シンプルな近似 confidence。厳しめに手動レビュー寄りに倒す。
        confidence = 0.6 if normalized_name in best.name else 0.4
        # fallback: trigram 精度がないため弱めのブースト
        if synonym_hit and confidence >= 0.5:
            confidence = min(confidence + 0.05, 0.65)
        return best.id, confidence, []

    rows: list[dict[str, Any]] = response.data or []
    if not rows:
        return None, 0.0, rows

    best = rows[0]
    confidence = float(best["similarity"])
    # RPC 経路: trigram + synonym 辞書のダブル裏付けがあるため +0.10 / cap 0.85
    if synonym_hit and confidence >= 0.5:
        confidence = min(confidence + 0.10, 0.85)
    return best["id"], confidence, rows


async def _get_wider_candidates(
    supabase: AsyncClient,
    normalized_name: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Gemini 評価用に広い候補セットを取得。

    まず threshold=0.25 で RPC 検索。RPC に name フィールドがあれば利用。
    候補が 3 件未満なら ILIKE 検索で補完し、重複排除して返す。
    """
    candidates: dict[str, dict[str, Any]] = {}

    # RPC で trigram 候補を取得（name フィールドがあれば利用）
    for threshold in (0.25, 0.15):
        try:
            response = await supabase.rpc(
                "similarity_search_mext_foods",
                {"search_name": normalized_name, "threshold": threshold},
            ).execute()
            for row in response.data or []:
                row_id = row.get("id")
                row_name = row.get("name")
                if row_id and row_name and row_id not in candidates:
                    candidates[row_id] = {"id": row_id, "name": row_name}
            if len(candidates) >= 3:
                break
        except APIError:
            break

    # ILIKE で補完（RPC に name がない場合、または候補が少ない場合）
    if len(candidates) < 3:
        ilike_foods = await mext_food_repo.search_by_name(supabase, normalized_name, limit=limit)
        for food in ilike_foods:
            food_id = str(food.id) if food.id else None
            if food_id and food_id not in candidates:
                candidates[food_id] = {"id": food_id, "name": food.name}

    return list(candidates.values())[:limit]


async def match_ingredient(
    supabase: AsyncClient,
    ingredient_name: str,
) -> tuple[UUID | None, float]:
    """食材名を MEXT 食品 DB で検索し、(mext_food_id, confidence) を返す。

    cache → trigram の順に検索する。Gemini は呼ばない。
    （Gemini フォールバックは match_recipe_ingredients のバッチ処理のみ）
    """
    normalized_name, synonym_hit = _normalize_for_mext(ingredient_name)

    # 1. キャッシュ確認（TTL 考慮済み）
    cached = await ingredient_cache_repo.get_cached(supabase, normalized_name)
    if cached is not None:
        return cached  # (mext_food_id, confidence)

    # 2. trigram 検索
    mext_id, confidence, _candidates = await _trigram_match(supabase, normalized_name, synonym_hit)

    # 3. auto-match → キャッシュして返却
    if confidence >= CONFIDENCE_AUTO_MATCH:
        await ingredient_cache_repo.set_cached(supabase, normalized_name, mext_id, confidence, "trigram")

    return mext_id, confidence


async def match_recipe_ingredients(
    supabase: AsyncClient,
    recipe_id: UUID,
    ingredients: list[dict],
) -> list[dict]:
    """レシピの全食材をマッチングして recipe_ingredients に保存する。

    低信頼食材は Gemini バッチで一括再評価する（API key が設定されている場合のみ）。
    """
    # raw 材料行とマッチ済み行の二重登録を防ぐため、常に置換する。
    await supabase.table("recipe_ingredients").delete().eq("recipe_id", str(recipe_id)).execute()

    results: list[dict] = []
    gemini_pending: list[tuple[int, str]] = []  # (index, normalized_name)

    for i, ing in enumerate(ingredients):
        name = ing.get("ingredient_name", "")
        amount_text = ing.get("amount_text")
        parsed_name, amount_g = parse_ingredient_text(f"{name} {amount_text}" if amount_text else name)

        is_negligible = parsed_name in NEGLIGIBLE_INGREDIENTS
        mext_food_id, confidence = await match_ingredient(supabase, parsed_name)

        # Gemini 候補収集用に正規化名を取得
        normalized_name, _ = _normalize_for_mext(parsed_name)

        record = {
            "recipe_id": str(recipe_id),
            "ingredient_name": name,
            "amount_text": amount_text,
            "amount_g": amount_g,
            "mext_food_id": str(mext_food_id) if mext_food_id else None,
            "match_confidence": confidence,
            "manual_review_needed": (
                False if is_negligible else CONFIDENCE_MANUAL_REVIEW <= confidence < CONFIDENCE_AUTO_MATCH
            ),
            "is_negligible": is_negligible,
        }
        results.append(record)

        # Gemini 候補収集（非 negligible かつ低信頼かつ API key あり）
        if not is_negligible and confidence < CONFIDENCE_AUTO_MATCH and settings.google_api_key:
            gemini_pending.append((i, normalized_name))

    # バッチ Gemini（候補取得 → Gemini 呼出し → 結果反映）
    if gemini_pending:
        batch_items: list[tuple[int, str, list[dict[str, Any]]]] = []
        for idx, norm_name in gemini_pending:
            wider = await _get_wider_candidates(supabase, norm_name)
            if wider:
                batch_items.append((idx, norm_name, wider))

        if batch_items:
            gem_input = [(norm_name, cands) for _, norm_name, cands in batch_items]
            gem_results = await gemini_match_batch(gem_input)

            cache_entries: list[dict[str, Any]] = []
            for (idx, norm_name, _), gr in zip(batch_items, gem_results, strict=True):
                if gr.mext_food_id:
                    results[idx]["mext_food_id"] = gr.mext_food_id
                    results[idx]["match_confidence"] = gr.confidence
                    results[idx]["manual_review_needed"] = False
                    cache_entries.append(
                        {
                            "normalized_name": norm_name,
                            "mext_food_id": gr.mext_food_id,
                            "confidence": gr.confidence,
                            "source": "gemini",
                        }
                    )
                else:
                    cache_entries.append(
                        {
                            "normalized_name": norm_name,
                            "mext_food_id": None,
                            "confidence": 0.0,
                            "source": "no_match",
                        }
                    )

            if cache_entries:
                await ingredient_cache_repo.set_cached_batch(supabase, cache_entries)

    if results:
        await supabase.table("recipe_ingredients").insert(results).execute()

    return results


# --- Nutrition Calculation ---


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
        # 栄養的に無視できる食材は coverage を下げない
        if row.get("is_negligible"):
            matched_count += 1
            continue

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
