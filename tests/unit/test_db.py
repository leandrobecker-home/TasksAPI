"""Unit tests for the database engine factory (RT03)."""

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db import create_db_engine


def test_foreign_keys_are_on_for_a_file_database(tmp_path: Path) -> None:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'tasks.db'}")

    with engine.connect() as connection:
        enabled = connection.execute(text("PRAGMA foreign_keys")).scalar_one()

    engine.dispose()
    assert enabled == 1


def test_foreign_keys_are_on_for_every_connection(tmp_path: Path) -> None:
    """The pragma is per connection, so it must be set on each new one."""
    engine = create_db_engine(f"sqlite:///{tmp_path / 'tasks.db'}")

    with engine.connect() as first, engine.connect() as second:
        first_value = first.execute(text("PRAGMA foreign_keys")).scalar_one()
        second_value = second.execute(text("PRAGMA foreign_keys")).scalar_one()

    engine.dispose()
    assert (first_value, second_value) == (1, 1)


def test_foreign_key_violation_is_rejected_by_the_database(tmp_path: Path) -> None:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'tasks.db'}")

    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE parent (id INTEGER PRIMARY KEY)"))
        connection.execute(
            text(
                "CREATE TABLE child (id INTEGER PRIMARY KEY, "
                "parent_id INTEGER NOT NULL REFERENCES parent(id))"
            )
        )

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("INSERT INTO child (parent_id) VALUES (999)"))

    engine.dispose()


@pytest.mark.parametrize("url", ["sqlite://", "sqlite:///:memory:"])
def test_in_memory_database_is_shared_by_all_connections(url: str) -> None:
    engine = create_db_engine(url)

    with engine.begin() as writer:
        writer.execute(text("CREATE TABLE shared (id INTEGER PRIMARY KEY)"))

    with engine.connect() as reader:
        found = reader.execute(
            text("SELECT name FROM sqlite_master WHERE name = 'shared'")
        ).scalar_one()

    engine.dispose()
    assert found == "shared"


def test_in_memory_databases_are_independent_from_each_other() -> None:
    first = create_db_engine("sqlite://")
    second = create_db_engine("sqlite://")

    with first.begin() as connection:
        connection.execute(text("CREATE TABLE only_in_first (id INTEGER)"))

    with second.connect() as connection:
        tables = connection.execute(
            text("SELECT COUNT(*) FROM sqlite_master WHERE name = 'only_in_first'")
        ).scalar_one()

    first.dispose()
    second.dispose()
    assert tables == 0
