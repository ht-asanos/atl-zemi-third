from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from supabase import AsyncClient

_bearer = HTTPBearer()


def get_supabase_client(request: Request) -> AsyncClient:
    return request.app.state.supabase


async def get_authenticated_supabase(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> AsyncClient:
    client: AsyncClient = request.app.state.supabase
    client.postgrest.auth(credentials.credentials)
    return client


def get_service_supabase(request: Request) -> AsyncClient:
    """管理ジョブ専用。RLS をバイパスして書き込み可能。"""
    return request.app.state.service_supabase
