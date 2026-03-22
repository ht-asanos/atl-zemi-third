"""食材マッチング + confidence のテスト"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.models.food import NutritionStatus
from app.services.ingredient_matcher import (
    CONFIDENCE_AUTO_MATCH,
    CONFIDENCE_MANUAL_REVIEW,
    MEXT_SYNONYM_MAP,
    NEGLIGIBLE_INGREDIENTS,
    NutritionResult,
    _convert_to_grams,
    _normalize_for_mext,
    estimate_amount_g,
    match_ingredient,
    match_recipe_ingredients,
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
        assert g == 6.0

    def test_tablespoon_unit_before_number(self):
        name, g = parse_ingredient_text("醤油 大さじ2")
        assert name == "醤油"
        assert g == 30.0

    def test_tablespoon_with_each_prefix(self):
        name, g = parse_ingredient_text("醤油 各大さじ2")
        assert name == "醤油"
        assert g == 30.0

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

    def test_onion_notation_variant(self):
        name, g = parse_ingredient_text("たまねぎ 1個")
        assert name == "たまねぎ"
        assert g == 200.0

    def test_ml(self):
        name, g = parse_ingredient_text("だし汁 100ml")
        assert name == "だし汁"
        assert g == 100.0

    def test_no_amount(self):
        name, g = parse_ingredient_text("塩コショウ 少々")
        assert name == "塩コショウ"
        assert g == 2.0

    def test_plain_number(self):
        name, g = parse_ingredient_text("鶏肉 200")
        assert name == "鶏肉"
        assert g == 200.0

    def test_just_name(self):
        name, g = parse_ingredient_text("塩コショウ")
        assert name == "塩コショウ"
        assert g is None

    def test_half_onion_fraction(self):
        name, g = parse_ingredient_text("玉ねぎ 1/2個")
        assert name == "玉ねぎ"
        assert g == 100.0

    def test_mixed_fraction(self):
        name, g = parse_ingredient_text("にんじん 1と1/2本")
        assert name == "にんじん"
        assert g == 225.0

    def test_pinch_without_number(self):
        name, g = parse_ingredient_text("塩 少々")
        assert name == "塩"
        assert g == 2.0

    def test_hitotsumami_without_number(self):
        name, g = parse_ingredient_text("塩 ひとつまみ")
        assert name == "塩"
        assert g == 1.0


class TestConvertToGrams:
    def test_specific_food_unit(self):
        assert _convert_to_grams("卵", 3, "個") == 180.0

    def test_generic_unit(self):
        assert _convert_to_grams("水", 1, "カップ") == 200.0

    def test_oil_tablespoon_density(self):
        assert _convert_to_grams("ごま油", 1, "大さじ") == 12.0

    def test_sugar_tablespoon_density(self):
        assert _convert_to_grams("砂糖", 1, "大さじ") == 9.0

    def test_unknown_unit(self):
        assert _convert_to_grams("何か", 1, "房") is None

    def test_daikon_cm(self):
        assert _convert_to_grams("大根", 5, "cm") == 150.0

    def test_bacon_slices(self):
        assert _convert_to_grams("ベーコン", 3, "枚") == 54.0

    def test_no_zero_return(self):
        assert _convert_to_grams("塩", 0, "少々") is None


class TestNormalizeForMext:
    def test_egg_variants(self):
        assert _normalize_for_mext("たまご") == ("鶏卵", True)
        assert _normalize_for_mext("玉子") == ("鶏卵", True)
        assert _normalize_for_mext("卵") == ("鶏卵", True)

    def test_meat(self):
        assert _normalize_for_mext("鶏もも肉") == ("にわとり もも 皮つき", True)
        assert _normalize_for_mext("豚バラ") == ("ぶた ばら 脂身つき", True)

    def test_strips_decorations(self):
        assert _normalize_for_mext("★鶏もも肉") == ("にわとり もも 皮つき", True)
        assert _normalize_for_mext("●玉ねぎ（みじん切り）") == ("たまねぎ りん茎", True)

    def test_unknown_passthrough(self):
        name, hit = _normalize_for_mext("パクチー")
        assert name == "パクチー"
        assert hit is False

    def test_synonym_map_has_expected_keys(self):
        assert MEXT_SYNONYM_MAP["かまぼこ"] == "蒸しかまぼこ"
        assert MEXT_SYNONYM_MAP["竹輪"] == "焼きちくわ"


class TestConfidenceThresholds:
    def test_auto_match_threshold(self):
        assert CONFIDENCE_AUTO_MATCH == 0.6

    def test_manual_review_threshold(self):
        assert CONFIDENCE_MANUAL_REVIEW == 0.3

    def test_auto_match_higher_than_manual(self):
        assert CONFIDENCE_AUTO_MATCH > CONFIDENCE_MANUAL_REVIEW


class TestMatchIngredientBoost:
    """match_ingredient の confidence boost テスト。
    キャッシュは常にミスとしてモックする。
    """

    @pytest.fixture(autouse=True)
    def mock_cache_miss(self):
        """全テストでキャッシュミスを返す（set_cached も no-op）"""
        with patch("app.services.ingredient_matcher.ingredient_cache_repo") as mock_cache:
            mock_cache.get_cached = AsyncMock(return_value=None)
            mock_cache.set_cached = AsyncMock()
            yield mock_cache

    @pytest.mark.asyncio
    async def test_synonym_rpc_boost_reaches_auto_threshold(self):
        """RPC 経路: synonym_hit=True + similarity 0.55 → +0.10 boost → 0.65 (auto-match)"""
        supabase = MagicMock()
        rpc_builder = MagicMock()
        rpc_builder.execute = AsyncMock(return_value=type("R", (), {"data": [{"id": "x", "similarity": 0.55}]})())
        supabase.rpc.return_value = rpc_builder

        _, confidence = await match_ingredient(supabase, "たまご")
        assert confidence >= CONFIDENCE_AUTO_MATCH

    @pytest.mark.asyncio
    async def test_no_synonym_no_boost(self):
        """synonym_hit=False のとき confidence はブーストされない"""
        supabase = MagicMock()
        rpc_builder = MagicMock()
        rpc_builder.execute = AsyncMock(return_value=type("R", (), {"data": [{"id": "x", "similarity": 0.55}]})())
        supabase.rpc.return_value = rpc_builder

        _, confidence = await match_ingredient(supabase, "パクチー")
        assert confidence == pytest.approx(0.55)

    @pytest.mark.asyncio
    async def test_fallback_synonym_boost_ilike_match(self):
        """fallback 経路: synonym_hit=True + ILIKE 一致(0.6) → +0.05 → 0.65 (auto-match に入る)"""
        supabase = MagicMock()
        # RPC が失敗して fallback に入るよう APIError を発生させる
        from postgrest.exceptions import APIError

        supabase.rpc.return_value.execute = AsyncMock(
            side_effect=APIError({"message": "similarity_search_mext_foods does not exist", "code": "42883"})
        )

        mock_food = MagicMock()
        mock_food.id = "y"
        # normalized_name が best.name に含まれる → confidence 0.6
        mock_food.name = "鶏卵 全卵 生"

        with patch("app.services.ingredient_matcher.mext_food_repo.search_by_name", return_value=[mock_food]):
            _, confidence = await match_ingredient(supabase, "たまご")
        # "鶏卵" in "鶏卵 全卵 生" → 0.6, synonym_hit=True → min(0.65, 0.65) = 0.65
        assert confidence >= CONFIDENCE_AUTO_MATCH

    @pytest.mark.asyncio
    async def test_fallback_synonym_boost_no_ilike_stays_below_auto(self):
        """fallback 経路: synonym_hit=True + ILIKE 非一致(0.4) → +0.05 → 0.45 (auto-match に入らない)"""
        supabase = MagicMock()
        from postgrest.exceptions import APIError

        supabase.rpc.return_value.execute = AsyncMock(
            side_effect=APIError({"message": "similarity_search_mext_foods does not exist", "code": "42883"})
        )

        mock_food = MagicMock()
        mock_food.id = "z"
        # normalized_name "鶏卵" が best.name "豚肉 ばら" に含まれない → confidence 0.4
        mock_food.name = "豚肉 ばら 脂身つき"

        with patch("app.services.ingredient_matcher.mext_food_repo.search_by_name", return_value=[mock_food]):
            _, confidence = await match_ingredient(supabase, "たまご")
        assert confidence < CONFIDENCE_AUTO_MATCH


class TestNegligibleIngredients:
    def test_negligible_set_contains_expected(self):
        assert "水" in NEGLIGIBLE_INGREDIENTS
        assert "塩コショウ" in NEGLIGIBLE_INGREDIENTS
        assert "塩こしょう" in NEGLIGIBLE_INGREDIENTS

    def test_regular_ingredient_not_negligible(self):
        assert "鶏もも肉" not in NEGLIGIBLE_INGREDIENTS
        assert "玉ねぎ" not in NEGLIGIBLE_INGREDIENTS


class TestEstimateAmountG:
    def test_seasoning_defaults_to_10g(self):
        assert estimate_amount_g("塩") == 10.0
        assert estimate_amount_g("しょうゆ") == 10.0

    def test_oil_defaults_to_12g(self):
        assert estimate_amount_g("ごま油") == 12.0
        assert estimate_amount_g("オリーブオイル") == 12.0

    def test_other_defaults_to_100g(self):
        assert estimate_amount_g("鶏もも肉") == 100.0


class TestMatchIngredientCache:
    @pytest.mark.asyncio
    async def test_match_ingredient_uses_cache(self):
        """キャッシュヒット時は RPC を呼ばずにキャッシュ値を返す"""
        from uuid import UUID

        food_id = UUID("12345678-1234-1234-1234-123456789012")
        supabase = MagicMock()

        with patch("app.services.ingredient_matcher.ingredient_cache_repo") as mock_cache:
            mock_cache.get_cached = AsyncMock(return_value=(food_id, 0.75))
            result_id, confidence = await match_ingredient(supabase, "玉ねぎ")

        assert result_id == food_id
        assert confidence == 0.75
        # RPC は呼ばれていない
        supabase.rpc.assert_not_called()

    @pytest.mark.asyncio
    async def test_match_ingredient_no_gemini(self):
        """match_ingredient 内では Gemini は呼ばれない"""
        supabase = MagicMock()
        rpc_builder = MagicMock()
        rpc_builder.execute = AsyncMock(return_value=type("R", (), {"data": [{"id": "x", "similarity": 0.55}]})())
        supabase.rpc.return_value = rpc_builder

        with (
            patch("app.services.ingredient_matcher.ingredient_cache_repo") as mock_cache,
            patch("app.services.ingredient_matcher.gemini_mext_matcher", None, create=True) as _,
        ):
            mock_cache.get_cached = AsyncMock(return_value=None)
            mock_cache.set_cached = AsyncMock()
            # match_ingredient を呼び出しても Gemini は呼ばれない
            result_id, confidence = await match_ingredient(supabase, "パクチー")

        # RPC は呼ばれた（trigram）
        supabase.rpc.assert_called_once()
        assert confidence == pytest.approx(0.55)

    @pytest.mark.asyncio
    async def test_match_ingredient_caches_auto_match(self):
        """confidence >= CONFIDENCE_AUTO_MATCH のとき trigram 結果をキャッシュする"""
        supabase = MagicMock()
        rpc_builder = MagicMock()
        rpc_builder.execute = AsyncMock(return_value=type("R", (), {"data": [{"id": "food-id", "similarity": 0.8}]})())
        supabase.rpc.return_value = rpc_builder

        with patch("app.services.ingredient_matcher.ingredient_cache_repo") as mock_cache:
            mock_cache.get_cached = AsyncMock(return_value=None)
            mock_cache.set_cached = AsyncMock()
            await match_ingredient(supabase, "玉ねぎ")
            # キャッシュ書き込みが呼ばれた
            mock_cache.set_cached.assert_awaited_once()
            call_args = mock_cache.set_cached.call_args
            assert call_args.kwargs.get("source") == "trigram" or call_args.args[4] == "trigram"

    @pytest.mark.asyncio
    async def test_match_ingredient_low_confidence_not_cached(self):
        """confidence < CONFIDENCE_AUTO_MATCH のとき trigram 結果をキャッシュしない"""
        supabase = MagicMock()
        rpc_builder = MagicMock()
        rpc_builder.execute = AsyncMock(return_value=type("R", (), {"data": [{"id": "food-id", "similarity": 0.45}]})())
        supabase.rpc.return_value = rpc_builder

        with patch("app.services.ingredient_matcher.ingredient_cache_repo") as mock_cache:
            mock_cache.get_cached = AsyncMock(return_value=None)
            mock_cache.set_cached = AsyncMock()
            await match_ingredient(supabase, "謎の食材")
            # キャッシュ書き込みは呼ばれない
            mock_cache.set_cached.assert_not_awaited()


class TestMatchRecipeIngredientsGemini:
    @pytest.mark.asyncio
    async def test_match_recipe_ingredients_no_api_key(self):
        """API key なし → Gemini スキップ。trigram 結果がそのまま保存される。"""
        from uuid import UUID

        supabase = MagicMock()
        # RPC: confidence 0.4 (低信頼)
        rpc_builder = MagicMock()
        rpc_builder.execute = AsyncMock(return_value=type("R", (), {"data": [{"id": "food-id", "similarity": 0.4}]})())
        supabase.rpc.return_value = rpc_builder
        delete_chain = MagicMock()
        delete_chain.execute = AsyncMock(return_value=type("R", (), {"data": []})())
        insert_chain = MagicMock()
        insert_chain.execute = AsyncMock(return_value=type("R", (), {"data": []})())
        table_builder = MagicMock()
        table_builder.delete.return_value.eq.return_value = delete_chain
        table_builder.insert.return_value = insert_chain
        supabase.table.return_value = table_builder

        recipe_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        ingredients = [{"ingredient_name": "パクチー", "amount_text": "20g"}]

        with (
            patch("app.services.ingredient_matcher.ingredient_cache_repo") as mock_cache,
            patch("app.services.ingredient_matcher.settings") as mock_settings,
        ):
            mock_cache.get_cached = AsyncMock(return_value=None)
            mock_cache.set_cached = AsyncMock()
            mock_cache.set_cached_batch = AsyncMock()
            mock_settings.google_api_key = ""  # API key なし

            results = await match_recipe_ingredients(supabase, recipe_id, ingredients)

        assert len(results) == 1
        # Gemini は呼ばれていないので、低信頼の trigram 結果がそのまま
        assert results[0]["match_confidence"] == pytest.approx(0.4)
        # バッチキャッシュ書き込みは呼ばれていない
        mock_cache.set_cached_batch.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_match_recipe_ingredients_batch_gemini(self):
        """低信頼食材だけ Gemini バッチで再評価 → 結果が更新される"""
        from uuid import UUID

        supabase = MagicMock()
        # RPC: confidence 0.4 (低信頼) → Gemini 対象
        rpc_builder = MagicMock()
        rpc_builder.execute = AsyncMock(return_value=type("R", (), {"data": [{"id": "food-id", "similarity": 0.4}]})())
        supabase.rpc.return_value = rpc_builder
        delete_chain = MagicMock()
        delete_chain.execute = AsyncMock(return_value=type("R", (), {"data": []})())
        insert_chain = MagicMock()
        insert_chain.execute = AsyncMock(return_value=type("R", (), {"data": []})())
        table_builder = MagicMock()
        table_builder.delete.return_value.eq.return_value = delete_chain
        table_builder.insert.return_value = insert_chain
        supabase.table.return_value = table_builder

        recipe_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        ingredients = [{"ingredient_name": "チキン", "amount_text": "200g"}]

        from app.services.gemini_mext_matcher import GEMINI_MATCH_CONFIDENCE, GeminiMatchResult

        mock_gemini_result = [
            GeminiMatchResult(
                ingredient_name="チキン",
                mext_food_id="gemini-matched-uuid",
                mext_food_name="にわとり もも 皮つき",
                confidence=GEMINI_MATCH_CONFIDENCE,
            )
        ]

        with (
            patch("app.services.ingredient_matcher.ingredient_cache_repo") as mock_cache,
            patch("app.services.ingredient_matcher.settings") as mock_settings,
            patch(
                "app.services.ingredient_matcher.gemini_match_batch",
                new=AsyncMock(return_value=mock_gemini_result),
            ),
            patch(
                "app.services.ingredient_matcher._get_wider_candidates",
                new=AsyncMock(return_value=[{"id": "gemini-matched-uuid", "name": "にわとり もも 皮つき"}]),
            ),
        ):
            mock_cache.get_cached = AsyncMock(return_value=None)
            mock_cache.set_cached = AsyncMock()
            mock_cache.set_cached_batch = AsyncMock()
            mock_settings.google_api_key = "test-key"

            results = await match_recipe_ingredients(supabase, recipe_id, ingredients)

        assert len(results) == 1
        # Gemini で上書きされている
        assert results[0]["mext_food_id"] == "gemini-matched-uuid"
        assert results[0]["match_confidence"] == GEMINI_MATCH_CONFIDENCE
        assert results[0]["manual_review_needed"] is False

    @pytest.mark.asyncio
    async def test_match_recipe_ingredients_replaces_existing_rows(self):
        """保存前に既存 recipe_ingredients を削除して二重登録を防ぐ。"""
        from uuid import UUID

        supabase = MagicMock()
        rpc_builder = MagicMock()
        rpc_builder.execute = AsyncMock(return_value=type("R", (), {"data": [{"id": "food-id", "similarity": 0.8}]})())
        supabase.rpc.return_value = rpc_builder

        delete_execute = AsyncMock(return_value=type("R", (), {"data": []})())
        insert_execute = AsyncMock(return_value=type("R", (), {"data": []})())
        table_builder = MagicMock()
        table_builder.delete.return_value.eq.return_value.execute = delete_execute
        table_builder.insert.return_value.execute = insert_execute
        supabase.table.return_value = table_builder

        recipe_id = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
        ingredients = [{"ingredient_name": "鶏もも肉", "amount_text": "200g"}]

        with patch("app.services.ingredient_matcher.ingredient_cache_repo") as mock_cache:
            mock_cache.get_cached = AsyncMock(return_value=None)
            mock_cache.set_cached = AsyncMock()
            mock_cache.set_cached_batch = AsyncMock()

            results = await match_recipe_ingredients(supabase, recipe_id, ingredients)

        assert len(results) == 1
        delete_execute.assert_awaited_once()
        insert_execute.assert_awaited_once()


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
