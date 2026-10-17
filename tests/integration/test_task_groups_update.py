"""Integration tests for PATCH /api/v1/task-groups/{id} (RF04)."""

from datetime import datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from tests.factories import create_task_group

URL = "/api/v1/task-groups"


def patch(client: TestClient, group_id: Any, payload: Any) -> Any:
    return client.patch(f"{URL}/{group_id}", json=payload)


def moment(text: str) -> datetime:
    return datetime.fromisoformat(text)


# --- partial updates ----------------------------------------------------------------


def test_patch_changes_only_the_name(client: TestClient, session: Session) -> None:
    group = create_task_group(session, name="Work", description="original")

    response = patch(client, group.id, {"name": "Office"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json()["name"] == "Office"
    assert response.json()["description"] == "original"
    assert response.json()["id"] == str(group.id)


def test_patch_changes_only_the_description(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session, name="Work", description="original")

    body = patch(client, group.id, {"description": "changed"}).json()

    assert (body["name"], body["description"]) == ("Work", "changed")


def test_patch_changes_both_fields(client: TestClient, session: Session) -> None:
    group = create_task_group(session, name="Work", description="original")

    body = patch(client, group.id, {"name": "Office", "description": "new"}).json()

    assert (body["name"], body["description"]) == ("Office", "new")


def test_patch_with_null_clears_the_description(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session, name="Work", description="original")

    body = patch(client, group.id, {"description": None}).json()

    assert body["description"] is None
    assert body["name"] == "Work"


def test_patch_strips_surrounding_spaces_from_the_name(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session, name="Work")

    assert patch(client, group.id, {"name": "  Office  "}).json()["name"] == "Office"


def test_patch_is_persisted(client: TestClient, session: Session) -> None:
    group = create_task_group(session, name="Work")

    patch(client, group.id, {"name": "Office"})

    assert client.get(f"{URL}/{group.id}").json()["name"] == "Office"
    session.refresh(group)
    assert group.normalized_name == "office"


def test_a_renamed_group_is_listed_under_its_new_name(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session, name="Work")

    patch(client, group.id, {"name": "Office"})

    names = [item["name"] for item in client.get(URL).json()["items"]]
    assert names == ["Office"]
    assert client.get(URL, params={"q": "work"}).json()["total"] == 0


def test_patch_with_an_empty_body_changes_nothing(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session, name="Work", description="original")
    before = client.get(f"{URL}/{group.id}").json()

    response = patch(client, group.id, {})

    assert response.status_code == 200
    assert response.json() == before


# --- timestamps ---------------------------------------------------------------------


def test_patch_moves_updated_at_forward_and_keeps_created_at(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session, name="Work")
    before = client.get(f"{URL}/{group.id}").json()

    after = patch(client, group.id, {"name": "Office"}).json()

    assert after["created_at"] == before["created_at"]
    assert moment(after["updated_at"]) > moment(before["updated_at"])


# --- uniqueness (RN01) ----------------------------------------------------------------


@pytest.mark.parametrize("taken", ["Work", "work", "WORK", "  Work  "])
def test_renaming_to_another_groups_name_is_409(
    client: TestClient, session: Session, taken: str
) -> None:
    create_task_group(session, name="Work")
    home = create_task_group(session, name="Home")

    response = patch(client, home.id, {"name": taken})

    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Conflict"
    assert response.json()["detail"] == "A task group with this name already exists."


def test_renaming_to_another_groups_name_with_accents_is_409(
    client: TestClient, session: Session
) -> None:
    create_task_group(session, name="Ação")
    home = create_task_group(session, name="Home")

    assert patch(client, home.id, {"name": "AÇÃO"}).status_code == 409


def test_a_rejected_rename_keeps_the_old_name(
    client: TestClient, session: Session
) -> None:
    create_task_group(session, name="Work")
    home = create_task_group(session, name="Home")
    patch(client, home.id, {"name": "work"})

    assert client.get(f"{URL}/{home.id}").json()["name"] == "Home"


@pytest.mark.parametrize("same", ["Work", "WORK", "work", "  Work "])
def test_keeping_the_own_name_is_not_a_conflict(
    client: TestClient, session: Session, same: str
) -> None:
    group = create_task_group(session, name="Work")

    response = patch(client, group.id, {"name": same})

    assert response.status_code == 200
    assert response.json()["name"] == same.strip()


def test_a_name_freed_by_a_rename_can_be_taken(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session, name="Old")
    patch(client, group.id, {"name": "New"})

    assert client.post(URL, json={"name": "Old"}).status_code == 201


# --- validation (422) -----------------------------------------------------------------


@pytest.mark.parametrize("name", ["", "   ", None, 123, ["x"], "n" * 101])
def test_invalid_name_is_422(client: TestClient, session: Session, name: Any) -> None:
    group = create_task_group(session, name="Work")

    response = patch(client, group.id, {"name": name})

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"].startswith("name: ")


def test_description_over_500_characters_is_422(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session, name="Work")

    response = patch(client, group.id, {"description": "d" * 501})

    assert response.status_code == 422
    assert response.json()["detail"].startswith("description: ")


def test_the_maximum_lengths_are_accepted(client: TestClient, session: Session) -> None:
    group = create_task_group(session, name="Work")

    response = patch(client, group.id, {"name": "n" * 100, "description": "d" * 500})

    assert response.status_code == 200


def test_unknown_field_is_422(client: TestClient, session: Session) -> None:
    group = create_task_group(session, name="Work")

    response = patch(client, group.id, {"color": "red"})

    assert response.status_code == 422
    assert response.json()["detail"].startswith("color: ")


def test_generated_fields_sent_by_the_client_are_ignored(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session, name="Work")

    body = patch(
        client,
        group.id,
        {"name": "Office", "id": str(uuid4()), "created_at": "2000-01-01T00:00:00Z"},
    ).json()

    assert body["id"] == str(group.id)
    assert body["created_at"] != "2000-01-01T00:00:00Z"
    assert body["name"] == "Office"


def test_body_that_is_not_an_object_is_422(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session, name="Work")

    assert patch(client, group.id, ["name"]).status_code == 422


def test_malformed_json_is_400(client: TestClient, session: Session) -> None:
    group = create_task_group(session, name="Work")

    response = client.patch(
        f"{URL}/{group.id}",
        content='{"name": ',
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400


# --- not found and bad ids ------------------------------------------------------------


def test_unknown_id_is_404(client: TestClient) -> None:
    missing = uuid4()

    response = patch(client, missing, {"name": "Anything"})

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"] == f"Task group {missing} not found."


def test_id_that_is_not_a_uuid_is_422(client: TestClient) -> None:
    response = patch(client, "not-a-uuid", {"name": "Anything"})

    assert response.status_code == 422
    assert response.json()["detail"].startswith("group_id: ")


def test_an_invalid_body_wins_over_an_unknown_id(client: TestClient) -> None:
    assert patch(client, uuid4(), {"name": ""}).status_code == 422


# --- PUT is out of scope --------------------------------------------------------------


def test_put_is_not_available_on_a_group(client: TestClient, session: Session) -> None:
    group = create_task_group(session, name="Work")

    response = client.put(f"{URL}/{group.id}", json={"name": "Office"})

    assert response.status_code == 405
    assert "PATCH" in response.headers["allow"]
    session.refresh(group)
    assert group.name == "Work"


# --- documentation --------------------------------------------------------------------


def test_the_endpoint_is_documented(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"][f"{URL}/{{group_id}}"]["patch"]

    assert operation["summary"] == "Update a task group"
    assert operation["tags"] == ["task-groups"]
