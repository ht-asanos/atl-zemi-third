"""栄養計算失敗時のフォールバック推定。

レシピのタグ・タイトルからカテゴリを推定し、平均的な栄養値を返す。
"""

from app.models.recipe import Recipe

CATEGORY_AVERAGES: dict[str, dict[str, float]] = {
    "肉": {"kcal": 400, "protein_g": 25.0, "fat_g": 18.0, "carbs_g": 20.0},
    "魚": {"kcal": 300, "protein_g": 22.0, "fat_g": 12.0, "carbs_g": 15.0},
    "野菜": {"kcal": 200, "protein_g": 8.0, "fat_g": 5.0, "carbs_g": 25.0},
    "default": {"kcal": 350, "protein_g": 20.0, "fat_g": 12.0, "carbs_g": 30.0},
}

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "肉": ["鶏", "豚", "牛", "ひき肉", "ハンバーグ", "唐揚げ", "焼肉"],
    "魚": ["魚", "鮭", "さば", "刺身", "海鮮", "エビ", "イカ"],
    "野菜": ["サラダ", "野菜", "煮物"],
}


def _detect_category(recipe: Recipe) -> str:
    """タグ・タイトルからカテゴリを推定する。"""
    text = recipe.title or ""
    tags = recipe.tags or []
    combined = text + " " + " ".join(tags)

    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                return category
    return "default"


def get_fallback_nutrition(recipe: Recipe) -> dict:
    """タグ・タイトルから推定栄養を返す。常に non-None を返す（最悪 default）。"""
    category = _detect_category(recipe)
    return dict(CATEGORY_AVERAGES[category])
