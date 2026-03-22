"""MEXT Excel パーサーのテスト"""

from pathlib import Path

import pytest
from app.services.mext_excel_loader import (
    CATEGORY_NAMES,
    _parse_float,
    load_foods_from_excel,
)

EXCEL_DIR = Path(__file__).resolve().parent.parent.parent / "doc" / "mext"
MAIN_EXCEL = EXCEL_DIR / "20230428-mxt_kagsei-mext_00001_012.xlsx"


class TestParseFloat:
    def test_normal_int(self):
        val, flag = _parse_float(343)
        assert val == 343.0
        assert flag == "value"

    def test_normal_float(self):
        val, flag = _parse_float(12.7)
        assert val == 12.7
        assert flag == "value"

    def test_string_float(self):
        val, flag = _parse_float("9.4")
        assert val == 9.4
        assert flag == "value"

    def test_parenthesized(self):
        val, flag = _parse_float("(11.3)")
        assert val == 11.3
        assert flag == "value"

    def test_trace(self):
        val, flag = _parse_float("Tr")
        assert val == 0.0
        assert flag == "trace"

    def test_trace_lower(self):
        val, flag = _parse_float("tr")
        assert val == 0.0
        assert flag == "trace"

    def test_dash(self):
        val, flag = _parse_float("-")
        assert val == 0.0
        assert flag == "missing"

    def test_asterisk(self):
        val, flag = _parse_float("*")
        assert val == 0.0
        assert flag == "missing"

    def test_none(self):
        val, flag = _parse_float(None)
        assert val == 0.0
        assert flag == "missing"

    def test_empty_string(self):
        val, flag = _parse_float("")
        assert val == 0.0
        assert flag == "missing"

    def test_zero(self):
        val, flag = _parse_float(0)
        assert val == 0.0
        assert flag == "value"

    def test_fullwidth_parentheses(self):
        val, flag = _parse_float("（5.1）")
        assert val == 5.1
        assert flag == "value"


@pytest.mark.skipif(not MAIN_EXCEL.exists(), reason="MEXT Excel file not found")
class TestLoadFoodsFromExcel:
    @pytest.fixture(scope="class")
    def loaded(self):
        return load_foods_from_excel(MAIN_EXCEL)

    def test_food_count(self, loaded):
        foods, stats = loaded
        assert len(foods) > 2000
        assert stats["total_rows"] == len(foods)
        assert stats["skipped"] >= 0

    def test_first_food_identity(self, loaded):
        foods, _ = loaded
        first = foods[0]
        assert first.mext_food_id == "01001"
        assert "アマランサス" in first.name

    def test_nutrition_values(self, loaded):
        foods, _ = loaded
        first = foods[0]
        assert first.kcal_per_100g == 343.0
        assert first.protein_g_per_100g == 12.7
        assert first.fat_g_per_100g == 6.0
        assert first.category_code == "01"
        assert first.category_name == CATEGORY_NAMES["01"]

    def test_raw_data_fields(self, loaded):
        foods, _ = loaded
        first = foods[0]
        assert first.raw_data["source"] == "excel"
        assert "trace_fields" in first.raw_data
        assert "missing_fields" in first.raw_data

    def test_trace_detection(self, loaded):
        """Tr 値が trace_fields に記録されることを確認"""
        foods, _ = loaded
        has_trace = [f for f in foods if f.raw_data.get("trace_fields")]
        assert len(has_trace) > 0

    def test_zero_kcal_count(self, loaded):
        _, stats = loaded
        # 一部の食品（水、茶葉など）は 0 kcal
        assert isinstance(stats["zero_kcal"], int)

    def test_stats_file_name(self, loaded):
        _, stats = loaded
        assert stats["file"] == MAIN_EXCEL.name

    def test_fiber_sodium_calcium_iron(self, loaded):
        """微量栄養素が正しくパースされること"""
        foods, _ = loaded
        first = foods[0]
        # アマランサス: fiber=7.4, sodium=1, calcium=160, iron=9.4
        assert first.fiber_g_per_100g == 7.4
        assert first.sodium_mg_per_100g == 1.0
        assert first.calcium_mg_per_100g == 160.0
        assert first.iron_mg_per_100g == 9.4
