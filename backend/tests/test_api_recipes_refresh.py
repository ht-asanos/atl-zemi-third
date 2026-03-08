"""レシピ更新・backfill API のテスト"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.config import settings
from app.dependencies.auth import get_admin_user_id
from app.dependencies.supabase_client import get_service_supabase
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

ADMIN_USER_ID = uuid4()
NON_ADMIN_USER_ID = uuid4()


def _auth_header() -> dict:
    return {"Authorization": "Bearer dummy"}


@pytest.fixture(autouse=True)
def _override_deps():
    mock_sb = AsyncMock()
    app.dependency_overrides[get_admin_user_id] = lambda: ADMIN_USER_ID
    app.dependency_overrides[get_service_supabase] = lambda: mock_sb
    yield mock_sb
    app.dependency_overrides.clear()


class TestRefreshRecipes:
    def test_no_api_keys_returns_503(self, monkeypatch):
        monkeypatch.setattr(settings, "rakuten_app_id", "")
        monkeypatch.setattr(settings, "rakuten_access_key", "")
        resp = client.post("/recipes/refresh", headers=_auth_header())
        assert resp.status_code == 503

    def test_no_stale_categories(self, monkeypatch):
        monkeypatch.setattr(settings, "rakuten_app_id", "test_id")
        monkeypatch.setattr(settings, "rakuten_access_key", "test_key")

        with patch("app.routers.recipes.refresh_stale_recipes") as mock_refresh:
            from app.schemas.recipe import RefreshResult

            mock_refresh.return_value = RefreshResult(
                categories_checked=0, categories_refreshed=0, recipes_updated=0, errors=[]
            )
            resp = client.post("/recipes/refresh", headers=_auth_header())
            assert resp.status_code == 200
            data = resp.json()
            assert data["categories_refreshed"] == 0

    def test_stale_categories_triggers_upsert(self, monkeypatch):
        monkeypatch.setattr(settings, "rakuten_app_id", "test_id")
        monkeypatch.setattr(settings, "rakuten_access_key", "test_key")

        with patch("app.routers.recipes.refresh_stale_recipes") as mock_refresh:
            from app.schemas.recipe import RefreshResult

            mock_refresh.return_value = RefreshResult(
                categories_checked=2, categories_refreshed=2, recipes_updated=5, errors=[]
            )
            resp = client.post("/recipes/refresh", headers=_auth_header())
            assert resp.status_code == 200
            data = resp.json()
            assert data["recipes_updated"] == 5


class TestBackfillRecipes:
    def test_backfill_no_unmatched(self):
        with patch("app.routers.recipes.backfill_unmatched_ingredients") as mock_backfill:
            from app.schemas.recipe import BackfillResult

            mock_backfill.return_value = BackfillResult(
                unmatched_before=0,
                scraped_foods=0,
                matched_after=0,
                still_unmatched=0,
                errors=[],
            )
            resp = client.post("/recipes/backfill", headers=_auth_header())
            assert resp.status_code == 200
            data = resp.json()
            assert data["unmatched_before"] == 0


class TestNonAdminAccess:
    def test_refresh_non_admin_returns_403(self, monkeypatch):
        monkeypatch.setattr(settings, "rakuten_app_id", "test_id")
        monkeypatch.setattr(settings, "rakuten_access_key", "test_key")

        from fastapi import HTTPException

        def raise_403():
            raise HTTPException(status_code=403, detail="Admin access required")

        app.dependency_overrides[get_admin_user_id] = raise_403
        resp = client.post("/recipes/refresh", headers=_auth_header())
        assert resp.status_code == 403
