from enum import StrEnum

from pydantic import BaseModel, Field


class MuscleGroup(StrEnum):
    CHEST = "chest"
    BACK = "back"
    LEGS = "legs"
    SHOULDERS = "shoulders"
    ARMS = "arms"
    FOREARMS = "forearms"
    CORE = "core"
    FULL_BODY = "full_body"


class Exercise(BaseModel):
    id: str
    name_ja: str
    muscle_group: MuscleGroup
    sets: int
    reps: int | str
    rest_seconds: int = 60
    required_equipment: list[str] = Field(default_factory=lambda: ["none"])


class TrainingDay(BaseModel):
    day_label: str
    exercises: list[Exercise]


class TrainingTemplate(BaseModel):
    goal: str
    days: list[TrainingDay]
