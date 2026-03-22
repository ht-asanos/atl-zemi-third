"""CLI コマンド共通ヘルパー"""

import sys

import httpx
from app.config import settings

from supabase import acreate_client


async def _get_service_client():
    """service-role key を使った AsyncClient を作成する。"""
    if not settings.supabase_service_role_key:
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY is not set")
        sys.exit(1)
    return await acreate_client(settings.supabase_url, settings.supabase_service_role_key)


def _external_http_client() -> httpx.AsyncClient:
    """外部サイトアクセス用 HTTP クライアント。SSL 検証可否は設定で切り替える。"""
    return httpx.AsyncClient(timeout=30.0, verify=settings.mext_http_verify_ssl)
