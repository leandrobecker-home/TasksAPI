"""Integration tests for DELETE /api/v1/tasks/{id} (RF13)."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import Task, TaskGroup
from tests.factories import create_task, create_task_group

URL = "/api/v1/tasks"
GROUPS = "/api/v1/task-groups"


def test_delete_returns_204_with_no_body(client: TestClient, session: Session) -> None:
    task = create_task(session)

    response = client.delete(f"{URL}/{task.id}")

    assert response.status_code == 204
    assert response.content == b""


def test_a_deleted_task_is_gone(client: TestClient, session: Session) -> None:
    task = create_task(session)
    task_id = task.id

    client.delete(f"{URL}/{task_id}")

    assert client.get(f"{URL}/{task_id}").status_code == 404


def test_deletion_is_physical(client: TestClient, session: Session) -> None:
    task = create_task(session)
    task_id = task.id

    client.delete(f"{URL}/{task_id}")

    session.expire_all()
    assert session.get(Task, task_id) is None


def test_a_deleted_task_disappears_from_its_group_listing(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session)
    doomed = create_task(session, group, title="Doomed")
    create_task(session, group, title="Kept")

    client.delete(f"{URL}/{doomed.id}")

    body = client.get(f"{GROUPS}/{group.id}/tasks").json()
    assert [item["title"] for item in body["items"]] == ["Kept"]
    assert body["total"] == 1


def test_delete_removes_only_the_requested_task(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session)
    doomed = create_task(session, group)
    kept = create_task(session, group)

    client.delete(f"{URL}/{doomed.id}")

    assert client.get(f"{URL}/{kept.id}").status_code == 200


def test_delete_does_not_touch_the_group(client: TestClient, session: Session) -> None:
    group = create_task_group(session, name="Work")
    task = create_task(session, group)
    group_id = group.id

    client.delete(f"{URL}/{task.id}")

    session.expire_all()
    assert session.get(TaskGroup, group_id) is not None
    assert client.get(f"{GROUPS}/{group_id}").status_code == 200


def test_a_group_can_be_deleted_after_its_last_task_is(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session, name="Work")
    first = create_task(session, group)
    second = create_task(session, group)
    assert client.delete(f"{GROUPS}/{group.id}").status_code == 409

    client.delete(f"{URL}/{first.id}")
    assert client.delete(f"{GROUPS}/{group.id}").status_code == 409
    client.delete(f"{URL}/{second.id}")

    assert client.delete(f"{GROUPS}/{group.id}").status_code == 204


def test_deleting_twice_is_404_the_second_time(
    client: TestClient, session: Session
) -> None:
    task = create_task(session)

    first = client.delete(f"{URL}/{task.id}")
    second = client.delete(f"{URL}/{task.id}")

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
        "detail": f"Task {missing} not found.",
        "instance": f"{URL}/{missing}",
    }


@pytest.mark.parametrize("bad_id", ["not-a-uuid", "123"])
def test_id_that_is_not_a_uuid_is_422(client: TestClient, bad_id: str) -> None:
    response = client.delete(f"{URL}/{bad_id}")

    assert response.status_code == 422
    assert response.json()["detail"].startswith("task_id: ")


def test_a_failed_delete_does_not_remove_anything(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session)
    create_task(session, group)

    client.delete(f"{URL}/{uuid4()}")

    assert client.get(f"{GROUPS}/{group.id}/tasks").json()["total"] == 1


def test_a_group_id_is_not_a_task_id(client: TestClient, session: Session) -> None:
    group = create_task_group(session)

    assert client.delete(f"{URL}/{group.id}").status_code == 404
    assert client.get(f"{GROUPS}/{group.id}").status_code == 200


def test_a_single_task_advertises_all_its_methods(
    client: TestClient, session: Session
) -> None:
    task = create_task(session)

    response = client.post(f"{URL}/{task.id}", json={"title": "x"})

    assert response.status_code == 405
    assert response.headers["allow"] == "DELETE, GET, PATCH"


def test_the_endpoint_is_documented(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"][f"{URL}/{{task_id}}"]["delete"]

    assert operation["summary"] == "Delete a task"
    assert operation["tags"] == ["tasks"]
    assert "204" in operation["responses"]
