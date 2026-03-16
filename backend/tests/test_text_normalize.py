"""text_normalize ユニットテスト。"""

from app.utils.text_normalize import contains_normalized, normalize_jp


class TestNormalizeJp:
    def test_fullwidth_to_halfwidth(self):
        assert normalize_jp("Ａ１") == "A1"

    def test_katakana_to_hiragana(self):
        assert normalize_jp("カレー") == "かれー"

    def test_symbol_removal(self):
        assert normalize_jp("鶏・もも肉") == "鶏もも肉"

    def test_colon_removal(self):
        assert normalize_jp("主食：白米") == "主食白米"

    def test_space_removal(self):
        assert normalize_jp("焼き うどん") == "焼きうどん"

    def test_combined(self):
        # 全角カタカナ + 中黒 → ひらがな + 記号除去
        assert normalize_jp("カレー・うどん") == "かれーうどん"


class TestContainsNormalized:
    def test_udon_match(self):
        assert contains_normalized("焼うどん", "うどん") is True

    def test_no_match(self):
        assert contains_normalized("カレー", "うどん") is False

    def test_short_needle_rejected(self):
        """needle < 2文字は過短一致防止で False。"""
        assert contains_normalized("ライス", "ス") is False

    def test_single_char_needle(self):
        assert contains_normalized("パスタ", "タ") is False

    def test_two_char_needle_accepted(self):
        assert contains_normalized("パスタ", "パス") is True

    def test_katakana_hiragana_cross_match(self):
        """カタカナとひらがなの混在マッチ。"""
        assert contains_normalized("カレーうどん", "うどん") is True
        assert contains_normalized("カレーうどん", "ウドン") is True

    def test_empty_needle(self):
        assert contains_normalized("テスト", "") is False
