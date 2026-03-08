from functools import lru_cache
from uuid import UUID

import jwt
from app.config import settings
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

__all__ = ["get_current_user_id", "get_admin_user_id"]

_bearer = HTTPBearer()


@lru_cache(maxsize=1)
def _get_jwk_client() -> PyJWKClient:
    jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
    return PyJWKClient(jwks_url, cache_keys=True)


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> UUID:
    token = credentials.credentials
    try:
        # Try JWKS-based verification first (ES256, Supabase CLI v2.x+)
        jwk_client = _get_jwk_client()
        signing_key = jwk_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "HS256"],
            audience="authenticated",
            issuer=f"{settings.supabase_url}/auth/v1",
            options={"require": ["exp", "iss", "sub"]},
        )
    except (jwt.InvalidTokenError, Exception) as jwks_err:
        # Fallback: HS256 with shared secret (older Supabase / hosted)
        if settings.supabase_jwt_secret:
            try:
                payload = jwt.decode(
                    token,
                    settings.supabase_jwt_secret,
                    algorithms=["HS256"],
                    audience="authenticated",
                    issuer=f"{settings.supabase_url}/auth/v1",
                    options={"require": ["exp", "iss", "sub"]},
                )
            except jwt.InvalidTokenError as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid token: {e}",
                ) from e
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {jwks_err}",
            ) from jwks_err

    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing sub claim",
        )

    try:
        return UUID(sub)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid sub claim format",
        ) from e


def get_admin_user_id(
    user_id: UUID = Depends(get_current_user_id),
) -> UUID:
    """管理者限定。ADMIN_USER_IDS に含まれない場合は 403。"""
    allowed = {UUID(uid.strip()) for uid in settings.admin_user_ids.split(",") if uid.strip()}
    if not allowed or user_id not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user_id
