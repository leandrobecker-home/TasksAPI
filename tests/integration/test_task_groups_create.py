"""Integration tests for POST /api/v1/task-groups (RF01)."""

import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlmodel import Session, select

from app.config import Settings
from app.db import create_db_engine
from app.main import create_app
from app.models import TaskGroup
from tests.factories import create_task_group

URL = "/api/v1/task-groups"


def post(client: TestClient, payload: dict[str, Any]) -> Any:
    return client.post(URL, json=payload)


def group_count(session: Session) -> int:
    return len(session.exec(select(TaskGroup)).all())


# --- success ---------------------------------------------------------------------


def test_create_returns_201_with_the_new_group(client: TestClient) -> None:
    response = post(client, {"name": "Work", "description": "Job stuff"})

    body = response.json()
    assert response.status_code == 201
    assert response.headers["content-type"] == "application/json"
    assert set(body) == {"id", "name", "description", "created_at", "updated_at"}
    assert (body["name"], body["description"]) == ("Work", "Job stuff")
    assert UUID(body["id"])


def test_create_sets_the_location_header_to_the_new_resource(
    client: TestClient,
) -> None:
    response = post(client, {"name": "Work"})

    assert (
        response.headers["location"] == f"/api/v1/task-groups/{response.json()['id']}"
    )


def test_create_without_a_description_returns_null(client: TestClient) -> None:
    assert post(client, {"name": "Work"}).json()["description"] is None


def test_generated_fields_are_set_by_the_server(client: TestClient) -> None:
    body = post(client, {"name": "Work"}).json()

    assert body["created_at"] == body["updated_at"]
    assert body["created_at"].endswith("Z")


def test_create_persists_the_group(client: TestClient, session: Session) -> None:
    group_id = UUID(post(client, {"name": "  Work  "}).json()["id"])

    saved = session.get(TaskGroup, group_id)

    assert saved is not None
    assert (saved.name, saved.normalized_name) == ("Work", "work")


def test_create_strips_surrounding_spaces_from_the_name(client: TestClient) -> None:
    assert post(client, {"name": "   Work   "}).json()["name"] == "Work"


def test_create_accepts_the_maximum_lengths(client: TestClient) -> None:
    response = post(client, {"name": "n" * 100, "description": "d" * 500})

    assert response.status_code == 201


def test_create_handles_non_ascii_names(client: TestClient) -> None:
    response = post(client, {"name": "Ação rápida 日本語"})

    assert response.status_code == 201
    assert response.json()["name"] == "Ação rápida 日本語"


def test_generated_fields_sent_by_the_client_are_ignored(client: TestClient) -> None:
    sent_id = "00000000-0000-0000-0000-000000000001"

    body = post(
        client,
        {
            "name": "Work",
            "id": sent_id,
            "created_at": "2000-01-01T00:00:00Z",
            "updated_at": "2000-01-01T00:00:00Z",
        },
    ).json()

    assert body["id"] != sent_id
    assert body["created_at"] != "2000-01-01T00:00:00Z"
    assert body["updated_at"] != "2000-01-01T00:00:00Z"


# --- validation (422) -------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"description": "no name"},
        {"name": ""},
        {"name": "   "},
        {"name": None},
        {"name": 123},
        {"name": "n" * 101},
    ],
)
def test_invalid_name_is_422(
    client: TestClient, session: Session, payload: Any
) -> None:
    response = post(client, payload)

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"].startswith("name: ")
    assert group_count(session) == 0


def test_description_over_500_characters_is_422(client: TestClient) -> None:
    response = post(client, {"name": "Work", "description": "d" * 501})

    assert response.status_code == 422
    assert response.json()["detail"].startswith("description: ")


@pytest.mark.parametrize("field", ["color", "normalized_name", "total_tasks"])
def test_unknown_field_is_422(client: TestClient, field: str) -> None:
    response = post(client, {"name": "Work", field: "x"})

    assert response.status_code == 422
    assert response.json()["detail"].startswith(f"{field}: ")


def test_body_that_is_not_an_object_is_422(client: TestClient) -> None:
    assert client.post(URL, json=["Work"]).status_code == 422


def test_missing_body_is_422(client: TestClient) -> None:
    assert client.post(URL).status_code == 422


def test_malformed_json_is_400(client: TestClient) -> None:
    response = client.post(
        URL, content='{"name": ', headers={"content-type": "application/json"}
    )

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"


# --- uniqueness (RN01) --------------------------------------------------------------


@pytest.mark.parametrize("duplicate", ["Work", "work", "WORK", "  Work  "])
def test_duplicate_name_is_409(
    client: TestClient, session: Session, duplicate: str
) -> None:
    create_task_group(session, name="Work")

    response = post(client, {"name": duplicate})

    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Conflict",
        "status": 409,
        "detail": "A task group with this name already exists.",
        "instance": URL,
    }


def test_duplicate_name_with_accents_is_409(
    client: TestClient, session: Session
) -> None:
    create_task_group(session, name="Ação")

    assert post(client, {"name": "AÇÃO"}).status_code == 409


def test_a_rejected_duplicate_does_not_create_a_second_group(
    client: TestClient, session: Session
) -> None:
    create_task_group(session, name="Work")
    post(client, {"name": "work"})

    assert group_count(session) == 1


def test_the_api_keeps_working_after_a_conflict(client: TestClient) -> None:
    post(client, {"name": "Work"})
    post(client, {"name": "WORK"})

    assert post(client, {"name": "Home"}).status_code == 201


def test_names_that_differ_beyond_case_are_both_accepted(client: TestClient) -> None:
    assert post(client, {"name": "Work"}).status_code == 201
    assert post(client, {"name": "Work 2"}).status_code == 201


# --- concurrency ------------------------------------------------------------------


@pytest.fixture
def file_app(tmp_path: Path) -> Iterator[tuple[Any, Engine]]:
    """An application on a file database, whose connections are independent."""
    url = f"sqlite:///{tmp_path / 'concurrent.db'}"
    engine = create_db_engine(url)
    app = create_app(Settings(_env_file=None, database_url=url), engine)
    with TestClient(app):  # runs startup, which creates the tables
        pass
    yield app, engine
    engine.dispose()


def test_simultaneous_creations_of_the_same_name_create_exactly_one(
    file_app: tuple[Any, Engine],
) -> None:
    app, engine = file_app
    attempts = 8
    barrier = threading.Barrier(attempts)

    def create(number: int) -> int:
        barrier.wait(timeout=10)
        status: int = TestClient(app).post(URL, json={"name": "Same Name"}).status_code
        return status

    with ThreadPoolExecutor(max_workers=attempts) as pool:
        statuses = list(pool.map(create, range(attempts)))

    assert sorted(statuses) == [201] + [409] * (attempts - 1)
    with Session(engine) as session:
        assert group_count(session) == 1


# --- documentation ----------------------------------------------------------------


def test_the_endpoint_is_documented(client: TestClient) -> None:
    operation = client.get("/openapi.json").json()["paths"][URL]["post"]

    assert "201" in operation["responses"]
    assert operation["tags"] == ["task-groups"]
    assert operation["summary"] == "Create a task group"
