import pytest
from app.models.nutrition import ActivityLevel, Gender, Goal, UserProfile


@pytest.fixture
def male_profile() -> UserProfile:
    """テスト用: 25歳男性、170cm 70kg、中程度活動、diet 目的。"""
    return UserProfile(
        age=25,
        gender=Gender.MALE,
        height_cm=170.0,
        weight_kg=70.0,
        activity_level=ActivityLevel.MODERATE,
        goal=Goal.DIET,
    )


@pytest.fixture
def female_profile() -> UserProfile:
    """テスト用: 30歳女性、160cm 55kg、やや低い活動、bouldering 目的。"""
    return UserProfile(
        age=30,
        gender=Gender.FEMALE,
        height_cm=160.0,
        weight_kg=55.0,
        activity_level=ActivityLevel.MODERATE_LOW,
        goal=Goal.BOULDERING,
    )
