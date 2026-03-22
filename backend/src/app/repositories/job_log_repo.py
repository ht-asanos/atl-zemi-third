"""job_logs テーブル操作"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from supabase import AsyncClient


async def create_job_log(
    supabase: AsyncClient,
    *,
    run_id: UUID,
    job_name: str,
    attempt: int,
    triggered_by: str,
    status: str = "running",
    summary_json: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> UUID:
    response = await (
        supabase.table("job_logs")
        .insert(
            {
                "run_id": str(run_id),
                "job_name": job_name,
                "attempt": attempt,
                "triggered_by": triggered_by,
                "status": status,
                "summary_json": summary_json or {},
                "error_message": error_message,
            }
        )
        .execute()
    )
    rows: list[dict[str, Any]] = response.data or []
    return UUID(rows[0]["id"])


async def finish_job_log(
    supabase: AsyncClient,
    *,
    log_id: UUID,
    status: str,
    summary_json: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    await (
        supabase.table("job_logs")
        .update(
            {
                "status": status,
                "summary_json": summary_json or {},
                "error_message": error_message,
                "finished_at": datetime.now(UTC).isoformat(),
            }
        )
        .eq("id", str(log_id))
        .execute()
    )
