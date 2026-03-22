"""付け合わせレシピ除外フィルターのテスト"""

import uuid

import pytest
from app.models.food import NutritionStatus
from app.models.recipe import Recipe
from app.repositories.recipe_repo import _matches_staple_filter
from app.utils.text_normalize import is_accompaniment_for_staple

# --- is_accompaniment_for_staple 単体テスト ---


@pytest.mark.parametrize(
    "title, staple_short_name, expected",
    [
        ("うどんのつけ汁", "うどん", True),
        ("肉うどん", "うどん", False),
        ("カレーうどん", "うどん", False),
        ("鍋焼きうどん", "うどん", False),
        ("うどんつゆ", "うどん", True),
        ("パスタソース", "パスタ", True),
        ("ナポリタン", "パスタ", False),
        ("ふりかけ丼", "ご飯", True),
        ("何か", "オートミール", False),  # エントリなし → スキップ
    ],
)
def test_is_accompaniment_for_staple(title: str, staple_short_name: str, expected: bool) -> None:
    result = is_accompaniment_for_staple(title, staple_short_name)
    assert result == expected


def test_is_accompaniment_full_width_normalization() -> None:
    """全角キーワードも正規化後に一致すること。"""
    assert is_accompaniment_for_staple("うどんのつゆ", "うどん") is True


def test_is_accompaniment_katakana_normalized() -> None:
    """カタカナ→ひらがな正規化後に一致すること。"""
    # "タレ" → "たれ" に正規化されて "パスタ" の suffix "たれ" とマッチ
    assert is_accompaniment_for_staple("パスタたれ", "パスタ") is True


# --- _matches_staple_filter 統合テスト ---


def _make_recipe(title: str, tags: list[str] | None = None) -> Recipe:
    return Recipe(
        id=uuid.uuid4(),
        rakuten_recipe_id=None,
        title=title,
        description=None,
        image_url=None,
        recipe_url="https://example.com",
        ingredients=[],
        nutrition_per_serving=None,
        servings=2,
        cooking_minutes=None,
        cost_estimate=None,
        tags=tags or [],
        is_nutrition_calculated=False,
        nutrition_status=NutritionStatus.CALCULATED,
        generated_steps=[],
        steps_status="pending",
        youtube_video_id=None,
        recipe_source="rakuten",
        ingredient_nutrition_coverage={},
    )


def test_matches_staple_filter_includes_normal_udon() -> None:
    """うどんレシピは主食フィルタを通過する。"""
    recipe = _make_recipe("肉うどん", tags=["うどん"])
    assert _matches_staple_filter(recipe, ["うどん"], ["うどん"], "うどん") is True


def test_matches_staple_filter_excludes_accompaniment() -> None:
    """付け合わせレシピは主食フィルタで除外される。"""
    recipe = _make_recipe("うどんのつけ汁", tags=["うどん"])
    assert _matches_staple_filter(recipe, ["うどん"], ["うどん"], "うどん") is False


def test_matches_staple_filter_no_short_name_keeps_existing_behavior() -> None:
    """staple_short_name=None のとき、付け合わせ除外は行われない（既存挙動不変）。"""
    recipe = _make_recipe("うどんのつけ汁", tags=["うどん"])
    assert _matches_staple_filter(recipe, ["うどん"], ["うどん"], None) is True


def test_matches_staple_filter_no_match_returns_false() -> None:
    """主食タグもキーワードも一致しない場合は False。"""
    recipe = _make_recipe("ハンバーグ", tags=["肉料理"])
    assert _matches_staple_filter(recipe, ["うどん"], ["うどん"], "うどん") is False


def test_matches_staple_filter_pasta_sauce_excluded() -> None:
    """パスタソースはパスタ主食フィルタで除外される。"""
    recipe = _make_recipe("パスタソース", tags=["パスタ"])
    assert _matches_staple_filter(recipe, ["パスタ"], ["パスタ"], "パスタ") is False


def test_matches_staple_filter_napolitana_included() -> None:
    """ナポリタンはパスタレシピとして通過する（付け合わせではない）。"""
    recipe = _make_recipe("ナポリタン", tags=["パスタ"])
    assert _matches_staple_filter(recipe, ["パスタ"], ["パスタ"], "パスタ") is True


# --- _is_likely_non_meal セーフティネットテスト ---


def test_is_likely_non_meal_catches_tsukejiru() -> None:
    """ "つけ汁" を含むタイトルは True になる。"""
    from app.repositories.recipe_repo import _is_likely_non_meal

    assert _is_likely_non_meal("うどんのつけ汁") is True


def test_is_likely_non_meal_catches_tsukedare() -> None:
    """ "つけだれ" を含むタイトルは True になる。"""
    from app.repositories.recipe_repo import _is_likely_non_meal

    assert _is_likely_non_meal("焼き鳥のつけだれ") is True


def test_is_likely_non_meal_catches_kaeshi() -> None:
    """ "かえし" を含むタイトルは True になる。"""
    from app.repositories.recipe_repo import _is_likely_non_meal

    assert _is_likely_non_meal("そばのかえし") is True


def test_is_likely_non_meal_passes_normal() -> None:
    """通常の料理タイトルは False になる。"""
    from app.repositories.recipe_repo import _is_likely_non_meal

    assert _is_likely_non_meal("鍋焼きうどん") is False
    assert _is_likely_non_meal("カレーうどん") is False
    assert _is_likely_non_meal("親子丼") is False


def test_is_likely_non_meal_conservative_no_jam() -> None:
    """ "ジャム" はリストに含まないため False になる（誤除外リスク回避）。"""
    from app.repositories.recipe_repo import _is_likely_non_meal

    assert _is_likely_non_meal("ジャムのケーキ") is False


def test_is_likely_non_meal_tsuyudaku_passes() -> None:
    """ "つゆだく牛丼" は料理名の一部なので False になる。"""
    from app.repositories.recipe_repo import _is_likely_non_meal

    assert _is_likely_non_meal("つゆだく牛丼") is False
