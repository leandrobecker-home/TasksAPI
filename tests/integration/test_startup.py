"""Integration tests for the database preparation done at startup (RT03)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, inspect
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, select

from app.config import Settings
from app.db import create_db_engine
from app.main import create_app
from app.models import TaskGroup
from tests.factories import create_task_group


@pytest.fixture
def file_database(tmp_path: Path) -> Iterator[str]:
    yield f"sqlite:///{tmp_path / 'tasks.db'}"


def settings_for(database_url: str) -> Settings:
    return Settings(_env_file=None, database_url=database_url)


def test_starting_the_app_creates_the_tables(file_database: str) -> None:
    engine = create_db_engine(file_database)
    app = create_app(settings_for(file_database), engine)

    assert inspect(engine).get_table_names() == []
    with TestClient(app):
        tables = inspect(engine).get_table_names()
    engine.dispose()

    assert "task_groups" in tables


def test_the_app_builds_and_prepares_its_own_engine(file_database: str) -> None:
    app = create_app(settings_for(file_database))

    with TestClient(app):
        tables = inspect(app.state.engine).get_table_names()

    assert "task_groups" in tables


def test_restarting_the_app_keeps_the_existing_data(file_database: str) -> None:
    engine = create_db_engine(file_database)
    app = create_app(settings_for(file_database), engine)
    with TestClient(app), Session(engine) as session:
        create_task_group(session, name="Survivor")

    app = create_app(settings_for(file_database), engine)
    with TestClient(app), Session(engine) as session:
        names = [group.name for group in session.exec(select(TaskGroup))]
    engine.dispose()

    assert names == ["Survivor"]


def test_a_missing_directory_stops_the_app_from_starting(tmp_path: Path) -> None:
    """Failing fast beats serving errors on every request."""
    unreachable = f"sqlite:///{tmp_path / 'missing-directory' / 'tasks.db'}"
    engine = create_db_engine(unreachable)
    app = create_app(settings_for(unreachable), engine)

    with pytest.raises(OperationalError), TestClient(app):
        pass

    engine.dispose()


def test_tables_exist_for_the_shared_test_database(engine: Engine) -> None:
    assert {"task_groups"} <= set(inspect(engine).get_table_names())
