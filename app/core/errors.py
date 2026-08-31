"""Domain exceptions and their global handlers."""
from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.responses import error


class AppError(Exception):
    """Base class for expected, handled application errors."""

    status = 400
    message = "Bad request"

    def __init__(self, message: str | None = None, status: int | None = None):
        if message:
            self.message = message
        if status:
            self.status = status
        super().__init__(self.message)


class NotFound(AppError):
    status = 404
    message = "Resource not found"


class Unauthorized(AppError):
    status = 401
    message = "Authentication failed or token missing"


class Forbidden(AppError):
    status = 403
    message = "Access to the resource is denied"


class Conflict(AppError):
    status = 409
    message = "Request already in progress"


class ProviderUnavailable(AppError):
    status = 503
    message = "Upstream provider is currently unavailable"


def register_exception_handlers(app) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return error(exc.message, exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [f"{'.'.join(str(p) for p in e['loc'][1:])}: {e['msg']}" for e in exc.errors()]
        return error("Validation failed for one or more arguments", 400, details)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return error(str(exc.detail), exc.status_code)
