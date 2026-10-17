"""
统一异常定义 + FastAPI 全局错误处理。

所有业务异常继承 AppError，返回统一 JSON 格式：
{"error": {"code": "...", "message": "...", "details": ...}}
"""
import logging
import traceback
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("mathmodel.errors")


class AppError(Exception):
    """业务异常基类。"""
    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred"

    def __init__(self, message: str = None, details: dict = None):
        self.message = message or self.__class__.message
        self.details = details or {}

    def to_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.status_code,
            content={
                "error": {
                    "code": self.code,
                    "message": self.message,
                    "details": self.details,
                }
            },
        )


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    message = "Resource not found"


class ValidationError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"
    message = "Validation failed"


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"
    message = "Access denied"


class DependencyError(AppError):
    status_code = 422
    code = "DEPENDENCY_NOT_MET"
    message = "Stage dependency not satisfied"


class PipelineError(AppError):
    status_code = 500
    code = "PIPELINE_ERROR"
    message = "Pipeline execution failed"


# ── FastAPI 全局异常处理器 ──

async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """处理所有 AppError 子类 — 业务异常用 WARNING 级别记录。"""
    logger.warning(
        "AppError: %s %s → %d [%s] %s",
        request.method, request.url.path,
        exc.status_code, exc.code, exc.message,
    )
    return exc.to_response()


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底：记录完整 traceback，返回安全的错误响应。"""
    try:
        method = request.method
        path = request.url.path
    except Exception:
        method = "UNKNOWN"
        path = "UNKNOWN"

    logger.error(
        "Unhandled exception on %s %s:\n%s",
        method, path,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {},
            }
        },
    )
