"""アプリケーション共通エラーコード定義。

全ルーターで統一的なエラーレスポンスを返すためのカスタム例外と
FastAPI 例外ハンドラを提供する。
"""

from enum import StrEnum

from fastapi import Request
from fastapi.responses import JSONResponse


class ErrorCode(StrEnum):
    """アプリケーション共通エラーコード。"""

    RECIPE_NOT_FOUND = "RECIPE_NOT_FOUND"
    RECIPE_POOL_EXHAUSTED = "RECIPE_POOL_EXHAUSTED"
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PLAN_NOT_FOUND = "PLAN_NOT_FOUND"
    GENERATION_FAILED = "GENERATION_FAILED"
    CONFLICT = "CONFLICT"
    GOAL_NOT_FOUND = "GOAL_NOT_FOUND"
    PROFILE_CONFLICT = "PROFILE_CONFLICT"
    STAPLE_INVALID = "STAPLE_INVALID"
    FEEDBACK_NOT_FOUND = "FEEDBACK_NOT_FOUND"


class AppException(Exception):
    """アプリケーション共通例外。

    error_code, status_code, detail を保持し、
    例外ハンドラで統一フォーマットの JSON レスポンスへ変換される。
    """

    def __init__(self, error_code: ErrorCode, status_code: int, detail: str) -> None:
        self.error_code = error_code
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
    """AppException を JSON レスポンスに変換する FastAPI 例外ハンドラ。"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error_code": exc.error_code.value,
        },
    )
