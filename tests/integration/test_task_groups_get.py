"""Integration tests for GET /api/v1/task-groups/{id} (RF03)."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from tests.factories import create_task_group

URL = "/api/v1/task-groups"


def test_get_returns_the_group(client: TestClient, session: Session) -> None:
    group = create_task_group(session, name="Work", description="Job stuff")

    response = client.get(f"{URL}/{group.id}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {
        "id": str(group.id),
        "name": "Work",
        "description": "Job stuff",
        "created_at": response.json()["created_at"],
        "updated_at": response.json()["updated_at"],
    }
    assert response.json()["created_at"].endswith("Z")


def test_get_returns_a_null_description_when_there_is_none(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session, name="Work")

    assert client.get(f"{URL}/{group.id}").json()["description"] is None


def test_get_never_exposes_the_internal_normalized_name(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session, name="Work")

    assert "normalized_name" not in client.get(f"{URL}/{group.id}").json()


def test_get_returns_only_the_requested_group(
    client: TestClient, session: Session
) -> None:
    create_task_group(session, name="Other")
    wanted = create_task_group(session, name="Wanted")

    assert client.get(f"{URL}/{wanted.id}").json()["name"] == "Wanted"


def test_get_accepts_an_uppercase_uuid(client: TestClient, session: Session) -> None:
    group = create_task_group(session, name="Work")

    response = client.get(f"{URL}/{str(group.id).upper()}")

    assert response.status_code == 200
    assert response.json()["id"] == str(group.id)


def test_the_location_returned_by_post_leads_to_the_group(client: TestClient) -> None:
    created = client.post(URL, json={"name": "Work"})

    response = client.get(created.headers["location"])

    assert response.status_code == 200
    assert response.json() == created.json()


def test_unknown_id_is_404(client: TestClient) -> None:
    missing = uuid4()

    response = client.get(f"{URL}/{missing}")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Not Found",
        "status": 404,
        "detail": f"Task group {missing} not found.",
        "instance": f"{URL}/{missing}",
    }


@pytest.mark.parametrize("bad_id", ["not-a-uuid", "123", "xyz-xyz", "1234-5678"])
def test_id_that_is_not_a_uuid_is_422(client: TestClient, bad_id: str) -> None:
    response = client.get(f"{URL}/{bad_id}")

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"].startswith("group_id: ")


def test_post_is_not_allowed_on_a_single_group(client: TestClient) -> None:
    response = client.post(f"{URL}/{uuid4()}", json={"name": "x"})

    assert response.status_code == 405
    assert "GET" in response.headers["allow"]


def test_the_endpoint_is_documented(client: TestClient) -> None:
    operation = client.get("/openapi.json").json()["paths"][f"{URL}/{{group_id}}"][
        "get"
    ]

    assert operation["summary"] == "Get a task group"
    assert operation["tags"] == ["task-groups"]
    assert operation["parameters"][0]["schema"]["format"] == "uuid"
