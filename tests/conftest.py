"""Shared pytest fixtures: isolated database and HTTP client (RT15).

Every test gets its own in-memory SQLite database and its own application
instance, so tests never depend on each other or on execution order.
"""

from collections.abc import Iterator
from sqlite3 import Connection as SQLiteConnection

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event
from sqlalchemy.pool import ConnectionPoolEntry, StaticPool
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture
def engine() -> Iterator[Engine]:
    """Create a brand-new in-memory SQLite database for a single test.

    A static pool keeps one shared connection, so every session (including the
    ones opened from the TestClient worker thread) sees the same database.
    Foreign keys are enforced, as SQLite leaves them off by default.
    """
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(test_engine, "connect")
    def _enable_foreign_keys(
        dbapi_connection: SQLiteConnection, _record: ConnectionPoolEntry
    ) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SQLModel.metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """Provide a database session bound to the test's own database."""
    with Session(engine) as db_session:
        yield db_session


@pytest.fixture
def app() -> FastAPI:
    """Provide a fresh application instance for a single test.

    This is a bare FastAPI app until the application factory exists (stage 5),
    at which point it becomes ``create_app`` wired to the test database.
    """
    return FastAPI()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """Provide an HTTP client that calls the application in-process."""
    with TestClient(app) as test_client:
        yield test_client
