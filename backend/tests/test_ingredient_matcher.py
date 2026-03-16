"""食材マッチング + confidence のテスト"""

from app.models.food import NutritionStatus
from app.services.ingredient_matcher import (
    CONFIDENCE_AUTO_MATCH,
    CONFIDENCE_MANUAL_REVIEW,
    NutritionResult,
    _convert_to_grams,
    estimate_amount_g,
    parse_ingredient_text,
)


class TestParseIngredientText:
    def test_grams(self):
        name, g = parse_ingredient_text("鶏もも肉 200g")
        assert name == "鶏もも肉"
        assert g == 200.0

    def test_kg(self):
        name, g = parse_ingredient_text("豚肉 1.5kg")
        assert name == "豚肉"
        assert g == 1500.0

    def test_tablespoon(self):
        name, g = parse_ingredient_text("醤油 2大さじ")
        assert name == "醤油"
        assert g == 30.0

    def test_teaspoon(self):
        name, g = parse_ingredient_text("塩 1小さじ")
        assert name == "塩"
        assert g == 5.0

    def test_egg_count(self):
        name, g = parse_ingredient_text("卵 2個")
        assert name == "卵"
        assert g == 120.0

    def test_tofu(self):
        name, g = parse_ingredient_text("豆腐 1丁")
        assert name == "豆腐"
        assert g == 300.0

    def test_onion(self):
        name, g = parse_ingredient_text("玉ねぎ 1個")
        assert name == "玉ねぎ"
        assert g == 200.0

    def test_ml(self):
        name, g = parse_ingredient_text("だし汁 100ml")
        assert name == "だし汁"
        assert g == 100.0

    def test_no_amount(self):
        name, g = parse_ingredient_text("塩コショウ 少々")
        assert name == "塩コショウ 少々"
        assert g is None

    def test_plain_number(self):
        name, g = parse_ingredient_text("鶏肉 200")
        assert name == "鶏肉"
        assert g == 200.0

    def test_just_name(self):
        name, g = parse_ingredient_text("塩コショウ")
        assert name == "塩コショウ"
        assert g is None


class TestConvertToGrams:
    def test_specific_food_unit(self):
        assert _convert_to_grams("卵", 3, "個") == 180.0

    def test_generic_unit(self):
        assert _convert_to_grams("水", 1, "カップ") == 200.0

    def test_unknown_unit(self):
        assert _convert_to_grams("何か", 1, "房") is None


class TestConfidenceThresholds:
    def test_auto_match_threshold(self):
        assert CONFIDENCE_AUTO_MATCH == 0.6

    def test_manual_review_threshold(self):
        assert CONFIDENCE_MANUAL_REVIEW == 0.3

    def test_auto_match_higher_than_manual(self):
        assert CONFIDENCE_AUTO_MATCH > CONFIDENCE_MANUAL_REVIEW


class TestEstimateAmountG:
    def test_seasoning_defaults_to_10g(self):
        assert estimate_amount_g("塩") == 10.0
        assert estimate_amount_g("しょうゆ") == 10.0

    def test_oil_defaults_to_12g(self):
        assert estimate_amount_g("ごま油") == 12.0
        assert estimate_amount_g("オリーブオイル") == 12.0

    def test_other_defaults_to_100g(self):
        assert estimate_amount_g("鶏もも肉") == 100.0


class TestNutritionResult:
    def test_calculated_status(self):
        result = NutritionResult(
            nutrition={"kcal": 300, "protein_g": 20, "fat_g": 10, "carbs_g": 30},
            status=NutritionStatus.CALCULATED,
            matched_count=5,
            total_count=5,
        )
        assert result.status == NutritionStatus.CALCULATED
        assert result.nutrition is not None

    def test_estimated_status(self):
        result = NutritionResult(
            nutrition={"kcal": 200, "protein_g": 15, "fat_g": 8, "carbs_g": 25},
            status=NutritionStatus.ESTIMATED,
            matched_count=3,
            total_count=5,
        )
        assert result.status == NutritionStatus.ESTIMATED
        assert result.matched_count < result.total_count

    def test_failed_status(self):
        result = NutritionResult(
            nutrition=None,
            status=NutritionStatus.FAILED,
            matched_count=0,
            total_count=5,
        )
        assert result.status == NutritionStatus.FAILED
        assert result.nutrition is None
