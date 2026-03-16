"""買い物リスト正規化のテスト。"""

from app.services.shopping_normalizer import (
    canonicalize_ingredient,
    clean_ingredient_name,
    is_purchasable,
    normalize_ingredient_candidates,
)


class TestCleanIngredientName:
    def test_strip_stars(self):
        assert clean_ingredient_name("★鶏もも肉★") == "鶏もも肉"

    def test_strip_mixed_symbols(self):
        assert clean_ingredient_name("●にんじん◎") == "にんじん"

    def test_remove_parentheses(self):
        assert clean_ingredient_name("卵（Mサイズ）") == "卵"

    def test_remove_half_width_parens(self):
        assert clean_ingredient_name("卵(Mサイズ)") == "卵"

    def test_remove_brackets(self):
        assert clean_ingredient_name("【必須】鶏肉") == "鶏肉"

    def test_trim_dots(self):
        assert clean_ingredient_name("・塩・") == "塩"

    def test_no_change_clean_name(self):
        assert clean_ingredient_name("鶏もも肉") == "鶏もも肉"


class TestCanonicalizeIngredient:
    def test_cooking_sake(self):
        assert canonicalize_ingredient("料理酒") == "酒"

    def test_nihonshu(self):
        assert canonicalize_ingredient("日本酒") == "酒"

    def test_koikuchi_soy_sauce(self):
        assert canonicalize_ingredient("濃口醤油") == "しょうゆ"

    def test_soy_sauce(self):
        assert canonicalize_ingredient("醤油") == "しょうゆ"

    def test_shouyu_variant(self):
        assert canonicalize_ingredient("しょう油") == "しょうゆ"

    def test_salad_oil(self):
        assert canonicalize_ingredient("サラダ油") == "油"

    def test_pepper_katakana(self):
        assert canonicalize_ingredient("コショウ") == "こしょう"

    def test_pepper_kanji(self):
        assert canonicalize_ingredient("胡椒") == "こしょう"

    def test_unknown_stays_same(self):
        assert canonicalize_ingredient("鶏もも肉") == "鶏もも肉"

    def test_cleaning_plus_synonym(self):
        assert canonicalize_ingredient("★料理酒★") == "酒"


class TestIsPurchasable:
    def test_water_not_purchasable(self):
        assert is_purchasable("水") is False

    def test_hot_water_not_purchasable(self):
        assert is_purchasable("お湯") is False

    def test_boiling_water_not_purchasable(self):
        assert is_purchasable("熱湯") is False

    def test_ice_not_purchasable(self):
        assert is_purchasable("氷") is False

    def test_chicken_purchasable(self):
        assert is_purchasable("鶏もも肉") is True

    def test_salt_purchasable(self):
        assert is_purchasable("塩") is True

    def test_decorated_water_not_purchasable(self):
        assert is_purchasable("★水★") is False


class TestNormalizeIngredientCandidates:
    def test_splits_alternatives(self):
        assert normalize_ingredient_candidates("〇醤油 / みりん / 酒") == ["しょうゆ", "みりん", "酒"]

    def test_ignores_parentheses(self):
        assert normalize_ingredient_candidates("生きしめん(うどんでも)") == ["生きしめん"]

    def test_drops_header(self):
        assert normalize_ingredient_candidates("材料（2人分）") == []

    def test_deduplicates_candidates(self):
        assert normalize_ingredient_candidates("麺つゆ/めんつゆ") == ["めんつゆ"]

    def test_drops_angle_only(self):
        assert normalize_ingredient_candidates("<") == []
        assert normalize_ingredient_candidates(">") == []

    def test_strips_leading_punctuation(self):
        assert normalize_ingredient_candidates("、卵") == ["卵"]
        assert normalize_ingredient_candidates("､卵") == ["卵"]
        assert normalize_ingredient_candidates("　、卵") == ["卵"]
