"""レシピ多様性フィルタ

カテゴリ分類 + 段階的緩和で週間プラン内の同カテゴリ重複を抑制する。
"""

from __future__ import annotations

import re
import unicodedata


def _normalize_title(title: str) -> str:
    """全角→半角、記号除去、小文字化"""
    s = unicodedata.normalize("NFKC", title)
    s = re.sub(r"[★☆●◎■□▲△◆◇※♪♫!！?？\s　]", "", s)
    return s.lower()


# 判定順序が優先度（上ほど強い）
RECIPE_CATEGORIES: list[tuple[str, list[str]]] = [
    # --- 強カテゴリ（料理形態が明確） ---
    ("カレー", ["カレー", "かれー"]),
    ("鍋", ["鍋", "ポトフ", "おでん", "しゃぶしゃぶ", "すき焼き", "すきやき"]),
    ("丼", ["丼", "どんぶり"]),
    ("グラタン", ["グラタン", "ドリア", "ぐらたん", "どりあ"]),
    ("ハンバーグ", ["ハンバーグ", "はんばーぐ"]),
    ("餃子", ["餃子", "ぎょうざ", "シュウマイ", "焼売", "しゅうまい"]),
    # --- 麺カテゴリ ---
    ("うどん", ["うどん"]),
    ("そば", ["そば", "蕎麦"]),
    ("パスタ", ["パスタ", "スパゲッティ", "ペンネ", "マカロニ", "ぱすた"]),
    ("ラーメン", ["ラーメン", "らーめん"]),
    # --- 調理法カテゴリ ---
    ("炒飯", ["チャーハン", "炒飯", "ピラフ", "ちゃーはん", "ぴらふ"]),
    (
        "揚げ物",
        [
            "揚げ",
            "フライ",
            "天ぷら",
            "唐揚げ",
            "コロッケ",
            "カツ",
            "ふらい",
            "てんぷら",
            "からあげ",
            "ころっけ",
            "かつ",
        ],
    ),
    ("炒め物", ["炒め", "チンジャオ", "回鍋肉", "麻婆", "ホイコーロー", "いため"]),
    ("煮物", ["煮物", "煮込み", "肉じゃが", "筑前煮", "にもの", "にこみ"]),
    ("スープ", ["スープ", "味噌汁", "みそ汁", "豚汁", "シチュー", "すーぷ", "しちゅー"]),
    ("サラダ", ["サラダ", "さらだ"]),
]

# 正規化済みキーワードのキャッシュ
_NORMALIZED_CATEGORIES: list[tuple[str, list[str]]] | None = None


def _get_normalized_categories() -> list[tuple[str, list[str]]]:
    global _NORMALIZED_CATEGORIES
    if _NORMALIZED_CATEGORIES is None:
        _NORMALIZED_CATEGORIES = [
            (cat, [_normalize_title(kw) for kw in keywords]) for cat, keywords in RECIPE_CATEGORIES
        ]
    return _NORMALIZED_CATEGORIES


def classify_recipe(title: str) -> str | None:
    """タイトルからカテゴリを判定。優先順位付き、先にマッチしたものを採用。"""
    normalized = _normalize_title(title)
    for category, keywords in _get_normalized_categories():
        if any(kw in normalized for kw in keywords):
            return category
    return None


def classify_recipe_multi(title: str) -> set[str]:
    """タイトルからマッチする全カテゴリを返す。"""
    normalized = _normalize_title(title)
    cats = set()
    for category, keywords in _get_normalized_categories():
        if any(kw in normalized for kw in keywords):
            cats.add(category)
    return cats


class DiversityFilter:
    """段階的緩和つき多様性フィルタ（マルチラベル対応）"""

    def __init__(self, max_same: int = 1):
        self._max_same = max_same
        self._counts: dict[str, int] = {}

    @property
    def max_same(self) -> int:
        return self._max_same

    def can_add(self, title: str) -> bool:
        cats = classify_recipe_multi(title)
        if not cats:
            return True
        return all(self._counts.get(cat, 0) < self._max_same for cat in cats)

    def mark_added(self, title: str) -> None:
        for cat in classify_recipe_multi(title):
            self._counts[cat] = self._counts.get(cat, 0) + 1

    def relax(self) -> DiversityFilter:
        """上限を +1 緩和した新インスタンスを返す（カウントは引き継ぐ）"""
        relaxed = DiversityFilter(max_same=self._max_same + 1)
        relaxed._counts = dict(self._counts)
        return relaxed
