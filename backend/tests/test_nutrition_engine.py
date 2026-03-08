import pytest
from app.models.nutrition import ActivityLevel, Gender, Goal, UserProfile
from app.services.nutrition_engine import (
    calc_bmr,
    calc_pfc,
    calc_target_kcal,
    calc_tdee,
    calculate_nutrition_target,
)


class TestCalcBMR:
    def test_male(self) -> None:
        # 10*70 + 6.25*170 - 5*25 + 5 = 700 + 1062.5 - 125 + 5 = 1642.5
        result = calc_bmr(Gender.MALE, weight_kg=70, height_cm=170, age=25)
        assert result == pytest.approx(1642.5, abs=0.1)

    def test_female(self) -> None:
        # 10*55 + 6.25*160 - 5*30 - 161 = 550 + 1000 - 150 - 161 = 1239
        result = calc_bmr(Gender.FEMALE, weight_kg=55, height_cm=160, age=30)
        assert result == pytest.approx(1239.0, abs=0.1)


class TestCalcTDEE:
    def test_moderate(self) -> None:
        bmr = 1642.5
        result = calc_tdee(bmr, ActivityLevel.MODERATE)
        assert result == pytest.approx(1642.5 * 1.55, abs=0.1)

    def test_moderate_low(self) -> None:
        bmr = 1239.0
        result = calc_tdee(bmr, ActivityLevel.MODERATE_LOW)
        assert result == pytest.approx(1239.0 * 1.375, abs=0.1)


class TestCalcTargetKcal:
    def test_diet(self) -> None:
        tdee = 2545.875
        result = calc_target_kcal(tdee, Goal.DIET)
        assert result == pytest.approx(tdee - 400, abs=0.1)

    def test_strength(self) -> None:
        tdee = 2545.875
        result = calc_target_kcal(tdee, Goal.STRENGTH)
        assert result == pytest.approx(tdee + 250, abs=0.1)

    def test_bouldering(self) -> None:
        tdee = 1703.625
        result = calc_target_kcal(tdee, Goal.BOULDERING)
        assert result == pytest.approx(tdee + 75, abs=0.1)


class TestCalcPFC:
    def test_pfc_70kg(self) -> None:
        target_kcal = 2145.875
        pfc = calc_pfc(weight_kg=70, target_kcal=target_kcal)
        assert pfc.protein_g == pytest.approx(140.0, abs=0.1)
        assert pfc.fat_g == pytest.approx(56.0, abs=0.1)
        # carbs = (2145.875 - 140*4 - 56*9) / 4 = (2145.875 - 560 - 504) / 4 = 270.47
        assert pfc.carbs_g == pytest.approx(270.5, abs=0.1)


class TestCalculateNutritionTarget:
    def test_male_diet(self, male_profile: UserProfile) -> None:
        target = calculate_nutrition_target(male_profile)
        assert target.bmr == pytest.approx(1642.5, abs=0.1)
        assert target.tdee == pytest.approx(2545.9, abs=0.1)
        assert target.target_kcal == pytest.approx(2145.9, abs=0.1)
        assert target.pfc.protein_g == pytest.approx(140.0, abs=0.1)
        assert target.pfc.fat_g == pytest.approx(56.0, abs=0.1)

    def test_female_bouldering(self, female_profile: UserProfile) -> None:
        target = calculate_nutrition_target(female_profile)
        # BMR: 10*55 + 6.25*160 - 5*30 - 161 = 1239
        assert target.bmr == pytest.approx(1239.0, abs=0.1)
        # TDEE: 1239 * 1.375 = 1703.625
        assert target.tdee == pytest.approx(1703.6, abs=0.1)
        # target: 1703.625 + 75 = 1778.625
        assert target.target_kcal == pytest.approx(1778.6, abs=0.1)
