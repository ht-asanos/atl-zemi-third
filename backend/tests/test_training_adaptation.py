from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.schemas.feedback import FeedbackEventDetailResponse, FeedbackEventTagResponse
from app.schemas.log import WorkoutLogResponse
from app.services.training_adaptation import build_next_week_training_adjustment


def _workout_log(completed: bool, rpe: float | None, exercise_id: str = "dead_hang") -> WorkoutLogResponse:
    return WorkoutLogResponse(
        id=uuid4(),
        plan_id=uuid4(),
        log_date=date(2026, 3, 4),
        exercise_id=exercise_id,
        sets=3,
        reps=10,
        rpe=rpe,
        completed=completed,
        created_at=datetime.now(),
    )


def _workout_feedback_event(
    *,
    tags: list[str],
    completed: bool | None = None,
    rpe: float | None = None,
    exercise_id: str = "dead_hang",
) -> FeedbackEventDetailResponse:
    event_id = uuid4()
    return FeedbackEventDetailResponse(
        id=event_id,
        plan_id=uuid4(),
        domain="workout",
        meal_type=None,
        exercise_id=exercise_id,
        source_text="feedback",
        satisfaction=None,
        rpe=rpe,
        completed=completed,
        created_at=datetime.now(),
        tags=[
            FeedbackEventTagResponse(
                id=uuid4(),
                event_id=event_id,
                tag=tag,
                tag_source="llm",
                created_at=datetime.now(),
            )
            for tag in tags
        ],
        adaptation_events=[],
    )


class TestBuildNextWeekTrainingAdjustment:
    @pytest.mark.asyncio
    async def test_non_bouldering_returns_default(self) -> None:
        result = await build_next_week_training_adjustment(
            supabase=AsyncMock(),
            user_id=uuid4(),
            start_date=date(2026, 3, 9),
            goal_type="diet",
        )
        assert result.scale == 1.0
        assert result.protect_forearms is False

    @pytest.mark.asyncio
    async def test_high_rpe_reduces_scale_and_tag_protects_forearms(self) -> None:
        prev_plan = SimpleNamespace(
            id=uuid4(),
            workout_plan={
                "exercises": [
                    {"id": "dead_hang", "muscle_group": "forearms"},
                    {"id": "pull_up", "muscle_group": "back"},
                ]
            },
        )
        logs = [_workout_log(completed=False, rpe=9.2), _workout_log(completed=True, rpe=9.0, exercise_id="pull_up")]
        with (
            patch("app.services.training_adaptation.plan_repo") as mock_plan_repo,
            patch("app.services.training_adaptation.log_repo") as mock_log_repo,
            patch("app.services.training_adaptation.feedback_repo") as mock_feedback_repo,
            patch("app.services.training_adaptation.feedback_event_repo") as mock_feedback_event_repo,
        ):
            mock_plan_repo.get_weekly_plans = AsyncMock(return_value=[prev_plan])
            mock_log_repo.get_workout_logs_in_range = AsyncMock(return_value=logs)
            mock_feedback_repo.get_feedback_tags_by_plan = AsyncMock(return_value=[SimpleNamespace(tag="forearm_sore")])
            mock_feedback_event_repo.get_feedback_events_in_range = AsyncMock(return_value=[])

            result = await build_next_week_training_adjustment(
                supabase=AsyncMock(),
                user_id=uuid4(),
                start_date=date(2026, 3, 9),
                goal_type="bouldering",
            )

        assert result.scale == 0.9
        assert result.protect_forearms is True

    @pytest.mark.asyncio
    async def test_good_completion_increases_scale(self) -> None:
        prev_plan = SimpleNamespace(
            id=uuid4(),
            workout_plan={"exercises": [{"id": "dead_hang", "muscle_group": "forearms"}]},
        )
        logs = [_workout_log(completed=True, rpe=6.5), _workout_log(completed=True, rpe=7.0)]
        with (
            patch("app.services.training_adaptation.plan_repo") as mock_plan_repo,
            patch("app.services.training_adaptation.log_repo") as mock_log_repo,
            patch("app.services.training_adaptation.feedback_repo") as mock_feedback_repo,
            patch("app.services.training_adaptation.feedback_event_repo") as mock_feedback_event_repo,
        ):
            mock_plan_repo.get_weekly_plans = AsyncMock(return_value=[prev_plan])
            mock_log_repo.get_workout_logs_in_range = AsyncMock(return_value=logs)
            mock_feedback_repo.get_feedback_tags_by_plan = AsyncMock(return_value=[])
            mock_feedback_event_repo.get_feedback_events_in_range = AsyncMock(return_value=[])

            result = await build_next_week_training_adjustment(
                supabase=AsyncMock(),
                user_id=uuid4(),
                start_date=date(2026, 3, 9),
                goal_type="bouldering",
            )

        assert result.scale == 1.05
        assert result.protect_forearms is False

    @pytest.mark.asyncio
    async def test_negative_workout_feedback_lowers_scale_one_step(self) -> None:
        prev_plan = SimpleNamespace(
            id=uuid4(),
            workout_plan={"exercises": [{"id": "push_up", "muscle_group": "chest"}]},
        )
        logs = [_workout_log(completed=True, rpe=6.5, exercise_id="push_up")] * 2
        with (
            patch("app.services.training_adaptation.plan_repo") as mock_plan_repo,
            patch("app.services.training_adaptation.log_repo") as mock_log_repo,
            patch("app.services.training_adaptation.feedback_repo") as mock_feedback_repo,
            patch("app.services.training_adaptation.feedback_event_repo") as mock_feedback_event_repo,
        ):
            mock_plan_repo.get_weekly_plans = AsyncMock(return_value=[prev_plan])
            mock_log_repo.get_workout_logs_in_range = AsyncMock(return_value=logs)
            mock_feedback_repo.get_feedback_tags_by_plan = AsyncMock(return_value=[])
            mock_feedback_event_repo.get_feedback_events_in_range = AsyncMock(
                return_value=[
                    _workout_feedback_event(
                        tags=["too_hard"],
                        completed=False,
                        rpe=9.5,
                        exercise_id="push_up",
                    )
                ]
            )

            result = await build_next_week_training_adjustment(
                supabase=AsyncMock(),
                user_id=uuid4(),
                start_date=date(2026, 3, 9),
                goal_type="bouldering",
            )

        assert result.scale == 1.0
        assert result.protect_forearms is False

    @pytest.mark.asyncio
    async def test_feedback_can_only_lower_one_step(self) -> None:
        prev_plan = SimpleNamespace(
            id=uuid4(),
            workout_plan={"exercises": [{"id": "push_up", "muscle_group": "chest"}]},
        )
        logs = [_workout_log(completed=False, rpe=8.6, exercise_id="push_up")] * 2
        with (
            patch("app.services.training_adaptation.plan_repo") as mock_plan_repo,
            patch("app.services.training_adaptation.log_repo") as mock_log_repo,
            patch("app.services.training_adaptation.feedback_repo") as mock_feedback_repo,
            patch("app.services.training_adaptation.feedback_event_repo") as mock_feedback_event_repo,
        ):
            mock_plan_repo.get_weekly_plans = AsyncMock(return_value=[prev_plan])
            mock_log_repo.get_workout_logs_in_range = AsyncMock(return_value=logs)
            mock_feedback_repo.get_feedback_tags_by_plan = AsyncMock(return_value=[])
            mock_feedback_event_repo.get_feedback_events_in_range = AsyncMock(
                return_value=[
                    _workout_feedback_event(
                        tags=["too_hard"],
                        completed=False,
                        rpe=9.5,
                        exercise_id="push_up",
                    ),
                    _workout_feedback_event(
                        tags=["cannot_complete_reps"],
                        completed=False,
                        rpe=9.0,
                        exercise_id="push_up",
                    ),
                ]
            )

            result = await build_next_week_training_adjustment(
                supabase=AsyncMock(),
                user_id=uuid4(),
                start_date=date(2026, 3, 9),
                goal_type="bouldering",
            )

        assert result.scale == 0.9

    @pytest.mark.asyncio
    async def test_forearm_sore_feedback_event_protects_forearms(self) -> None:
        prev_plan = SimpleNamespace(
            id=uuid4(),
            workout_plan={"exercises": [{"id": "dead_hang", "muscle_group": "forearms"}]},
        )
        logs = [_workout_log(completed=True, rpe=7.0)]
        with (
            patch("app.services.training_adaptation.plan_repo") as mock_plan_repo,
            patch("app.services.training_adaptation.log_repo") as mock_log_repo,
            patch("app.services.training_adaptation.feedback_repo") as mock_feedback_repo,
            patch("app.services.training_adaptation.feedback_event_repo") as mock_feedback_event_repo,
        ):
            mock_plan_repo.get_weekly_plans = AsyncMock(return_value=[prev_plan])
            mock_log_repo.get_workout_logs_in_range = AsyncMock(return_value=logs)
            mock_feedback_repo.get_feedback_tags_by_plan = AsyncMock(return_value=[])
            mock_feedback_event_repo.get_feedback_events_in_range = AsyncMock(
                return_value=[_workout_feedback_event(tags=["forearm_sore"], exercise_id="dead_hang")]
            )

            result = await build_next_week_training_adjustment(
                supabase=AsyncMock(),
                user_id=uuid4(),
                start_date=date(2026, 3, 9),
                goal_type="bouldering",
            )

        assert result.protect_forearms is True
