"""FastAPI application factory (RT02)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import Engine

from app.config import Settings, get_settings
from app.db import create_db_engine
from app.routes import health

API_TITLE = "Tasks API"
API_VERSION = "0.1.0"
API_DESCRIPTION = "REST API for managing tasks grouped into task groups."


def create_app(
    settings: Settings | None = None, engine: Engine | None = None
) -> FastAPI:
    """Build the application.

    ``settings`` and ``engine`` are injectable so tests can supply their own;
    by default the settings come from the environment and the engine from
    ``settings.database_url``. An engine created here is disposed on shutdown,
    while an injected one is left to its owner.
    """
    app_settings = settings if settings is not None else get_settings()
    owns_engine = engine is None
    db_engine = (
        engine if engine is not None else create_db_engine(app_settings.database_url)
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        if owns_engine:
            db_engine.dispose()

    app = FastAPI(
        title=API_TITLE,
        version=API_VERSION,
        description=API_DESCRIPTION,
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.engine = db_engine
    app.include_router(health.router)
    return app
