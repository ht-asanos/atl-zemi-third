import pytest
from app.models.training import MuscleGroup
from app.services.training_template import get_template


class TestDietTemplate:
    def test_exists(self) -> None:
        t = get_template("diet")
        assert t.goal == "diet"
        assert len(t.days) >= 1

    def test_has_large_muscle_groups(self) -> None:
        t = get_template("diet")
        groups = {e.muscle_group for d in t.days for e in d.exercises}
        assert MuscleGroup.LEGS in groups
        assert MuscleGroup.CHEST in groups
        assert MuscleGroup.BACK in groups


class TestStrengthTemplate:
    def test_exists(self) -> None:
        t = get_template("strength")
        assert t.goal == "strength"
        assert len(t.days) == 3  # Push/Pull/Legs

    def test_push_pull_legs_labels(self) -> None:
        t = get_template("strength")
        labels = [d.day_label for d in t.days]
        assert "Push" in labels
        assert "Pull" in labels
        assert "Legs" in labels


class TestBoulderingTemplate:
    def test_exists(self) -> None:
        t = get_template("bouldering")
        assert t.goal == "bouldering"
        assert len(t.days) == 2

    def test_has_forearm_and_back(self) -> None:
        t = get_template("bouldering")
        groups = {e.muscle_group for d in t.days for e in d.exercises}
        assert MuscleGroup.FOREARMS in groups
        assert MuscleGroup.BACK in groups

    def test_has_pull_up_and_dead_hang(self) -> None:
        t = get_template("bouldering")
        ids = {e.id for d in t.days for e in d.exercises}
        assert "pull_up" in ids
        assert "dead_hang" in ids


class TestAllTemplates:
    @pytest.mark.parametrize("goal", ["diet", "strength", "bouldering"])
    def test_all_exercises_have_id_and_name_ja(self, goal: str) -> None:
        t = get_template(goal)
        for day in t.days:
            for ex in day.exercises:
                assert ex.id, f"Exercise missing id in {goal}/{day.day_label}"
                assert ex.name_ja, f"Exercise missing name_ja in {goal}/{day.day_label}"

    def test_unknown_goal_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown goal"):
            get_template("unknown")
