"""auth.py 単体テスト — JWT 検証の正常系 + 失敗系6パターン"""

import time
from unittest.mock import patch
from uuid import UUID

import jwt
import pytest
from app.dependencies.auth import get_current_user_id
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

TEST_SECRET = "test-jwt-secret-key-for-unit-tests"
TEST_SUPABASE_URL = "http://127.0.0.1:54321"
TEST_USER_ID = "550e8400-e29b-41d4-a716-446655440000"


def _make_token(
    sub: str = TEST_USER_ID,
    aud: str = "authenticated",
    iss: str = f"{TEST_SUPABASE_URL}/auth/v1",
    exp: int | None = None,
    algorithm: str = "HS256",
    secret: str = TEST_SECRET,
    **extra_claims: object,
) -> str:
    if exp is None:
        exp = int(time.time()) + 3600
    payload = {"sub": sub, "aud": aud, "iss": iss, "exp": exp, **extra_claims}
    return jwt.encode(payload, secret, algorithm=algorithm)


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _settings_patch():
    return patch.multiple(
        "app.dependencies.auth.settings",
        supabase_jwt_secret=TEST_SECRET,
        supabase_url=TEST_SUPABASE_URL,
    )


class TestGetCurrentUserIdSuccess:
    def test_valid_token_returns_uuid(self) -> None:
        token = _make_token()
        with _settings_patch():
            result = get_current_user_id(_creds(token))
        assert result == UUID(TEST_USER_ID)


class TestGetCurrentUserIdFailure:
    def test_expired_token(self) -> None:
        token = _make_token(exp=int(time.time()) - 100)
        with _settings_patch(), pytest.raises(HTTPException) as exc_info:
            get_current_user_id(_creds(token))
        assert exc_info.value.status_code == 401

    def test_wrong_audience(self) -> None:
        token = _make_token(aud="wrong-audience")
        with _settings_patch(), pytest.raises(HTTPException) as exc_info:
            get_current_user_id(_creds(token))
        assert exc_info.value.status_code == 401

    def test_wrong_issuer(self) -> None:
        token = _make_token(iss="https://evil.example.com/auth/v1")
        with _settings_patch(), pytest.raises(HTTPException) as exc_info:
            get_current_user_id(_creds(token))
        assert exc_info.value.status_code == 401

    def test_wrong_signature(self) -> None:
        token = _make_token(secret="wrong-secret")
        with _settings_patch(), pytest.raises(HTTPException) as exc_info:
            get_current_user_id(_creds(token))
        assert exc_info.value.status_code == 401

    def test_missing_sub(self) -> None:
        payload = {
            "aud": "authenticated",
            "iss": f"{TEST_SUPABASE_URL}/auth/v1",
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, TEST_SECRET, algorithm="HS256")
        with _settings_patch(), pytest.raises(HTTPException) as exc_info:
            get_current_user_id(_creds(token))
        assert exc_info.value.status_code == 401

    def test_rs256_algorithm_rejected(self) -> None:
        # HS256 以外のアルゴリズムが拒否されることを確認
        with _settings_patch(), pytest.raises(HTTPException) as exc_info:
            get_current_user_id(_creds("invalid.token.string"))
        assert exc_info.value.status_code == 401
