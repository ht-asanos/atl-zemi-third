"""適応エンジンのユニットテスト (最重要、12 ケース)"""

import copy

from app.models.food import FoodCategory, FoodItem
from app.services.adaptation_engine import adapt_plan

STAPLES = [
    FoodItem(
        name="冷凍うどん",
        category=FoodCategory.STAPLE,
        kcal_per_serving=210,
        protein_g=5.2,
        fat_g=0.8,
        carbs_g=44.0,
        serving_unit="1玉",
    ),
    FoodItem(
        name="白米",
        category=FoodCategory.STAPLE,
        kcal_per_serving=252,
        protein_g=3.8,
        fat_g=0.5,
        carbs_g=55.7,
        serving_unit="1膳",
    ),
    FoodItem(
        name="オートミール",
        category=FoodCategory.STAPLE,
        kcal_per_serving=190,
        protein_g=6.8,
        fat_g=3.4,
        carbs_g=32.2,
        serving_unit="50g",
    ),
]


def _ex(id, name_ja, muscle_group, sets, reps, rest_seconds=60):
    return {
        "id": id,
        "name_ja": name_ja,
        "muscle_group": muscle_group,
        "sets": sets,
        "reps": reps,
        "rest_seconds": rest_seconds,
    }


def _make_plan(exercises=None, meals=None):
    if exercises is None:
        exercises = [
            _ex("push_up", "プッシュアップ", "chest", 3, 12),
            _ex("pull_up", "チンニング", "back", 4, 8, 90),
        ]
    if meals is None:
        meals = [
            {
                "staple": {
                    "name": "冷凍うどん",
                    "category": "staple",
                    "kcal_per_serving": 210,
                    "protein_g": 5.2,
                    "fat_g": 0.8,
                    "carbs_g": 44.0,
                    "serving_unit": "1玉",
                    "price_yen": 40,
                    "cooking_minutes": 3,
                },
                "protein_sources": [
                    {
                        "name": "卵",
                        "category": "protein",
                        "kcal_per_serving": 91,
                        "protein_g": 7.4,
                        "fat_g": 6.2,
                        "carbs_g": 0.2,
                        "serving_unit": "1個",
                        "price_yen": 25,
                        "cooking_minutes": 3,
                    },
                ],
                "bulk_items": [
                    {
                        "name": "きのこミックス",
                        "category": "bulk",
                        "kcal_per_serving": 18,
                        "protein_g": 2.7,
                        "fat_g": 0.2,
                        "carbs_g": 3.1,
                        "serving_unit": "100g",
                        "price_yen": 80,
                        "cooking_minutes": 2,
                    },
                ],
            }
        ]
    return {
        "meal_plan": meals,
        "workout_plan": {"day_label": "全身A", "exercises": exercises},
    }


class TestTooHard:
    def test_reduces_sets_and_reps(self) -> None:
        plan = _make_plan()
        new_plan, changes = adapt_plan(plan, ["too_hard"], STAPLES, "冷凍うどん")
        ex = new_plan["workout_plan"]["exercises"]
        assert ex[0]["sets"] == 2
        assert ex[0]["reps"] == 9
        assert ex[1]["sets"] == 3
        assert ex[1]["reps"] == 6
        assert len(changes) == 2

    def test_string_reps_preserved(self) -> None:
        """plank の "30秒" はスキップされる"""
        exercises = [_ex("plank", "プランク", "core", 3, "30秒")]
        plan = _make_plan(exercises=exercises)
        new_plan, changes = adapt_plan(plan, ["too_hard"], STAPLES, "冷凍うどん")
        ex = new_plan["workout_plan"]["exercises"][0]
        assert ex["reps"] == "30秒"
        assert ex["sets"] == 3
        assert len(changes) == 0


class TestCannotCompleteReps:
    def test_reduces_reps(self) -> None:
        plan = _make_plan()
        new_plan, changes = adapt_plan(
            plan,
            ["cannot_complete_reps"],
            STAPLES,
            "冷凍うどん",
        )
        ex = new_plan["workout_plan"]["exercises"]
        assert ex[0]["reps"] == 10  # 12 - 2
        assert ex[1]["reps"] == 6  # 8 - 2

    def test_substitutes_when_min(self) -> None:
        exercises = [_ex("pull_up", "チンニング", "back", 4, 1, 90)]
        plan = _make_plan(exercises=exercises)
        new_plan, changes = adapt_plan(
            plan,
            ["cannot_complete_reps"],
            STAPLES,
            "冷凍うどん",
        )
        ex = new_plan["workout_plan"]["exercises"][0]
        assert ex["id"] == "bodyweight_row"
        assert any("代替" in c for c in changes)


class TestForearmSore:
    def test_excludes_forearm_exercises(self) -> None:
        exercises = [
            _ex("pull_up", "チンニング", "back", 4, 8, 90),
            _ex("dead_hang", "デッドハング", "forearms", 3, "30秒", 90),
            _ex("finger_curl", "フィンガーカール", "forearms", 3, 15),
        ]
        plan = _make_plan(exercises=exercises)
        new_plan, changes = adapt_plan(plan, ["forearm_sore"], STAPLES, "冷凍うどん")
        ex = new_plan["workout_plan"]["exercises"]
        assert len(ex) == 1
        assert ex[0]["id"] == "pull_up"

    def test_empty_exercises_adds_fallback(self) -> None:
        """全種目がforearmの場合、plankで補完"""
        exercises = [
            _ex("dead_hang", "デッドハング", "forearms", 3, "30秒", 90),
            _ex("finger_curl", "フィンガーカール", "forearms", 3, 15),
        ]
        plan = _make_plan(exercises=exercises)
        new_plan, changes = adapt_plan(plan, ["forearm_sore"], STAPLES, "冷凍うどん")
        ex = new_plan["workout_plan"]["exercises"]
        assert len(ex) == 1
        assert ex[0]["id"] == "plank"
        assert any("補完" in c for c in changes)


class TestBoredStaple:
    def test_replaces_staple(self) -> None:
        plan = _make_plan()
        new_plan, changes = adapt_plan(plan, ["bored_staple"], STAPLES, "冷凍うどん")
        new_staple = new_plan["meal_plan"][0]["staple"]["name"]
        assert new_staple != "冷凍うどん"

    def test_excludes_current(self) -> None:
        """現在の主食は候補から除外される"""
        plan = _make_plan()
        new_plan, changes = adapt_plan(plan, ["bored_staple"], STAPLES, "冷凍うどん")
        new_staple = new_plan["meal_plan"][0]["staple"]["name"]
        assert new_staple != "冷凍うどん"
        assert new_staple in ["白米", "オートミール"]


class TestTooMuchFood:
    def test_removes_bulk_one_serving(self) -> None:
        plan = _make_plan()
        new_plan, changes = adapt_plan(plan, ["too_much_food"], STAPLES, "冷凍うどん")
        assert len(new_plan["meal_plan"][0]["bulk_items"]) == 0
        assert any("かさ増し" in c for c in changes)

    def test_removes_protein_when_no_bulk(self) -> None:
        meals = [
            {
                "staple": {
                    "name": "冷凍うどん",
                    "category": "staple",
                    "kcal_per_serving": 210,
                    "protein_g": 5.2,
                    "fat_g": 0.8,
                    "carbs_g": 44.0,
                    "serving_unit": "1玉",
                    "price_yen": 40,
                    "cooking_minutes": 3,
                },
                "protein_sources": [
                    {
                        "name": "卵",
                        "category": "protein",
                        "kcal_per_serving": 91,
                        "protein_g": 7.4,
                        "fat_g": 6.2,
                        "carbs_g": 0.2,
                        "serving_unit": "1個",
                        "price_yen": 25,
                        "cooking_minutes": 3,
                    },
                ],
                "bulk_items": [],
            }
        ]
        plan = _make_plan(meals=meals)
        new_plan, changes = adapt_plan(plan, ["too_much_food"], STAPLES, "冷凍うどん")
        assert len(new_plan["meal_plan"][0]["protein_sources"]) == 0
        assert any("タンパク源" in c for c in changes)


class TestCombined:
    def test_multiple_tags(self) -> None:
        plan = _make_plan()
        new_plan, changes = adapt_plan(
            plan,
            ["too_hard", "too_much_food"],
            STAPLES,
            "冷凍うどん",
        )
        assert new_plan["workout_plan"]["exercises"][0]["sets"] < 3
        assert len(new_plan["meal_plan"][0]["bulk_items"]) == 0

    def test_no_tags_no_changes(self) -> None:
        plan = _make_plan()
        original = copy.deepcopy(plan)
        new_plan, changes = adapt_plan(plan, [], STAPLES, "冷凍うどん")
        assert new_plan == original
        assert changes == []
