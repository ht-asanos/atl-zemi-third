"""レシピ多様性フィルタのテスト"""

from app.services.recipe_diversity import DiversityFilter, classify_recipe, classify_recipe_multi


class TestClassifyRecipe:
    """カテゴリ分類の優先順位テスト"""

    def test_nabe_yaki_udon_is_nabe(self):
        """鍋焼きうどん → 鍋が先にマッチ"""
        assert classify_recipe("鍋焼きうどん") == "鍋"

    def test_curry_udon_is_curry(self):
        """カレーうどん → カレーが先にマッチ"""
        assert classify_recipe("カレーうどん") == "カレー"

    def test_plain_udon(self):
        assert classify_recipe("肉うどん") == "うどん"

    def test_curry(self):
        assert classify_recipe("チキンカレー") == "カレー"

    def test_nabe(self):
        assert classify_recipe("キムチ鍋") == "鍋"

    def test_don(self):
        assert classify_recipe("親子丼") == "丼"

    def test_pasta(self):
        assert classify_recipe("ミートソースパスタ") == "パスタ"

    def test_ramen(self):
        assert classify_recipe("味噌ラーメン") == "ラーメン"

    def test_agemono(self):
        assert classify_recipe("鶏の唐揚げ") == "揚げ物"

    def test_itamemono(self):
        assert classify_recipe("野菜炒め") == "炒め物"

    def test_nimono(self):
        assert classify_recipe("肉じゃが") == "煮物"

    def test_soup(self):
        assert classify_recipe("豚汁") == "スープ"

    def test_salad(self):
        assert classify_recipe("大根サラダ") == "サラダ"

    def test_unknown_returns_none(self):
        assert classify_recipe("鮭のムニエル") is None

    def test_gratin(self):
        assert classify_recipe("マカロニグラタン") == "グラタン"

    def test_hamburg(self):
        assert classify_recipe("和風ハンバーグ") == "ハンバーグ"

    def test_gyoza(self):
        assert classify_recipe("羽根つき餃子") == "餃子"

    def test_oden_is_nabe(self):
        assert classify_recipe("おでん") == "鍋"

    def test_fullwidth_symbols_ignored(self):
        """記号が除去されてもマッチすること"""
        assert classify_recipe("★絶品！チキンカレー★") == "カレー"

    def test_chahan(self):
        assert classify_recipe("パラパラチャーハン") == "炒飯"

    def test_soba(self):
        assert classify_recipe("ざるそば") == "そば"

    def test_sukiyaki_is_nabe(self):
        assert classify_recipe("すき焼き") == "鍋"

    def test_tonkatsu_is_agemono(self):
        assert classify_recipe("とんかつ") == "揚げ物"

    def test_mapo_is_itamemono(self):
        assert classify_recipe("麻婆豆腐") == "炒め物"


class TestClassifyRecipeMulti:
    """マルチラベル分類テスト"""

    def test_curry_udon_matches_both(self):
        assert classify_recipe_multi("カレーうどん") == {"カレー", "うどん"}

    def test_katsudon_matches_both(self):
        assert classify_recipe_multi("カツ丼") == {"丼", "揚げ物"}

    def test_single_category(self):
        assert classify_recipe_multi("チキンカレー") == {"カレー"}

    def test_unknown_returns_empty(self):
        assert classify_recipe_multi("鮭のムニエル") == set()

    def test_curry_pan_only_curry(self):
        """誤検知テスト: カレーパンはカレーのみ（パンカテゴリは存在しない）"""
        assert classify_recipe_multi("カレーパン") == {"カレー"}

    def test_nabe_soup(self):
        """誤検知テスト: 鍋風スープは鍋とスープの両方"""
        assert classify_recipe_multi("鍋風スープ") == {"鍋", "スープ"}

    def test_nabe_yaki_udon(self):
        assert classify_recipe_multi("鍋焼きうどん") == {"鍋", "うどん"}


class TestDiversityFilter:
    def test_first_item_always_passes(self):
        df = DiversityFilter(max_same=1)
        assert df.can_add("チキンカレー") is True

    def test_same_category_blocked(self):
        df = DiversityFilter(max_same=1)
        df.mark_added("チキンカレー")
        assert df.can_add("ポークカレー") is False

    def test_different_category_passes(self):
        df = DiversityFilter(max_same=1)
        df.mark_added("チキンカレー")
        assert df.can_add("肉うどん") is True

    def test_unknown_category_always_passes(self):
        df = DiversityFilter(max_same=1)
        df.mark_added("鮭のムニエル")
        assert df.can_add("鯖の味噌焼き") is True

    def test_max_same_2(self):
        df = DiversityFilter(max_same=2)
        df.mark_added("チキンカレー")
        assert df.can_add("ポークカレー") is True
        df.mark_added("ポークカレー")
        assert df.can_add("シーフードカレー") is False

    def test_relax_increases_limit(self):
        df = DiversityFilter(max_same=1)
        df.mark_added("チキンカレー")
        assert df.can_add("ポークカレー") is False

        relaxed = df.relax()
        assert relaxed.max_same == 2
        assert relaxed.can_add("ポークカレー") is True

    def test_relax_preserves_counts(self):
        df = DiversityFilter(max_same=1)
        df.mark_added("チキンカレー")
        df.mark_added("肉うどん")

        relaxed = df.relax()
        relaxed.mark_added("ポークカレー")
        # カレー: 2件、max_same=2 → 3件目はブロック
        assert relaxed.can_add("シーフードカレー") is False

    def test_staged_relaxation_fills_count(self):
        """段階緩和で必要件数に到達するシナリオ"""
        titles = [
            "チキンカレー",
            "ポークカレー",
            "キムチ鍋",
            "豆乳鍋",
            "肉うどん",
            "ざるそば",
            "鮭のムニエル",
        ]

        # max_same=1 で選択
        df = DiversityFilter(max_same=1)
        selected = []
        for t in titles:
            if df.can_add(t):
                selected.append(t)
                df.mark_added(t)

        # カレー1, 鍋1, うどん1, そば1, 不明1 = 5件
        assert len(selected) == 5

        # 段階緩和で残りを追加
        df = df.relax()
        for t in titles:
            if t not in selected and df.can_add(t):
                selected.append(t)
                df.mark_added(t)

        # ポークカレー, 豆乳鍋 が追加 = 7件
        assert len(selected) == 7

    def test_multi_label_blocks_both_categories(self):
        """カレーうどん追加後、肉うどんもチキンカレーもブロック"""
        df = DiversityFilter(max_same=1)
        df.mark_added("カレーうどん")
        assert df.can_add("肉うどん") is False
        assert df.can_add("チキンカレー") is False

    def test_multi_label_other_category_passes(self):
        """カレーうどん追加後、関係ないカテゴリは通過"""
        df = DiversityFilter(max_same=1)
        df.mark_added("カレーうどん")
        assert df.can_add("親子丼") is True

    def test_multi_label_unknown_still_passes(self):
        """分類不能レシピは引き続き通過"""
        df = DiversityFilter(max_same=1)
        df.mark_added("カレーうどん")
        assert df.can_add("鮭のムニエル") is True

    def test_multi_label_relax_allows_second(self):
        """relax 後に max_same=2 で同カテゴリ通過"""
        df = DiversityFilter(max_same=1)
        df.mark_added("カレーうどん")
        relaxed = df.relax()
        assert relaxed.can_add("肉うどん") is True
        assert relaxed.can_add("チキンカレー") is True
