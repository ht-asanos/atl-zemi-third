"""AppException とエラーコードのユニットテスト。"""

import pytest
from app.exceptions import AppException, ErrorCode, app_exception_handler
from fastapi import Request


class TestErrorCode:
    def test_all_codes_are_string_enum(self) -> None:
        """全エラーコードが文字列として使用できること。"""
        for code in ErrorCode:
            assert isinstance(code.value, str)

    def test_expected_codes_exist(self) -> None:
        """定義済みエラーコードが全て存在すること。"""
        expected = [
            "RECIPE_NOT_FOUND",
            "RECIPE_POOL_EXHAUSTED",
            "NETWORK_TIMEOUT",
            "VALIDATION_ERROR",
            "PLAN_NOT_FOUND",
            "GENERATION_FAILED",
            "CONFLICT",
            "GOAL_NOT_FOUND",
            "PROFILE_CONFLICT",
            "STAPLE_INVALID",
        ]
        actual = [c.value for c in ErrorCode]
        for code in expected:
            assert code in actual, f"{code} が ErrorCode に定義されていない"


class TestAppException:
    def test_creation(self) -> None:
        """AppException のフィールドが正しく設定されること。"""
        exc = AppException(ErrorCode.GOAL_NOT_FOUND, 404, "Goal not found")
        assert exc.error_code == ErrorCode.GOAL_NOT_FOUND
        assert exc.status_code == 404
        assert exc.detail == "Goal not found"

    def test_inherits_exception(self) -> None:
        """AppException は Exception を継承すること。"""
        exc = AppException(ErrorCode.CONFLICT, 409, "Conflict occurred")
        assert isinstance(exc, Exception)
        assert str(exc) == "Conflict occurred"

    def test_different_status_codes(self) -> None:
        """異なるステータスコードで作成できること。"""
        exc_404 = AppException(ErrorCode.PLAN_NOT_FOUND, 404, "Not found")
        exc_422 = AppException(ErrorCode.VALIDATION_ERROR, 422, "Invalid")
        exc_409 = AppException(ErrorCode.CONFLICT, 409, "Conflict")
        assert exc_404.status_code == 404
        assert exc_422.status_code == 422
        assert exc_409.status_code == 409


class TestAppExceptionHandler:
    @pytest.mark.asyncio
    async def test_handler_returns_json_response(self) -> None:
        """ハンドラが正しい JSON レスポンスを返すこと。"""
        exc = AppException(ErrorCode.RECIPE_NOT_FOUND, 404, "Recipe not found")
        # Request のモックを作成
        scope = {"type": "http", "method": "GET", "path": "/test"}
        request = Request(scope)

        response = await app_exception_handler(request, exc)

        assert response.status_code == 404
        # JSONResponse の body をデコードして検証
        import json

        body = json.loads(response.body)
        assert body["detail"] == "Recipe not found"
        assert body["error_code"] == "RECIPE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_handler_preserves_error_code(self) -> None:
        """ハンドラが error_code を正しくレスポンスに含めること。"""
        exc = AppException(ErrorCode.STAPLE_INVALID, 422, "Not a staple")
        scope = {"type": "http", "method": "POST", "path": "/plans/weekly"}
        request = Request(scope)

        response = await app_exception_handler(request, exc)

        import json

        body = json.loads(response.body)
        assert body["error_code"] == "STAPLE_INVALID"
        assert response.status_code == 422
