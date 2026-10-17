"""Domain exceptions mapped to RFC 9457 problem+json responses."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class WorkshopError(Exception):
    """Base class for all domain errors."""

    status_code = 400
    title = "Workshop error"

    def __init__(self, detail: str, *, errors: list[dict[str, str]] | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.errors = errors


class NotFoundError(WorkshopError):
    status_code = 404
    title = "Not found"


class ForbiddenError(WorkshopError):
    status_code = 403
    title = "Forbidden"


class ConflictError(WorkshopError):
    status_code = 409
    title = "Conflict"


class DomainValidationError(WorkshopError):
    status_code = 422
    title = "Validation failed"


class InvalidTransitionError(ConflictError):
    def __init__(self, from_status: str, to_status: str) -> None:
        super().__init__(f"Transition from '{from_status}' to '{to_status}' is not allowed")


class AIFailureError(WorkshopError):
    status_code = 502
    title = "AI provider failure"


def _problem(
    *,
    status: int,
    title: str,
    detail: str,
    instance: str,
    errors: list[dict[str, str]] | None = None,
) -> JSONResponse:
    body: dict[str, object] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": instance,
    }
    if errors is not None:
        body["errors"] = errors
    return JSONResponse(status_code=status, content=body, media_type="application/problem+json")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(WorkshopError)
    async def _workshop_error(request: Request, exc: WorkshopError) -> JSONResponse:
        return _problem(
            status=exc.status_code,
            title=exc.title,
            detail=exc.detail,
            instance=str(request.url.path),
            errors=exc.errors,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {
                "field": ".".join(str(part) for part in err.get("loc", ())),
                "message": err.get("msg", ""),
            }
            for err in exc.errors()
        ]
        return _problem(
            status=422,
            title="Validation failed",
            detail="Request body failed validation",
            instance=str(request.url.path),
            errors=errors,
        )
