"""ingredient_mext_cache リポジトリのテスト"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from app.repositories.ingredient_cache_repo import (
    clear_all,
    get_cached,
    set_cached,
    set_cached_batch,
)

_FOOD_ID = "12345678-1234-1234-1234-123456789012"


def _make_select_supabase(data: list) -> MagicMock:
    """SELECT チェーンのモック"""
    supabase = MagicMock()
    chain = MagicMock()
    chain.execute = AsyncMock(return_value=type("R", (), {"data": data})())
    supabase.table.return_value.select.return_value.eq.return_value.limit.return_value = chain
    return supabase


def _make_upsert_supabase() -> tuple[MagicMock, list]:
    """UPSERT チェーンのモックと記録リスト"""
    supabase = MagicMock()
    captured: list = []

    def capture_upsert(data, **kwargs):
        captured.append(data)
        mock = MagicMock()
        mock.execute = AsyncMock(return_value=type("R", (), {"data": []})())
        return mock

    supabase.table.return_value.upsert = capture_upsert
    return supabase, captured


class TestGetCached:
    @pytest.mark.asyncio
    async def test_get_cached_hit(self):
        """キャッシュが存在する場合は (mext_food_id, confidence) を返す"""
        supabase = _make_select_supabase([{"mext_food_id": _FOOD_ID, "confidence": 0.75, "expires_at": None}])
        result = await get_cached(supabase, "たまねぎ りん茎")
        assert result is not None
        mext_id, confidence = result
        assert mext_id == UUID(_FOOD_ID)
        assert confidence == 0.75

    @pytest.mark.asyncio
    async def test_get_cached_miss(self):
        """キャッシュが存在しない場合は None を返す"""
        supabase = _make_select_supabase([])
        result = await get_cached(supabase, "パクチー")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_cached_no_match_entry(self):
        """mext_food_id=None の no_match エントリも返す"""
        supabase = _make_select_supabase([{"mext_food_id": None, "confidence": 0.0, "expires_at": None}])
        result = await get_cached(supabase, "謎の食材")
        assert result is not None
        mext_id, confidence = result
        assert mext_id is None
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_no_match_ttl_expired(self):
        """expires_at が過去 → TTL 超過として None を返す"""
        past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        supabase = _make_select_supabase([{"mext_food_id": None, "confidence": 0.0, "expires_at": past}])
        result = await get_cached(supabase, "謎の食材")
        assert result is None

    @pytest.mark.asyncio
    async def test_no_match_ttl_not_yet_expired(self):
        """expires_at が未来 → 有効なキャッシュとして返す"""
        future = (datetime.now(UTC) + timedelta(days=3)).isoformat()
        supabase = _make_select_supabase([{"mext_food_id": None, "confidence": 0.0, "expires_at": future}])
        result = await get_cached(supabase, "謎の食材")
        assert result is not None
        mext_id, confidence = result
        assert mext_id is None
        assert confidence == 0.0


class TestSetCached:
    @pytest.mark.asyncio
    async def test_set_cached_upsert_called(self):
        """set_cached が ingredient_mext_cache テーブルへ upsert を呼ぶ"""
        supabase, captured = _make_upsert_supabase()
        food_id = UUID(_FOOD_ID)
        await set_cached(supabase, "たまねぎ りん茎", food_id, 0.75, "trigram")
        supabase.table.assert_called_with("ingredient_mext_cache")
        assert len(captured) == 1
        record = captured[0]
        assert record["normalized_name"] == "たまねぎ りん茎"
        assert record["mext_food_id"] == _FOOD_ID
        assert record["confidence"] == 0.75
        assert record["source"] == "trigram"

    @pytest.mark.asyncio
    async def test_trigram_source_no_expires_at(self):
        """trigram マッチは expires_at=None（無期限）"""
        supabase, captured = _make_upsert_supabase()
        food_id = UUID(_FOOD_ID)
        await set_cached(supabase, "鶏卵", food_id, 0.8, "trigram")
        assert captured[0]["expires_at"] is None

    @pytest.mark.asyncio
    async def test_no_match_has_expires_at(self):
        """source='no_match' のとき expires_at が設定される"""
        supabase, captured = _make_upsert_supabase()
        await set_cached(supabase, "謎の食材", None, 0.0, "no_match")
        record = captured[0]
        assert record["expires_at"] is not None
        assert record["mext_food_id"] is None

    @pytest.mark.asyncio
    async def test_gemini_source_no_expires_at(self):
        """gemini マッチは expires_at=None（無期限）"""
        supabase, captured = _make_upsert_supabase()
        food_id = UUID(_FOOD_ID)
        await set_cached(supabase, "チキン", food_id, 0.65, "gemini")
        assert captured[0]["expires_at"] is None


class TestSetCachedBatch:
    @pytest.mark.asyncio
    async def test_set_cached_batch_empty_no_op(self):
        """空リストの場合は table() を呼ばない"""
        supabase = MagicMock()
        await set_cached_batch(supabase, [])
        supabase.table.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_cached_batch_upserts_all(self):
        """複数エントリをまとめて 1 回の upsert で保存する"""
        supabase, captured = _make_upsert_supabase()
        entries = [
            {"normalized_name": "たまご", "mext_food_id": None, "confidence": 0.0, "source": "no_match"},
            {"normalized_name": "鶏卵", "mext_food_id": _FOOD_ID, "confidence": 0.65, "source": "gemini"},
        ]
        await set_cached_batch(supabase, entries)
        supabase.table.assert_called_with("ingredient_mext_cache")
        assert len(captured) == 1  # 1 回の upsert で両方保存
        records = captured[0]
        assert len(records) == 2

    @pytest.mark.asyncio
    async def test_set_cached_batch_no_match_has_ttl(self):
        """バッチ内の no_match エントリに expires_at が設定される"""
        supabase, captured = _make_upsert_supabase()
        entries = [
            {"normalized_name": "謎食材1", "mext_food_id": None, "confidence": 0.0, "source": "no_match"},
            {"normalized_name": "鶏もも", "mext_food_id": _FOOD_ID, "confidence": 0.75, "source": "trigram"},
        ]
        await set_cached_batch(supabase, entries)
        records = captured[0]
        no_match_record = next(r for r in records if r["normalized_name"] == "謎食材1")
        trigram_record = next(r for r in records if r["normalized_name"] == "鶏もも")
        assert no_match_record["expires_at"] is not None
        assert trigram_record["expires_at"] is None


class TestClearAll:
    @pytest.mark.asyncio
    async def test_clear_all_calls_delete(self):
        """clear_all が ingredient_mext_cache テーブルを delete する"""
        supabase = MagicMock()
        supabase.table.return_value.delete.return_value.neq.return_value.execute = AsyncMock(
            return_value=type("R", (), {"data": []})()
        )
        await clear_all(supabase)
        supabase.table.assert_called_with("ingredient_mext_cache")
        supabase.table.return_value.delete.assert_called_once()
