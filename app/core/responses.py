"""Uniform response envelopes.

Every response follows the shape used across the reference APIs:

    {"status": 200, "message": "...", "data": {...}}

and errors:

    {"status": 400, "message": "...", "errors": [...]}
"""
from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse


def ok(data: Any = None, message: str = "Success", status: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status, content={"status": status, "message": message, "data": data})


def accepted(data: Any = None, message: str = "Process initiated") -> JSONResponse:
    return JSONResponse(status_code=202, content={"status": 202, "message": message, "data": data})


def error(message: str, status: int = 400, errors: list[str] | None = None) -> JSONResponse:
    body: dict[str, Any] = {"status": status, "message": message}
    if errors:
        body["errors"] = errors
    return JSONResponse(status_code=status, content=body)
