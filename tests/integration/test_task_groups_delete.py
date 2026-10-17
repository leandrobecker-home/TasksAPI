"""Integration tests for DELETE /api/v1/task-groups/{id} (RF05, RN03)."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import Task, TaskGroup
from tests.factories import create_task, create_task_group

URL = "/api/v1/task-groups"


def test_delete_returns_204_with_no_body(client: TestClient, session: Session) -> None:
    group = create_task_group(session, name="Work")

    response = client.delete(f"{URL}/{group.id}")

    assert response.status_code == 204
    assert response.content == b""


def test_a_deleted_group_is_gone(client: TestClient, session: Session) -> None:
    group = create_task_group(session, name="Work")
    group_id = group.id

    client.delete(f"{URL}/{group_id}")

    assert client.get(f"{URL}/{group_id}").status_code == 404
    session.expire_all()
    assert session.get(TaskGroup, group_id) is None


def test_a_deleted_group_disappears_from_the_listing(
    client: TestClient, session: Session
) -> None:
    doomed = create_task_group(session, name="Doomed")
    create_task_group(session, name="Kept")

    client.delete(f"{URL}/{doomed.id}")

    body = client.get(URL).json()
    assert [item["name"] for item in body["items"]] == ["Kept"]
    assert body["total"] == 1


def test_delete_removes_only_the_requested_group(
    client: TestClient, session: Session
) -> None:
    doomed = create_task_group(session, name="Doomed")
    kept = create_task_group(session, name="Kept")

    client.delete(f"{URL}/{doomed.id}")

    assert client.get(f"{URL}/{kept.id}").status_code == 200


def test_the_name_of_a_deleted_group_can_be_used_again(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session, name="Temporary")
    client.delete(f"{URL}/{group.id}")

    assert client.post(URL, json={"name": "temporary"}).status_code == 201


def test_deleting_twice_is_404_the_second_time(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session, name="Work")

    first = client.delete(f"{URL}/{group.id}")
    second = client.delete(f"{URL}/{group.id}")

    assert (first.status_code, second.status_code) == (204, 404)


def test_unknown_id_is_404(client: TestClient) -> None:
    missing = uuid4()

    response = client.delete(f"{URL}/{missing}")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Not Found",
        "status": 404,
        "detail": f"Task group {missing} not found.",
        "instance": f"{URL}/{missing}",
    }


@pytest.mark.parametrize("bad_id", ["not-a-uuid", "123"])
def test_id_that_is_not_a_uuid_is_422(client: TestClient, bad_id: str) -> None:
    response = client.delete(f"{URL}/{bad_id}")

    assert response.status_code == 422
    assert response.json()["detail"].startswith("group_id: ")


def test_a_failed_delete_does_not_remove_anything(
    client: TestClient, session: Session
) -> None:
    create_task_group(session, name="Work")

    client.delete(f"{URL}/{uuid4()}")

    assert client.get(URL).json()["total"] == 1


def test_the_collection_cannot_be_deleted(client: TestClient) -> None:
    response = client.delete(URL)

    assert response.status_code == 405
    assert "POST" in response.headers["allow"]


def test_a_single_group_advertises_all_its_methods(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session, name="Work")

    response = client.put(f"{URL}/{group.id}", json={"name": "x"})

    assert response.status_code == 405
    assert response.headers["allow"] == "DELETE, GET, PATCH"


def test_the_endpoint_is_documented(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"][f"{URL}/{{group_id}}"]["delete"]

    assert operation["summary"] == "Delete a task group"
    assert operation["tags"] == ["task-groups"]
    assert "204" in operation["responses"]


# --- a group with tasks cannot be deleted (RN03) ----------------------------------


def test_a_group_with_a_task_cannot_be_deleted(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session, name="Work")
    create_task(session, group)

    response = client.delete(f"{URL}/{group.id}")

    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Conflict",
        "status": 409,
        "detail": "The task group still has tasks; delete or move them first.",
        "instance": f"{URL}/{group.id}",
    }


def test_a_refused_delete_leaves_the_group_and_its_tasks_in_place(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session, name="Work")
    task = create_task(session, group)
    group_id, task_id = group.id, task.id

    client.delete(f"{URL}/{group_id}")

    session.expire_all()
    assert client.get(f"{URL}/{group_id}").status_code == 200
    assert session.get(Task, task_id) is not None


def test_a_group_can_be_deleted_after_its_tasks_are_removed(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session, name="Work")
    task = create_task(session, group)
    assert client.delete(f"{URL}/{group.id}").status_code == 409

    session.delete(task)
    session.commit()

    assert client.delete(f"{URL}/{group.id}").status_code == 204
    assert client.get(f"{URL}/{group.id}").status_code == 404


def test_tasks_in_another_group_do_not_block_the_delete(
    client: TestClient, session: Session
) -> None:
    empty = create_task_group(session, name="Empty")
    busy = create_task_group(session, name="Busy")
    create_task(session, busy)

    assert client.delete(f"{URL}/{empty.id}").status_code == 204
