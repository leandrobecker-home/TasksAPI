"""Database engine creation (RT03).

SQLite leaves foreign key enforcement off by default, so every connection
turns it on explicitly. Everything specific to SQLite lives here, which keeps
a future move to PostgreSQL out of the routes and services.
"""

from sqlite3 import Connection as SQLiteConnection
from typing import Any

from sqlalchemy import Engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.pool import ConnectionPoolEntry, StaticPool
from sqlmodel import SQLModel, create_engine

from app import models as _models  # noqa: F401  (registers every table on the metadata)

_IN_MEMORY_DATABASES = (None, "", ":memory:")


def _enable_sqlite_foreign_keys(
    dbapi_connection: SQLiteConnection, _record: ConnectionPoolEntry
) -> None:
    """Turn on foreign key enforcement for a freshly opened SQLite connection."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def create_db_engine(database_url: str) -> Engine:
    """Create the engine for ``database_url``.

    For SQLite, connections may be used from any thread (FastAPI runs sync
    endpoints in a worker pool), foreign keys are enforced on every connection,
    and an in-memory database is pinned to a single shared connection so that
    all sessions see the same data.
    """
    url = make_url(database_url)
    is_sqlite = url.get_backend_name() == "sqlite"

    options: dict[str, Any] = {}
    if is_sqlite:
        options["connect_args"] = {"check_same_thread": False}
        if url.database in _IN_MEMORY_DATABASES:
            options["poolclass"] = StaticPool

    engine = create_engine(url, **options)
    if is_sqlite:
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def create_tables(engine: Engine) -> None:
    """Create every table that does not exist yet.

    This is how the schema is built in release R1; versioned migrations with
    Alembic replace it in R2. Existing tables and their data are left alone.
    """
    SQLModel.metadata.create_all(engine)
