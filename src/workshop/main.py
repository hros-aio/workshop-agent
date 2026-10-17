"""FastAPI application factory.

The service is mounted under `/workshop-api` by the ingress/NestJS proxy; the
app itself serves routes at the root so the OpenAPI paths match the contract
prefix only at the gateway. Tests use the app directly.
"""

from __future__ import annotations

from fastapi import FastAPI

from workshop.analysis.router import router as analysis_router
from workshop.common.errors import register_exception_handlers
from workshop.document.router import router as document_router
from workshop.export.router import router as export_router
from workshop.logging import configure_logging
from workshop.project.router import router as project_router
from workshop.proposal.router import router as proposal_router
from workshop.review.router import router as review_router
from workshop.settings import get_settings
from workshop.validation.router import router as validation_router


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="Workshop Module API",
        version="1.0.0",
        description="AI-assisted HRMS implementation discovery workflow.",
        root_path="",
    )
    register_exception_handlers(app)

    @app.get("/health", tags=["Health"])
    def health() -> dict[str, str]:
        settings = get_settings()
        return {"status": "ok", "version": app.version, "schema": settings.db_schema}

    app.include_router(project_router)
    app.include_router(document_router)
    app.include_router(analysis_router)
    app.include_router(proposal_router)
    app.include_router(review_router)
    app.include_router(validation_router)
    app.include_router(export_router)
    return app


app = create_app()
