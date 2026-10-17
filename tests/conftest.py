"""Shared pytest fixtures: isolated database and HTTP client (RT15).

Every test gets its own in-memory SQLite database and its own application
instance, so tests never depend on each other or on execution order.
"""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlmodel import Session

from app.config import Settings
from app.db import create_db_engine, create_tables
from app.main import create_app


@pytest.fixture
def engine() -> Iterator[Engine]:
    """Create a brand-new in-memory SQLite database for a single test.

    The engine comes from the application's own factory, so tests exercise the
    same setup as production: one shared connection (every session, including
    the ones opened from the TestClient worker thread, sees the same database)
    and foreign keys enforced.
    """
    test_engine = create_db_engine("sqlite://")
    create_tables(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """Provide a database session bound to the test's own database."""
    with Session(engine) as db_session:
        yield db_session


@pytest.fixture
def app(engine: Engine) -> FastAPI:
    """Provide a fresh application instance wired to the test database."""
    settings = Settings(_env_file=None, database_url="sqlite://")
    return create_app(settings, engine)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """Provide an HTTP client that calls the application in-process."""
    with TestClient(app) as test_client:
        yield test_client
