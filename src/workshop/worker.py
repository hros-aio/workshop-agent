"""Arq worker entrypoint.

Run with: `arq workshop.worker.WorkerSettings`
The worker processes Analysis Runs off the HTTP request path.
"""

from __future__ import annotations

from typing import Any, ClassVar

from arq.connections import RedisSettings

from workshop.analysis.jobs import process_analysis_run
from workshop.logging import configure_logging
from workshop.settings import get_settings


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging()


async def shutdown(ctx: dict[str, Any]) -> None:
    return None


class WorkerSettings:
    functions: ClassVar[list[Any]] = [process_analysis_run]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    job_timeout = get_settings().analysis_timeout_seconds
