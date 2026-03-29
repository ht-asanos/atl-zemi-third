from datetime import datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.config import settings
from app.dependencies.auth import get_admin_user_id
from app.dependencies.supabase_client import get_service_supabase
from app.main import app
from app.models.training import Exercise, MuscleGroup
from app.schemas.training_progression import (
    AdminTrainingProgressionGraphEdge,
    AdminTrainingProgressionGraphNode,
    AdminTrainingProgressionGraphResponse,
    AdminTrainingProgressionGraphSummary,
    AdminTrainingProgressionGraphTrack,
    TrainingProgressionEdgeResponse,
    TrainingProgressionIngestVideoResult,
    TrainingProgressionPresetReview,
    TrainingProgressionReviewItem,
    TrainingProgressionSourceResponse,
)
from fastapi.testclient import TestClient


def test_list_training_progression_review_returns_items() -> None:
    mock_supabase = object()
    app.dependency_overrides[get_admin_user_id] = lambda: uuid4()
    app.dependency_overrides[get_service_supabase] = lambda: mock_supabase

    review_item = TrainingProgressionReviewItem(
        edge=TrainingProgressionEdgeResponse(
            id=uuid4(),
            source_id=uuid4(),
            from_label_raw="懸垂",
            from_exercise_id=None,
            from_reps=10,
            to_label_raw="チンアップ",
            to_exercise_id=None,
            to_reps=5,
            relation_type="unlock_if_can_do",
            goal_scope=["bouldering", "strength"],
            evidence_text="懸垂が10回できるなら",
            confidence=0.9,
            review_status="pending",
            review_note=None,
            reviewed_by=None,
            reviewed_at=None,
            created_at=datetime.now(),
        ),
        source=TrainingProgressionSourceResponse(
            id=uuid4(),
            platform="youtube",
            channel_handle="@CalisthenicsTokyo",
            channel_id="cid",
            video_id="abc123def45",
            video_title="懸垂ができるなら",
            video_url="https://www.youtube.com/shorts/abc123def45",
            published_at=None,
            title_query="ができるなら",
            transcript_language="ja",
            transcript_quality_json={},
            ingest_status="review_pending",
            raw_extraction_json=None,
            created_at=datetime.now(),
        ),
        preset_review=TrainingProgressionPresetReview(
            from_exercise_id="pull_up",
            from_reps=10,
            to_exercise_id="chin_up",
            to_reps=5,
            goal_scope=["bouldering", "strength"],
            review_note="curated",
            add_aliases=[],
        ),
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        with patch(
            "app.routers.admin_training_progressions.list_review_items_with_presets",
            AsyncMock(return_value=[review_item]),
        ):
            response = client.get("/admin/training-progressions/review")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["preset_review"]["to_exercise_id"] == "chin_up"


def test_ingest_training_progressions_endpoint() -> None:
    mock_supabase = object()
    app.dependency_overrides[get_admin_user_id] = lambda: uuid4()
    app.dependency_overrides[get_service_supabase] = lambda: mock_supabase

    with (
        patch.object(settings, "youtube_api_key", "yt-key"),
        patch.object(settings, "google_api_key", "google-key"),
        patch(
            "app.routers.admin_training_progressions.ingest_training_progressions",
            AsyncMock(
                return_value=(
                    [
                        TrainingProgressionIngestVideoResult(
                            video_id="abc123def45",
                            video_title="懸垂ができるなら",
                            status="review_pending",
                            source_id=str(uuid4()),
                            edges_created=2,
                        )
                    ],
                    type(
                        "Stats",
                        (),
                        {
                            "videos_found": 1,
                            "videos_scanned": 2,
                            "videos_title_matched": 1,
                            "videos_processed": 1,
                            "transcripts_fetched": 1,
                            "transcripts_naturalized": 1,
                            "videos_with_edges": 1,
                            "edges_created": 2,
                        },
                    )(),
                )
            ),
        ),
    ):
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/admin/training-progressions/ingest",
                json={"channel_handle": "@CalisthenicsTokyo", "title_keyword": "ができるなら", "max_results": 10},
            )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["videos_found"] == 1
    assert body["edges_created"] == 2
    assert body["results"][0]["status"] == "review_pending"


def test_list_training_progression_catalog_endpoint() -> None:
    mock_supabase = object()
    app.dependency_overrides[get_admin_user_id] = lambda: uuid4()
    app.dependency_overrides[get_service_supabase] = lambda: mock_supabase

    catalog = {
        "push_up": Exercise(
            id="push_up",
            name_ja="プッシュアップ",
            muscle_group=MuscleGroup.CHEST,
            sets=3,
            reps=12,
            rest_seconds=60,
        )
    }
    with TestClient(app, raise_server_exceptions=False) as client:
        with patch(
            "app.routers.admin_training_progressions.get_exercise_catalog",
            return_value=catalog,
        ):
            response = client.get("/admin/training-progressions/catalog")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()[0]["id"] == "push_up"


def test_review_progression_endpoint() -> None:
    mock_supabase = object()
    admin_id = uuid4()
    edge_id = uuid4()
    app.dependency_overrides[get_admin_user_id] = lambda: admin_id
    app.dependency_overrides[get_service_supabase] = lambda: mock_supabase

    with TestClient(app, raise_server_exceptions=False) as client:
        with patch(
            "app.routers.admin_training_progressions.review_progression_edge",
            AsyncMock(return_value=None),
        ) as mock_review:
            response = client.post(
                f"/admin/training-progressions/review/{edge_id}",
                json={
                    "review_status": "approved",
                    "from_exercise_id": "pull_up",
                    "from_reps": 10,
                    "to_exercise_id": "chin_up",
                    "to_reps": 5,
                    "goal_scope": ["bouldering", "strength"],
                    "review_note": "looks good",
                    "add_aliases": ["懸垂"],
                },
            )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    mock_review.assert_awaited_once()
    _, kwargs = mock_review.call_args
    assert kwargs["edge_id"] == edge_id
    assert kwargs["reviewed_by"] == admin_id
    assert kwargs["to_exercise_id"] == "chin_up"


def test_apply_progression_presets_endpoint() -> None:
    mock_supabase = object()
    admin_id = uuid4()
    app.dependency_overrides[get_admin_user_id] = lambda: admin_id
    app.dependency_overrides[get_service_supabase] = lambda: mock_supabase

    with TestClient(app, raise_server_exceptions=False) as client:
        with patch(
            "app.routers.admin_training_progressions.apply_curated_progression_presets",
            AsyncMock(return_value=(8, 2)),
        ) as mock_apply:
            response = client.post("/admin/training-progressions/apply-presets")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"reviewed": 8, "skipped": 2}
    mock_apply.assert_awaited_once()
    _, kwargs = mock_apply.call_args
    assert kwargs["reviewed_by"] == admin_id


def test_get_progression_graph_endpoint() -> None:
    mock_supabase = object()
    app.dependency_overrides[get_admin_user_id] = lambda: uuid4()
    app.dependency_overrides[get_service_supabase] = lambda: mock_supabase

    graph = AdminTrainingProgressionGraphResponse(
        summary=AdminTrainingProgressionGraphSummary(
            status="approved",
            goal_type="strength",
            edge_count=1,
            track_count=1,
            unmapped_edge_count=0,
        ),
        tracks=[
            AdminTrainingProgressionGraphTrack(
                track_id="reverse_scapular_push_up",
                title="リバーススキャピュラープッシュアップ",
                nodes=[
                    AdminTrainingProgressionGraphNode(
                        exercise_id="reverse_scapular_push_up",
                        name_ja="リバーススキャピュラープッシュアップ",
                        required_equipment=["none"],
                        review_count=1,
                    ),
                    AdminTrainingProgressionGraphNode(
                        exercise_id="reverse_plank_raise",
                        name_ja="リバースプランクレイズ",
                        required_equipment=["none"],
                        review_count=1,
                    ),
                ],
                edges=[
                    AdminTrainingProgressionGraphEdge(
                        edge_id=uuid4(),
                        from_exercise_id="reverse_scapular_push_up",
                        to_exercise_id="reverse_plank_raise",
                        from_reps_required=10,
                        to_reps_target=1,
                        review_status="approved",
                        video_id="X8-rbhsd2ZY",
                        video_title="bridge",
                        review_note="curated",
                    )
                ],
            )
        ],
        unmapped_edges=[],
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        with patch(
            "app.routers.admin_training_progressions.build_admin_training_progression_graph",
            AsyncMock(return_value=graph),
        ) as mock_graph:
            response = client.get("/admin/training-progressions/graph?status=approved&goal_type=strength")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["summary"]["track_count"] == 1
    assert response.json()["tracks"][0]["edges"][0]["video_id"] == "X8-rbhsd2ZY"
    mock_graph.assert_awaited_once()
