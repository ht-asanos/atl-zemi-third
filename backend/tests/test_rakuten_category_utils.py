from app.services.rakuten_recipe import build_category_index, find_category_ids_by_keywords


def test_build_category_index_and_keyword_search():
    categories = [
        {"categoryId": "16", "categoryName": "麺・粉物料理"},
        {"categoryId": "151", "categoryName": "アレンジうどん", "parentCategoryId": "16"},
        {"categoryId": "1114", "categoryName": "焼うどん", "parentCategoryId": "151"},
        {"categoryId": "152", "categoryName": "ラーメン", "parentCategoryId": "16"},
    ]

    idx = build_category_index(categories)
    ids = find_category_ids_by_keywords(idx, ["うどん"])

    assert "16-151" in ids
    assert "16-151-1114" in ids
    assert all("152" not in x for x in ids)
