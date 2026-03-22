"""ingredient_mext_cache テーブル操作

食材正規化名 → MEXT 食品 ID のマッチング結果を永続化するキャッシュ。
- trigram / gemini エントリは無期限（expires_at = NULL）
- no_match エントリは TTL 7 日（expires_at = now() + 7 days）
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from supabase import AsyncClient

logger = logging.getLogger(__name__)

NO_MATCH_TTL_DAYS = 7


async def get_cached(
    supabase: AsyncClient,
    normalized_name: str,
) -> tuple[UUID | None, float] | None:
    """有効なキャッシュを返す。expires_at 超過分は無視し None を返す。

    Returns:
        (mext_food_id, confidence) — mext_food_id は None の場合もある（no_match）
        None — キャッシュミス
    """
    response = await (
        supabase.table("ingredient_mext_cache")
        .select("mext_food_id, confidence, expires_at")
        .eq("normalized_name", normalized_name)
        .limit(1)
        .execute()
    )
    rows: list[dict[str, Any]] = response.data or []
    if not rows:
        return None

    row = rows[0]

    # TTL チェック
    expires_at = row.get("expires_at")
    if expires_at is not None:
        if isinstance(expires_at, str):
            try:
                exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            except ValueError:
                exp = None
        elif isinstance(expires_at, datetime):
            exp = expires_at
        else:
            exp = None

        if exp is not None:
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=UTC)
            if datetime.now(UTC) > exp:
                return None  # TTL 超過 → キャッシュミス扱い

    mext_food_id = row.get("mext_food_id")
    confidence = float(row.get("confidence") or 0.0)
    return (UUID(mext_food_id) if mext_food_id else None), confidence


async def set_cached(
    supabase: AsyncClient,
    normalized_name: str,
    mext_food_id: UUID | None,
    confidence: float,
    source: str,
) -> None:
    """UPSERT。source='no_match' 時のみ expires_at = now() + 7 days。"""
    now = datetime.now(UTC)
    expires_at: str | None = None
    if source == "no_match":
        expires_at = (now + timedelta(days=NO_MATCH_TTL_DAYS)).isoformat()

    record: dict[str, Any] = {
        "normalized_name": normalized_name,
        "mext_food_id": str(mext_food_id) if mext_food_id else None,
        "confidence": confidence,
        "source": source,
        "updated_at": now.isoformat(),
        "expires_at": expires_at,
    }
    await supabase.table("ingredient_mext_cache").upsert(record, on_conflict="normalized_name").execute()


async def set_cached_batch(
    supabase: AsyncClient,
    entries: list[dict[str, Any]],
) -> None:
    """複数エントリを一括 UPSERT。"""
    if not entries:
        return

    now = datetime.now(UTC)
    records: list[dict[str, Any]] = []
    for e in entries:
        source = e["source"]
        expires_at: str | None = None
        if source == "no_match":
            expires_at = (now + timedelta(days=NO_MATCH_TTL_DAYS)).isoformat()

        mext_food_id = e.get("mext_food_id")
        records.append(
            {
                "normalized_name": e["normalized_name"],
                "mext_food_id": str(mext_food_id) if mext_food_id else None,
                "confidence": e["confidence"],
                "source": source,
                "updated_at": now.isoformat(),
                "expires_at": expires_at,
            }
        )

    await supabase.table("ingredient_mext_cache").upsert(records, on_conflict="normalized_name").execute()


async def clear_all(supabase: AsyncClient) -> None:
    """全キャッシュ削除。MEXT 全再投入時に使用。"""
    await supabase.table("ingredient_mext_cache").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
