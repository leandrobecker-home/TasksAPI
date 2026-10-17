"""Sanity tests for the shared fixtures (RT15)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session


@pytest.mark.parametrize("attempt", [1, 2, 3])
def test_database_is_new_for_each_test(session: Session, attempt: int) -> None:
    """CREATE TABLE fails if a previous test left its table behind."""
    connection = session.connection()
    connection.execute(text("CREATE TABLE probe (id INTEGER PRIMARY KEY)"))
    connection.execute(text("INSERT INTO probe DEFAULT VALUES"))

    count = connection.execute(text("SELECT COUNT(*) FROM probe")).scalar_one()

    assert count == 1


def test_sessions_share_the_same_database(engine: Engine, session: Session) -> None:
    session.connection().execute(text("CREATE TABLE shared (id INTEGER PRIMARY KEY)"))
    session.commit()

    with Session(engine) as other_session:
        tables = other_session.connection().execute(
            text("SELECT name FROM sqlite_master WHERE name = 'shared'")
        )

        assert tables.scalar_one() == "shared"


def test_foreign_keys_are_enforced(session: Session) -> None:
    connection = session.connection()
    connection.execute(text("CREATE TABLE parent (id INTEGER PRIMARY KEY)"))
    connection.execute(
        text(
            "CREATE TABLE child (id INTEGER PRIMARY KEY, "
            "parent_id INTEGER NOT NULL REFERENCES parent(id))"
        )
    )

    with pytest.raises(IntegrityError):
        connection.execute(text("INSERT INTO child (parent_id) VALUES (999)"))


def test_client_calls_the_application(app: FastAPI, client: TestClient) -> None:
    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    response = client.get("/ping")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_each_test_gets_a_new_application(app: FastAPI) -> None:
    """A route registered by another test must never be visible here."""
    assert not [route for route in app.routes if getattr(route, "path", "") == "/ping"]
