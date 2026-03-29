from datetime import date, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.schemas.feedback import FeedbackEventDetailResponse, FeedbackEventTagResponse
from app.schemas.log import WorkoutLogResponse
from app.schemas.training_progression import (
    TrainingProgressionEdgeResponse,
    TrainingProgressionReviewItem,
    TrainingProgressionSourceResponse,
)
from app.services.training_progression_planner import recommend_progression_replacements
from app.services.training_progression_service import (
    apply_curated_progression_presets,
    ingest_training_progressions,
    list_review_items_with_presets,
)
from app.services.training_skill_tree_service import build_training_skill_tree


def _approved_edge(
    *,
    from_id: str = "pull_up",
    from_reps: int = 10,
    to_id: str = "chin_up",
    to_reps: int = 5,
    goal_scope: list[str] | None = None,
) -> TrainingProgressionEdgeResponse:
    return TrainingProgressionEdgeResponse(
        id=uuid4(),
        source_id=uuid4(),
        from_label_raw="懸垂",
        from_exercise_id=from_id,
        from_reps=from_reps,
        to_label_raw="チンアップ",
        to_exercise_id=to_id,
        to_reps=to_reps,
        relation_type="unlock_if_can_do",
        goal_scope=goal_scope or ["bouldering", "strength"],
        evidence_text="懸垂10回できるならチンアップ5回",
        confidence=0.95,
        review_status="approved",
        review_note=None,
        reviewed_by=None,
        reviewed_at=None,
        created_at=datetime.now(),
    )


class TestTrainingProgressionIngest:
    @pytest.mark.asyncio
    async def test_ingest_skips_no_transcript(self) -> None:
        supabase = AsyncMock()
        source = type("Source", (), {"id": uuid4()})()

        with (
            patch("app.services.training_progression_service.resolve_channel_id", AsyncMock(return_value="cid")),
            patch(
                "app.services.training_progression_service.fetch_channel_videos_by_query",
                AsyncMock(
                    return_value=[
                        {
                            "video_id": "abc123def45",
                            "title": "懸垂ができるなら",
                            "published_at": None,
                        }
                    ]
                ),
            ),
            patch(
                "app.services.training_progression_service.training_progression_repo.list_active_aliases",
                AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.training_progression_service.training_progression_repo.get_source_by_video_id",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.services.training_progression_service.training_progression_repo.create_progression_source",
                AsyncMock(return_value=source),
            ),
            patch(
                "app.services.training_progression_service.training_progression_repo.update_progression_source",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.services.training_progression_service.fetch_transcript",
                AsyncMock(side_effect=RuntimeError("no transcript")),
            ),
        ):
            results, stats = await ingest_training_progressions(
                supabase,
                http_client=AsyncMock(),
                api_key="yt-key",
                channel_handle="@CalisthenicsTokyo",
                title_keyword="ができるなら",
                max_results=10,
            )

        assert stats.videos_found == 1
        assert stats.videos_processed == 0
        assert results[0].status == "no_transcript"

    @pytest.mark.asyncio
    async def test_failed_existing_source_is_retried(self) -> None:
        supabase = AsyncMock()
        existing = type(
            "Source",
            (),
            {
                "id": uuid4(),
                "ingest_status": "failed",
                "video_url": "https://www.youtube.com/shorts/abc123def45",
            },
        )()

        with (
            patch("app.services.training_progression_service.resolve_channel_id", AsyncMock(return_value="cid")),
            patch(
                "app.services.training_progression_service.fetch_channel_videos_by_query",
                AsyncMock(
                    return_value=[
                        {
                            "video_id": "abc123def45",
                            "title": "懸垂ができるなら",
                            "published_at": None,
                        }
                    ]
                ),
            ),
            patch(
                "app.services.training_progression_service.training_progression_repo.list_active_aliases",
                AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.training_progression_service.training_progression_repo.get_source_by_video_id",
                AsyncMock(return_value=existing),
            ),
            patch(
                "app.services.training_progression_service.training_progression_repo.update_progression_source",
                AsyncMock(return_value=None),
            ) as mock_update,
            patch(
                "app.services.training_progression_service.fetch_transcript",
                AsyncMock(
                    return_value={
                        "text": "懸垂が10回できるならチンアップが5回できます",
                        "is_generated": False,
                        "language_code": "ja",
                        "quality": {"quality_score": 80},
                    }
                ),
            ),
            patch(
                "app.services.training_progression_service.extract_progression_edges_from_transcript",
                AsyncMock(
                    return_value=[
                        type(
                            "Edge",
                            (),
                            {
                                "from_label": "懸垂",
                                "from_reps": 10,
                                "to_label": "チンアップ",
                                "to_reps": 5,
                                "evidence_text": "懸垂が10回できるならチンアップが5回できます",
                                "confidence": 0.9,
                                "model_dump": lambda self: {
                                    "from_label": "懸垂",
                                    "from_reps": 10,
                                    "to_label": "チンアップ",
                                    "to_reps": 5,
                                    "evidence_text": "懸垂が10回できるならチンアップが5回できます",
                                    "confidence": 0.9,
                                },
                            },
                        )()
                    ]
                ),
            ),
            patch(
                "app.services.training_progression_service.training_progression_repo.create_progression_edges",
                AsyncMock(return_value=[_approved_edge()]),
            ),
        ):
            results, stats = await ingest_training_progressions(
                supabase,
                http_client=AsyncMock(),
                api_key="yt-key",
                channel_handle="@CalisthenicsTokyo",
                title_keyword="ができるなら",
                max_results=10,
            )

        assert stats.videos_processed == 1
        assert results[0].status == "review_pending"
        assert mock_update.await_count >= 2

    @pytest.mark.asyncio
    async def test_low_quality_manual_transcript_is_naturalized_and_diagnostics_are_saved(self) -> None:
        supabase = AsyncMock()
        source = type(
            "Source",
            (),
            {"id": uuid4(), "video_url": "https://www.youtube.com/shorts/abc123def45"},
        )()

        with (
            patch("app.services.training_progression_service.resolve_channel_id", AsyncMock(return_value="cid")),
            patch(
                "app.services.training_progression_service.fetch_channel_videos_by_query",
                AsyncMock(
                    return_value=[
                        {
                            "video_id": "abc123def45",
                            "title": "懸垂ができるなら",
                            "published_at": None,
                        }
                    ]
                ),
            ),
            patch(
                "app.services.training_progression_service.training_progression_repo.list_active_aliases",
                AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.training_progression_service.training_progression_repo.get_source_by_video_id",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.services.training_progression_service.training_progression_repo.create_progression_source",
                AsyncMock(return_value=source),
            ),
            patch(
                "app.services.training_progression_service.fetch_transcript",
                AsyncMock(
                    return_value={
                        "text": "懸垂が10回できるなら 次はチンアップ5回です",
                        "is_generated": False,
                        "language_code": "ja",
                        "quality": {"quality_score": 50},
                    }
                ),
            ),
            patch(
                "app.services.training_progression_service.naturalize_auto_transcript",
                AsyncMock(return_value="懸垂が10回できるなら、次はチンアップ5回です。"),
            ) as mock_naturalize,
            patch(
                "app.services.training_progression_service.extract_progression_edges_from_transcript",
                AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.training_progression_service.training_progression_repo.create_progression_edges",
                AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.training_progression_service.training_progression_repo.update_progression_source",
                AsyncMock(return_value=None),
            ) as mock_update,
        ):
            results, stats = await ingest_training_progressions(
                supabase,
                http_client=AsyncMock(),
                api_key="yt-key",
                channel_handle="@CalisthenicsTokyo",
                title_keyword="ができるなら",
                max_results=10,
            )

        assert results[0].status == "no_edges"
        assert stats.transcripts_fetched == 1
        assert stats.transcripts_naturalized == 1
        mock_naturalize.assert_awaited_once()
        update_kwargs = mock_update.await_args_list[-1].kwargs
        assert update_kwargs["raw_extraction_json"]["diagnostics"]["naturalization_reason"] == "low_quality"
        assert update_kwargs["raw_extraction_json"]["diagnostics"]["extraction_count"] == 0
        assert (
            update_kwargs["raw_extraction_json"]["diagnostics"]["empty_reason_hint"]
            == "no_progression_pattern_detected"
        )


class TestTrainingProgressionPlanner:
    @pytest.mark.asyncio
    async def test_recommend_upgrade_when_threshold_met(self) -> None:
        log = WorkoutLogResponse(
            id=uuid4(),
            plan_id=uuid4(),
            log_date=date(2026, 3, 18),
            exercise_id="pull_up",
            sets=3,
            reps=10,
            rpe=7.0,
            completed=True,
            created_at=datetime.now(),
        )
        with (
            patch(
                "app.services.training_progression_planner.log_repo.get_workout_logs_in_range",
                AsyncMock(return_value=[log]),
            ),
            patch(
                "app.services.training_progression_planner.feedback_event_repo.get_feedback_events_in_range",
                AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.training_progression_planner.training_progression_repo.list_approved_edges",
                AsyncMock(return_value=[_approved_edge()]),
            ),
        ):
            result = await recommend_progression_replacements(
                AsyncMock(),
                user_id=uuid4(),
                start_date=date(2026, 3, 22),
                goal_type="bouldering",
                available_equipment=["pull_up_bar"],
            )
        assert result["pull_up"].replacement_id == "chin_up"

    @pytest.mark.asyncio
    async def test_negative_feedback_prevents_upgrade_and_recommends_regression(self) -> None:
        event_id = uuid4()
        event = FeedbackEventDetailResponse(
            id=event_id,
            plan_id=uuid4(),
            domain="workout",
            meal_type=None,
            exercise_id="chin_up",
            source_text="too hard",
            satisfaction=None,
            rpe=9.5,
            completed=False,
            created_at=datetime.now(),
            tags=[
                FeedbackEventTagResponse(
                    id=uuid4(),
                    event_id=event_id,
                    tag="too_hard",
                    tag_source="llm",
                    created_at=datetime.now(),
                )
            ],
            adaptation_events=[],
        )
        with (
            patch(
                "app.services.training_progression_planner.log_repo.get_workout_logs_in_range",
                AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.training_progression_planner.feedback_event_repo.get_feedback_events_in_range",
                AsyncMock(return_value=[event]),
            ),
            patch(
                "app.services.training_progression_planner.training_progression_repo.list_approved_edges",
                AsyncMock(return_value=[_approved_edge()]),
            ),
        ):
            result = await recommend_progression_replacements(
                AsyncMock(),
                user_id=uuid4(),
                start_date=date(2026, 3, 22),
                goal_type="strength",
                available_equipment=["pull_up_bar"],
            )
        assert result["chin_up"].replacement_id == "pull_up"

    @pytest.mark.asyncio
    async def test_upgrade_is_skipped_when_target_equipment_is_unavailable(self) -> None:
        log = WorkoutLogResponse(
            id=uuid4(),
            plan_id=uuid4(),
            log_date=date(2026, 3, 18),
            exercise_id="pull_up",
            sets=3,
            reps=10,
            rpe=7.0,
            completed=True,
            created_at=datetime.now(),
        )
        with (
            patch(
                "app.services.training_progression_planner.log_repo.get_workout_logs_in_range",
                AsyncMock(return_value=[log]),
            ),
            patch(
                "app.services.training_progression_planner.feedback_event_repo.get_feedback_events_in_range",
                AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.training_progression_planner.training_progression_repo.list_approved_edges",
                AsyncMock(return_value=[_approved_edge(to_id="chin_up")]),
            ),
        ):
            result = await recommend_progression_replacements(
                AsyncMock(),
                user_id=uuid4(),
                start_date=date(2026, 3, 22),
                goal_type="strength",
                available_equipment=["none"],
            )
        assert result == {}

    @pytest.mark.asyncio
    async def test_strength_track_recommends_first_advanced_stage_from_template_slot(self) -> None:
        log = WorkoutLogResponse(
            id=uuid4(),
            plan_id=uuid4(),
            log_date=date(2026, 3, 18),
            exercise_id="tricep_dip",
            sets=3,
            reps=6,
            rpe=7.0,
            completed=True,
            created_at=datetime.now(),
        )
        dip_bar_edge = _approved_edge(
            from_id="dip_bar_swing",
            from_reps=5,
            to_id="swing_tuck_planche",
            to_reps=1,
            goal_scope=["strength"],
        ).model_copy(update={"from_label_raw": "ディップスバーの上でスイング", "to_label_raw": "スイングタックプラン"})
        with (
            patch(
                "app.services.training_progression_planner.log_repo.get_workout_logs_in_range",
                AsyncMock(return_value=[log]),
            ),
            patch(
                "app.services.training_progression_planner.feedback_event_repo.get_feedback_events_in_range",
                AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.training_progression_planner.training_progression_repo.list_approved_edges",
                AsyncMock(return_value=[dip_bar_edge]),
            ),
        ):
            result = await recommend_progression_replacements(
                AsyncMock(),
                user_id=uuid4(),
                start_date=date(2026, 3, 22),
                goal_type="strength",
                available_equipment=["dip_bars"],
            )
        assert result["tricep_dip"].replacement_id == "dip_bar_swing"

    @pytest.mark.asyncio
    async def test_strength_track_progresses_bridge_slot_using_logged_stage(self) -> None:
        log = WorkoutLogResponse(
            id=uuid4(),
            plan_id=uuid4(),
            log_date=date(2026, 3, 18),
            exercise_id="reverse_scapular_push_up",
            sets=3,
            reps=10,
            rpe=7.0,
            completed=True,
            created_at=datetime.now(),
        )
        bridge_edge = _approved_edge(
            from_id="reverse_scapular_push_up",
            from_reps=10,
            to_id="reverse_plank_raise",
            to_reps=1,
            goal_scope=["strength"],
        ).model_copy(
            update={"from_label_raw": "リバーススキャピュラープッシュアップ", "to_label_raw": "リバースプランクレイズ"}
        )
        with (
            patch(
                "app.services.training_progression_planner.log_repo.get_workout_logs_in_range",
                AsyncMock(return_value=[log]),
            ),
            patch(
                "app.services.training_progression_planner.feedback_event_repo.get_feedback_events_in_range",
                AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.training_progression_planner.training_progression_repo.list_approved_edges",
                AsyncMock(return_value=[bridge_edge]),
            ),
        ):
            result = await recommend_progression_replacements(
                AsyncMock(),
                user_id=uuid4(),
                start_date=date(2026, 3, 22),
                goal_type="strength",
                available_equipment=["none"],
            )
        assert result["overhead_press"].replacement_id == "reverse_plank_raise"


class TestTrainingSkillTree:
    @pytest.mark.asyncio
    async def test_build_training_skill_tree_marks_current_and_recommended_nodes(self) -> None:
        log = WorkoutLogResponse(
            id=uuid4(),
            plan_id=uuid4(),
            log_date=date(2026, 3, 18),
            exercise_id="reverse_scapular_push_up",
            sets=3,
            reps=10,
            rpe=7.0,
            completed=True,
            created_at=datetime.now(),
        )
        edge = _approved_edge(
            from_id="reverse_scapular_push_up",
            from_reps=10,
            to_id="reverse_plank_raise",
            to_reps=1,
            goal_scope=["strength"],
        ).model_copy(
            update={"from_label_raw": "リバーススキャピュラープッシュアップ", "to_label_raw": "リバースプランクレイズ"}
        )

        with (
            patch(
                "app.services.training_skill_tree_service.log_repo.get_workout_logs_in_range",
                AsyncMock(return_value=[log]),
            ),
            patch(
                "app.services.training_skill_tree_service.feedback_event_repo.get_feedback_events_in_range",
                AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.training_skill_tree_service.training_progression_repo.list_approved_edges",
                AsyncMock(return_value=[edge]),
            ),
            patch(
                "app.services.training_skill_tree_service.recommend_progression_replacements",
                AsyncMock(
                    return_value={
                        "overhead_press": type(
                            "Rec",
                            (),
                            {
                                "replacement_id": "reverse_plank_raise",
                                "reason": "reverse_scapular_push_up 10回条件を満たしたため reverse_plank_raise へ進行",
                            },
                        )()
                    }
                ),
            ),
        ):
            result = await build_training_skill_tree(
                AsyncMock(),
                user_id=uuid4(),
                goal_type="strength",
                start_date=date(2026, 3, 22),
                available_equipment=["none"],
            )

        assert result.summary.available_edge_count == 1
        assert result.summary.recommended_count == 1
        assert len(result.tracks) == 1
        node_by_id = {node.exercise_id: node for node in result.tracks[0].nodes}
        assert node_by_id["reverse_scapular_push_up"].status == "current"
        assert node_by_id["reverse_plank_raise"].status == "recommended"
        assert node_by_id["reverse_plank_raise"].recommendation_reason is not None
        assert node_by_id["reverse_scapular_push_up"].latest_log_summary is not None
        assert node_by_id["reverse_scapular_push_up"].latest_log_summary["reps"] == 10

    @pytest.mark.asyncio
    async def test_build_training_skill_tree_marks_blocked_nodes_from_negative_feedback(self) -> None:
        event_id = uuid4()
        event = FeedbackEventDetailResponse(
            id=event_id,
            plan_id=uuid4(),
            domain="workout",
            meal_type=None,
            exercise_id="chin_up",
            source_text="too hard",
            satisfaction=None,
            rpe=9.5,
            completed=False,
            created_at=datetime.now(),
            tags=[
                FeedbackEventTagResponse(
                    id=uuid4(),
                    event_id=event_id,
                    tag="too_hard",
                    tag_source="llm",
                    created_at=datetime.now(),
                )
            ],
            adaptation_events=[],
        )
        edge = _approved_edge(from_id="pull_up", to_id="chin_up", goal_scope=["bouldering"])
        with (
            patch(
                "app.services.training_skill_tree_service.log_repo.get_workout_logs_in_range",
                AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.training_skill_tree_service.feedback_event_repo.get_feedback_events_in_range",
                AsyncMock(return_value=[event]),
            ),
            patch(
                "app.services.training_skill_tree_service.training_progression_repo.list_approved_edges",
                AsyncMock(return_value=[edge]),
            ),
            patch(
                "app.services.training_skill_tree_service.recommend_progression_replacements",
                AsyncMock(return_value={}),
            ),
        ):
            result = await build_training_skill_tree(
                AsyncMock(),
                user_id=uuid4(),
                goal_type="bouldering",
                start_date=date(2026, 3, 22),
                available_equipment=["pull_up_bar"],
            )

        node_by_id = {node.exercise_id: node for node in result.tracks[0].nodes}
        assert result.summary.has_negative_feedback is True
        assert node_by_id["chin_up"].status == "blocked"
        assert node_by_id["chin_up"].latest_feedback_summary is not None
        assert "too_hard" in node_by_id["chin_up"].latest_feedback_summary["tags"]


class TestTrainingProgressionPresets:
    @pytest.mark.asyncio
    async def test_list_review_items_with_presets_adds_curated_mapping(self) -> None:
        item = TrainingProgressionReviewItem(
            edge=_approved_edge(
                from_id=None,
                to_id=None,
                from_reps=10,
                to_reps=1,
            ).model_copy(
                update={
                    "from_label_raw": "リバーススキャピュラープッシュアップ",
                    "to_label_raw": "リバースプランクレイズ",
                    "review_status": "pending",
                }
            ),
            source=TrainingProgressionSourceResponse(
                id=uuid4(),
                platform="youtube",
                channel_handle="@CalisthenicsTokyo",
                channel_id="cid",
                video_id="X8-rbhsd2ZY",
                video_title="bridge",
                video_url="https://www.youtube.com/shorts/X8-rbhsd2ZY",
                published_at=None,
                title_query="ができるなら",
                transcript_language="ja",
                transcript_quality_json={},
                ingest_status="review_pending",
                raw_extraction_json=None,
                created_at=datetime.now(),
            ),
        )
        with patch(
            "app.services.training_progression_service.training_progression_repo.list_review_items",
            AsyncMock(return_value=[item]),
        ):
            items = await list_review_items_with_presets(AsyncMock())
        assert items[0].preset_review is not None
        assert items[0].preset_review.to_exercise_id == "reverse_plank_raise"
        assert items[0].preset_review.goal_scope == ["bouldering", "strength"]

    @pytest.mark.asyncio
    async def test_apply_curated_progression_presets_reviews_only_matched_items(self) -> None:
        matched_item = TrainingProgressionReviewItem(
            edge=_approved_edge(
                from_id=None,
                to_id=None,
                from_reps=5,
                to_reps=1,
            ).model_copy(
                update={
                    "id": uuid4(),
                    "from_label_raw": "ディップスバーの上でスイング",
                    "to_label_raw": "スイングタックプラン",
                    "review_status": "pending",
                }
            ),
            source=TrainingProgressionSourceResponse(
                id=uuid4(),
                platform="youtube",
                channel_handle="@CalisthenicsTokyo",
                channel_id="cid",
                video_id="sNQX-X5J5nI",
                video_title="dip-bars",
                video_url="https://www.youtube.com/shorts/sNQX-X5J5nI",
                published_at=None,
                title_query="ができるなら",
                transcript_language="ja",
                transcript_quality_json={},
                ingest_status="review_pending",
                raw_extraction_json=None,
                created_at=datetime.now(),
            ),
        )
        unmatched_item = TrainingProgressionReviewItem(
            edge=_approved_edge(
                from_id=None,
                to_id=None,
            ).model_copy(
                update={
                    "id": uuid4(),
                    "from_label_raw": "未知A",
                    "to_label_raw": "未知B",
                    "review_status": "pending",
                }
            ),
            source=TrainingProgressionSourceResponse(
                id=uuid4(),
                platform="youtube",
                channel_handle="@CalisthenicsTokyo",
                channel_id="cid",
                video_id="unknown",
                video_title="unknown",
                video_url="https://www.youtube.com/shorts/unknown",
                published_at=None,
                title_query="ができるなら",
                transcript_language="ja",
                transcript_quality_json={},
                ingest_status="review_pending",
                raw_extraction_json=None,
                created_at=datetime.now(),
            ),
        )
        with (
            patch(
                "app.services.training_progression_service.training_progression_repo.list_review_items",
                AsyncMock(return_value=[matched_item, unmatched_item]),
            ),
            patch(
                "app.services.training_progression_service.review_progression_edge",
                AsyncMock(return_value=None),
            ) as mock_review,
        ):
            reviewed, skipped = await apply_curated_progression_presets(
                AsyncMock(),
                reviewed_by=uuid4(),
            )
        assert reviewed == 1
        assert skipped == 1
        mock_review.assert_awaited_once()
