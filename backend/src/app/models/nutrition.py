from enum import StrEnum

from pydantic import BaseModel, Field


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"


class ActivityLevel(StrEnum):
    LOW = "low"
    MODERATE_LOW = "moderate_low"
    MODERATE = "moderate"
    HIGH = "high"


ACTIVITY_MULTIPLIERS: dict[ActivityLevel, float] = {
    ActivityLevel.LOW: 1.2,
    ActivityLevel.MODERATE_LOW: 1.375,
    ActivityLevel.MODERATE: 1.55,
    ActivityLevel.HIGH: 1.725,
}


class Goal(StrEnum):
    DIET = "diet"
    STRENGTH = "strength"
    BOULDERING = "bouldering"


class UserProfile(BaseModel):
    age: int = Field(ge=10, le=120)
    gender: Gender
    height_cm: float = Field(gt=0)
    weight_kg: float = Field(gt=0)
    activity_level: ActivityLevel
    goal: Goal


class PFCBudget(BaseModel):
    protein_g: float
    fat_g: float
    carbs_g: float

    @property
    def total_kcal(self) -> float:
        return self.protein_g * 4 + self.fat_g * 9 + self.carbs_g * 4


class NutritionTarget(BaseModel):
    bmr: float
    tdee: float
    target_kcal: float
    pfc: PFCBudget
