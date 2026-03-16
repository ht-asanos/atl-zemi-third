"""買い物リスト食材名の正規化。

装飾記号・括弧注釈の除去、同義語マッピング、非購買品目フィルタを提供する。
"""

from __future__ import annotations

import re

# --- テキストクリーニング ---
_STRIP_PATTERN = re.compile(r"[★☆●◎■□▲△◆◇※♪♫]")
_BRACKET_PATTERN = re.compile(r"[（\(][^）\)]*[）\)]|[【\[][^】\]]*[】\]]")
_TRIM_PATTERN = re.compile(r"^[\s・…]+|[\s・…]+$")
_HEADER_PATTERN = re.compile(r"^\s*<?\s*材料[^>]*>?\s*$")
_TAG_PATTERN = re.compile(r"<[^>]+>")
_PREFIX_HINT_PATTERN = re.compile(r"^\s*(あれば|あれば、|お好みで|お好みで、)\s*")
_LEADING_SYMBOL_PATTERN = re.compile(r"^\s*〇+")
_LEADING_PUNCT_PATTERN = re.compile(r"^[、。,.､，\s\u3000]+")
_ALT_SEP_PATTERN = re.compile(r"\s*(?:/|／|or|OR|でも|又は)\s*")


def clean_ingredient_name(name: str) -> str:
    """装飾記号・括弧注釈を除去する。"""
    name = _STRIP_PATTERN.sub("", name)
    name = _BRACKET_PATTERN.sub("", name)
    name = _TRIM_PATTERN.sub("", name)
    return name.strip()


# --- 同義語辞書 ---
SYNONYM_MAP: dict[str, str] = {
    "料理酒": "酒",
    "日本酒": "酒",
    "清酒": "酒",
    "濃口醤油": "しょうゆ",
    "薄口醤油": "しょうゆ",
    "醤油": "しょうゆ",
    "しょう油": "しょうゆ",
    "片栗粉": "かたくり粉",
    "サラダ油": "油",
    "サラダオイル": "油",
    "コショウ": "こしょう",
    "胡椒": "こしょう",
    "麺つゆ": "めんつゆ",
    "あごだしつゆ": "めんつゆ",
    "つゆ": "めんつゆ",
    "カマボコ": "かまぼこ",
    "ネギ": "ねぎ",
}


def canonicalize_ingredient(name: str) -> str:
    """クリーニング + 同義語マッピング。"""
    cleaned = clean_ingredient_name(name)
    return SYNONYM_MAP.get(cleaned, cleaned)


# --- 購買フィルタ ---
NON_PURCHASABLE_NAMES = {"水", "氷", "湯", "お湯", "熱湯"}


def is_purchasable(ingredient_name: str, category_name: str | None = None) -> bool:
    """購買不要品目を判定する。"""
    canonical = canonicalize_ingredient(ingredient_name)
    return canonical not in NON_PURCHASABLE_NAMES


def _preclean(name: str) -> str:
    s = name.strip()
    if _HEADER_PATTERN.match(s):
        return ""
    s = _TAG_PATTERN.sub("", s)
    s = _LEADING_SYMBOL_PATTERN.sub("", s)
    s = _LEADING_PUNCT_PATTERN.sub("", s)
    s = _PREFIX_HINT_PATTERN.sub("", s)
    s = _BRACKET_PATTERN.sub("", s)
    s = _STRIP_PATTERN.sub("", s)
    s = _TRIM_PATTERN.sub("", s)
    if s in {"<", ">"}:
        return ""
    return s.strip()


def normalize_ingredient_candidates(name: str) -> list[str]:
    """1つの材料表記を購買候補の配列へ展開する。

    例:
      "〇醤油 / みりん / 酒" -> ["しょうゆ", "みりん", "酒"]
      "生きしめん(うどんでも)" -> ["生きしめん"]
    """
    s = _preclean(name)
    if not s:
        return []

    parts = [p.strip() for p in _ALT_SEP_PATTERN.split(s) if p.strip()]
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        c = canonicalize_ingredient(p)
        # 区切り記号や全角空白が混入した先頭ノイズを最終的に除去する
        c = c.lstrip("、。,.､， \u3000").strip()
        if not c:
            continue
        if c in seen:
            continue
        seen.add(c)
        out.append(c)
    return out
