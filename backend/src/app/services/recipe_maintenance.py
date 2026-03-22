"""レシピ保守ジョブの共通ランナー。"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from app.config import settings
from app.repositories import job_log_repo
from app.services.cli._shared import _external_http_client, _get_service_client
from app.services.recipe_quality_gate import filter_meal_like_recipes
from app.services.recipe_refresh import (
    backfill_missing_normalized_ingredients,
    backfill_unmatched_ingredients,
    refresh_stale_recipes,
)

from supabase import AsyncClient

MAX_RETRIES = 3


@dataclass
class MaintenanceJobResult:
    job_name: str
    attempt_count: int
    succeeded: bool
    summary: dict[str, Any]
    error_message: str | None = None


@dataclass
class MaintenanceRunResult:
    run_id: UUID
    triggered_by: str
    jobs: list[MaintenanceJobResult]

    @property
    def has_failures(self) -> bool:
        return any(not job.succeeded for job in self.jobs)


def _require_setting(value: str, env_name: str) -> None:
    if not value:
        raise RuntimeError(f"{env_name} is not set")


async def prune_non_meal_recipes(
    supabase: AsyncClient,
    *,
    execute: bool,
    output_path: str | None = None,
) -> dict[str, Any]:
    """既存 recipes を品質ゲートで再判定し、非食事レシピを削除する。"""
    resp = await supabase.table("recipes").select("id,title,description,tags").execute()
    rows = resp.data or []
    if not rows:
        return {
            "total_recipes": 0,
            "candidate_count": 0,
            "deleted_count": 0,
            "candidate_titles": [],
        }

    ing_resp = await supabase.table("recipe_ingredients").select("recipe_id,ingredient_name").execute()
    ing_rows = ing_resp.data or []
    ing_map: dict[str, list[dict[str, str | None]]] = {}
    for row in ing_rows:
        rid = row.get("recipe_id")
        if not rid:
            continue
        ing_map.setdefault(rid, []).append(
            {
                "ingredient_name": row.get("ingredient_name", ""),
                "amount_text": None,
            }
        )

    recipes = [
        {
            "id": r.get("id"),
            "title": r.get("title", ""),
            "description": r.get("description", ""),
            "tags": r.get("tags") or [],
            "ingredients": ing_map.get(r.get("id"), []),
        }
        for r in rows
    ]

    gate = await filter_meal_like_recipes(recipes)
    rejected = gate.rejected
    reject_ids = [x["recipe"].get("id") for x in rejected if x["recipe"].get("id")]
    reject_ids = [x for x in reject_ids if x]

    candidates = [
        {
            "id": x["recipe"].get("id"),
            "title": x["recipe"].get("title", ""),
            "reason": x.get("reason", ""),
        }
        for x in rejected
    ]

    if output_path:
        Path(output_path).write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")

    deleted_count = 0
    if execute and reject_ids:
        await supabase.table("recipe_ingredients").delete().in_("recipe_id", reject_ids).execute()
        await supabase.table("recipes").delete().in_("id", reject_ids).execute()
        deleted_count = len(reject_ids)

    return {
        "total_recipes": len(recipes),
        "candidate_count": len(reject_ids),
        "deleted_count": deleted_count,
        "candidate_titles": [c["title"] for c in candidates[:20]],
    }


async def _run_refresh_job(supabase: AsyncClient) -> dict[str, Any]:
    _require_setting(settings.rakuten_app_id, "RAKUTEN_APP_ID")
    _require_setting(settings.rakuten_access_key, "RAKUTEN_ACCESS_KEY")
    async with _external_http_client() as http_client:
        result = await refresh_stale_recipes(
            supabase,
            http_client,
            settings.rakuten_app_id,
            settings.rakuten_access_key,
        )
    return result.model_dump()


async def _run_backfill_job(supabase: AsyncClient) -> dict[str, Any]:
    async with _external_http_client() as http_client:
        normalized = await backfill_missing_normalized_ingredients(supabase, http_client)
        result = await backfill_unmatched_ingredients(supabase, http_client)
    return {
        "normalized": normalized,
        "backfill": result.model_dump(),
    }


async def _run_prune_job(supabase: AsyncClient) -> dict[str, Any]:
    _require_setting(settings.google_api_key, "GOOGLE_API_KEY")
    return await prune_non_meal_recipes(supabase, execute=True)


async def _run_job_with_retries(
    supabase: AsyncClient,
    *,
    run_id: UUID,
    triggered_by: str,
    job_name: str,
    runner: Callable[[AsyncClient], Awaitable[dict[str, Any]]],
) -> MaintenanceJobResult:
    last_error: str | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        log_id = await job_log_repo.create_job_log(
            supabase,
            run_id=run_id,
            job_name=job_name,
            attempt=attempt,
            triggered_by=triggered_by,
        )
        try:
            summary = await runner(supabase)
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            await job_log_repo.finish_job_log(
                supabase,
                log_id=log_id,
                status="failed",
                summary_json={},
                error_message=last_error,
            )
            if attempt == MAX_RETRIES:
                return MaintenanceJobResult(
                    job_name=job_name,
                    attempt_count=attempt,
                    succeeded=False,
                    summary={},
                    error_message=last_error,
                )
            continue

        await job_log_repo.finish_job_log(
            supabase,
            log_id=log_id,
            status="success",
            summary_json=summary,
        )
        return MaintenanceJobResult(
            job_name=job_name,
            attempt_count=attempt,
            succeeded=True,
            summary=summary,
        )

    return MaintenanceJobResult(
        job_name=job_name,
        attempt_count=MAX_RETRIES,
        succeeded=False,
        summary={},
        error_message=last_error,
    )


async def run_recipe_maintenance(*, triggered_by: str) -> MaintenanceRunResult:
    if triggered_by not in {"schedule", "manual"}:
        raise ValueError("triggered_by must be 'schedule' or 'manual'")

    supabase = await _get_service_client()
    run_id = uuid4()
    jobs = [
        ("refresh-recipes", _run_refresh_job),
        ("backfill", _run_backfill_job),
        ("prune-non-meal-recipes", _run_prune_job),
    ]

    results: list[MaintenanceJobResult] = []
    for job_name, runner in jobs:
        result = await _run_job_with_retries(
            supabase,
            run_id=run_id,
            triggered_by=triggered_by,
            job_name=job_name,
            runner=runner,
        )
        results.append(result)

    return MaintenanceRunResult(run_id=run_id, triggered_by=triggered_by, jobs=results)
