from datetime import date
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.dependencies.auth import get_current_user_id
from app.dependencies.supabase_client import get_authenticated_supabase
from app.main import app
from app.schemas.plan import ShoppingListResponse
from fastapi.testclient import TestClient

TEST_USER_ID = uuid4()


@pytest.fixture
def client():
    mock_supabase = AsyncMock()
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_authenticated_supabase] = lambda: mock_supabase
    yield TestClient(app, raise_server_exceptions=False), mock_supabase
    app.dependency_overrides.clear()


def test_get_shopping_list_checks(client) -> None:
    test_client, _ = client
    with patch(
        "app.routers.plans.shopping_check_repo.get_checked_group_ids", new=AsyncMock(return_value={"g:a", "g:b"})
    ):
        resp = test_client.get("/plans/weekly/shopping-list/checks?start_date=2026-03-09")

    assert resp.status_code == 200
    body = resp.json()
    assert body["start_date"] == "2026-03-09"
    assert body["checked_group_ids"] == ["g:a", "g:b"]


def test_post_shopping_list_check(client) -> None:
    test_client, _ = client
    with patch("app.routers.plans.shopping_check_repo.set_group_checked", new=AsyncMock()) as mock_set:
        resp = test_client.post(
            "/plans/weekly/shopping-list/checks",
            json={
                "start_date": "2026-03-09",
                "group_id": "g:abc",
                "checked": True,
            },
        )

    assert resp.status_code == 204
    mock_set.assert_awaited_once()
    kwargs = mock_set.await_args.kwargs
    assert kwargs["user_id"] == TEST_USER_ID
    assert kwargs["start_date"] == date(2026, 3, 9)
    assert kwargs["group_id"] == "g:abc"
    assert kwargs["checked"] is True


def test_get_shopping_list_passes_checked_groups(client) -> None:
    test_client, _ = client
    with (
        patch("app.routers.plans.shopping_check_repo.get_checked_group_ids", new=AsyncMock(return_value={"g:abc"})),
        patch(
            "app.routers.plans.generate_shopping_list",
            new=AsyncMock(
                return_value=ShoppingListResponse(
                    start_date=date(2026, 3, 9),
                    items=[],
                    recipe_count=0,
                )
            ),
        ) as mock_gen,
    ):
        resp = test_client.get("/plans/weekly/shopping-list?start_date=2026-03-09")

    assert resp.status_code == 200
    mock_gen.assert_awaited_once()
    kwargs = mock_gen.await_args.kwargs
    assert kwargs["checked_group_ids"] == {"g:abc"}
