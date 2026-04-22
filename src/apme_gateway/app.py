"""FastAPI application factory for the gateway."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from apme_gateway._galaxy_proxy_sync import schedule_push
from apme_gateway.api.feedback import router as feedback_router
from apme_gateway.api.operation_router import operation_router
from apme_gateway.api.router import router
from apme_gateway.config import load_config
from apme_gateway.operation_registry import get_operation_registry

_log = logging.getLogger(__name__)

_BACKSTAGE_USER_HEADER = "X-Backstage-User"


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:  # noqa: ARG001
    """Gateway startup/shutdown lifecycle.

    On startup, schedule a background push of Galaxy server configs from
    the DB to the Galaxy Proxy and start the operation registry reaper.
    On shutdown, clean up in-flight operations.

    Args:
        app: The FastAPI application instance (unused, required by lifespan protocol).

    Yields:
        None: Control to the application.
    """
    schedule_push()
    get_operation_registry().start_reaper()
    yield
    await get_operation_registry().shutdown()


def create_app() -> FastAPI:
    """Build the FastAPI application with all routers registered.

    Returns:
        Configured FastAPI instance.
    """
    cfg = load_config()
    app = FastAPI(
        title="APME Gateway",
        description="Reporting persistence and read-only REST API (ADR-020 / ADR-029)",
        version="0.1.0",
        lifespan=_lifespan,
    )

    if cfg.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cfg.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")  # type: ignore[untyped-decorator]
    async def _log_backstage_user(  # noqa: DOC101,DOC103,DOC107,DOC201
        request: Request,
        call_next: object,
    ) -> object:
        backstage_user = request.headers.get(_BACKSTAGE_USER_HEADER)
        if backstage_user:
            _log.info("backstage_user=%s method=%s path=%s", backstage_user, request.method, request.url.path)
        return await call_next(request)  # type: ignore[operator]

    app.include_router(router)
    app.include_router(feedback_router)
    app.include_router(operation_router)
    return app
