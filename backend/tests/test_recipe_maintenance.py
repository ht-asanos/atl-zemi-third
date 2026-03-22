from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.services import data_loader
from app.services.recipe_maintenance import prune_non_meal_recipes, run_recipe_maintenance


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeDeleteQuery:
    def __init__(self, table_name: str, deletes: list[tuple[str, str, list[str]]]):
        self.table_name = table_name
        self.deletes = deletes
        self.column = None
        self.values = None

    def in_(self, column, values):
        self.column = column
        self.values = list(values)
        return self

    async def execute(self):
        assert self.column is not None
        assert self.values is not None
        self.deletes.append((self.table_name, self.column, self.values))
        return _FakeResponse([])


class _FakeTable:
    def __init__(self, name: str, responses: dict[str, list[dict]], deletes: list[tuple[str, str, list[str]]]):
        self.name = name
        self.responses = responses
        self.deletes = deletes

    def select(self, *_args):
        return self

    async def execute(self):
        return _FakeResponse(self.responses[self.name])

    def delete(self):
        return _FakeDeleteQuery(self.name, self.deletes)


class _FakeSupabase:
    def __init__(self, responses: dict[str, list[dict]]):
        self.responses = responses
        self.deletes: list[tuple[str, str, list[str]]] = []

    def table(self, name: str):
        return _FakeTable(name, self.responses, self.deletes)


@pytest.mark.asyncio
async def test_prune_non_meal_recipes_deletes_rejected(tmp_path: Path):
    supabase = _FakeSupabase(
        {
            "recipes": [
                {"id": "r1", "title": "鍋焼きうどん", "description": "", "tags": ["うどん"]},
                {"id": "r2", "title": "つけ汁", "description": "", "tags": ["うどん"]},
            ],
            "recipe_ingredients": [
                {"recipe_id": "r1", "ingredient_name": "うどん"},
                {"recipe_id": "r2", "ingredient_name": "めんつゆ"},
            ],
        }
    )
    output_path = tmp_path / "prune_candidates.json"

    mocked_gate = type(
        "Gate",
        (),
        {
            "accepted": [{"id": "r1", "title": "鍋焼きうどん"}],
            "rejected": [{"recipe": {"id": "r2", "title": "つけ汁"}, "reason": "not_meal_like"}],
        },
    )()

    with patch("app.services.recipe_maintenance.filter_meal_like_recipes", AsyncMock(return_value=mocked_gate)):
        result = await prune_non_meal_recipes(supabase, execute=True, output_path=str(output_path))

    assert result["candidate_count"] == 1
    assert result["deleted_count"] == 1
    assert supabase.deletes == [
        ("recipe_ingredients", "recipe_id", ["r2"]),
        ("recipes", "id", ["r2"]),
    ]
    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved == [{"id": "r2", "title": "つけ汁", "reason": "not_meal_like"}]


@pytest.mark.asyncio
async def test_run_recipe_maintenance_retries_and_records_logs():
    supabase = AsyncMock()
    create_ids = [uuid4(), uuid4(), uuid4(), uuid4()]
    refresh = AsyncMock(side_effect=[RuntimeError("boom"), {"recipes_updated": 3}])
    backfill = AsyncMock(return_value={"backfill": {"matched_after": 2}})
    prune = AsyncMock(return_value={"deleted_count": 1})

    with (
        patch("app.services.recipe_maintenance._get_service_client", AsyncMock(return_value=supabase)),
        patch("app.services.recipe_maintenance.job_log_repo.create_job_log", AsyncMock(side_effect=create_ids)),
        patch("app.services.recipe_maintenance.job_log_repo.finish_job_log", AsyncMock()) as finish_log,
        patch("app.services.recipe_maintenance._run_refresh_job", refresh),
        patch("app.services.recipe_maintenance._run_backfill_job", backfill),
        patch("app.services.recipe_maintenance._run_prune_job", prune),
    ):
        result = await run_recipe_maintenance(triggered_by="schedule")

    assert result.run_id
    assert result.has_failures is False
    assert [job.job_name for job in result.jobs] == [
        "refresh-recipes",
        "backfill",
        "prune-non-meal-recipes",
    ]
    assert result.jobs[0].attempt_count == 2
    assert finish_log.await_args_list[0].kwargs["status"] == "failed"
    assert finish_log.await_args_list[1].kwargs["status"] == "success"
    assert finish_log.await_args_list[2].kwargs["status"] == "success"
    assert finish_log.await_args_list[3].kwargs["status"] == "success"


@pytest.mark.asyncio
async def test_run_recipe_maintenance_continues_after_failed_job():
    supabase = AsyncMock()
    create_ids = [uuid4() for _ in range(5)]
    refresh = AsyncMock(side_effect=[RuntimeError("boom")] * 3)
    backfill = AsyncMock(return_value={"backfill": {"matched_after": 2}})
    prune = AsyncMock(return_value={"deleted_count": 1})

    with (
        patch("app.services.recipe_maintenance._get_service_client", AsyncMock(return_value=supabase)),
        patch("app.services.recipe_maintenance.job_log_repo.create_job_log", AsyncMock(side_effect=create_ids)),
        patch("app.services.recipe_maintenance.job_log_repo.finish_job_log", AsyncMock()) as finish_log,
        patch("app.services.recipe_maintenance._run_refresh_job", refresh),
        patch("app.services.recipe_maintenance._run_backfill_job", backfill),
        patch("app.services.recipe_maintenance._run_prune_job", prune),
    ):
        result = await run_recipe_maintenance(triggered_by="manual")

    assert result.has_failures is True
    assert result.jobs[0].succeeded is False
    assert result.jobs[1].succeeded is True
    assert result.jobs[2].succeeded is True
    assert finish_log.await_count == 5


def test_data_loader_dispatches_run_recipe_maintenance(monkeypatch):
    called: dict[str, str] = {}

    async def fake_cmd_run_recipe_maintenance(*, triggered_by: str):
        called["triggered_by"] = triggered_by

    monkeypatch.setattr(data_loader, "cmd_run_recipe_maintenance", fake_cmd_run_recipe_maintenance)
    monkeypatch.setattr(
        data_loader,
        "sys",
        type("FakeSys", (), {"argv": ["data_loader.py", "run-recipe-maintenance", "--triggered-by", "schedule"]}),
    )

    data_loader.main()

    assert called["triggered_by"] == "schedule"
