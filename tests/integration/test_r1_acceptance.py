"""Acceptance checks for release R1: the contract and the rule of the group."""

from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import Task
from tests.factories import create_task, create_task_group

API = "/api/v1"
GROUP_TASKS = f"{API}/task-groups/{{group_id}}/tasks"

R1_ENDPOINTS = {
    ("GET", "/health"),
    ("POST", f"{API}/task-groups"),
    ("GET", f"{API}/task-groups"),
    ("GET", f"{API}/task-groups/{{group_id}}"),
    ("PATCH", f"{API}/task-groups/{{group_id}}"),
    ("DELETE", f"{API}/task-groups/{{group_id}}"),
    ("POST", GROUP_TASKS),
    ("GET", GROUP_TASKS),
    ("GET", f"{API}/tasks/{{task_id}}"),
    ("PATCH", f"{API}/tasks/{{task_id}}"),
    ("DELETE", f"{API}/tasks/{{task_id}}"),
}

METHODS = {"get", "post", "put", "patch", "delete"}


def documented_endpoints(client: TestClient) -> set[tuple[str, str]]:
    paths: dict[str, dict[str, Any]] = client.get("/openapi.json").json()["paths"]
    return {
        (method.upper(), path)
        for path, operations in paths.items()
        for method in operations
        if method in METHODS
    }


def task_count(session: Session) -> int:
    session.expire_all()
    return len(session.exec(select(Task)).all())


# --- the contract of release R1 --------------------------------------------


def test_the_api_exposes_exactly_the_r1_endpoints(client: TestClient) -> None:
    assert documented_endpoints(client) == R1_ENDPOINTS


def test_there_is_no_put_endpoint(client: TestClient) -> None:
    assert {m for m, _ in documented_endpoints(client)} == {
        "GET",
        "POST",
        "PATCH",
        "DELETE",
    }


def test_the_only_task_creating_endpoint_lives_inside_a_group(
    client: TestClient,
) -> None:
    creators = {
        path for method, path in documented_endpoints(client) if method == "POST"
    }

    assert creators == {f"{API}/task-groups", GROUP_TASKS}


def test_every_business_endpoint_is_under_the_api_prefix(client: TestClient) -> None:
    outside = {
        path
        for _, path in documented_endpoints(client)
        if not path.startswith(API) and path != "/health"
    }

    assert outside == set()


# --- no task without a group (RN02) ------------------------------------------


def test_no_endpoint_can_create_a_task_without_a_group(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session, name="Work")
    existing = create_task(session, group, title="Existing")
    unknown = uuid4()
    body = {"title": "Orphan"}

    attempts = {
        "POST /tasks (no such route)": client.post(f"{API}/tasks", json=body),
        "POST to an unknown group": client.post(
            GROUP_TASKS.format(group_id=unknown), json=body
        ),
        "POST with a group id in the body": client.post(
            GROUP_TASKS.format(group_id=group.id),
            json={**body, "task_group_id": str(unknown)},
        ),
        "POST with a null group id in the body": client.post(
            GROUP_TASKS.format(group_id=group.id),
            json={**body, "task_group_id": None},
        ),
        "POST of a group carrying tasks": client.post(
            f"{API}/task-groups",
            json={"name": "Sneaky", "tasks": [body]},
        ),
        "PUT on a task": client.put(f"{API}/tasks/{existing.id}", json=body),
        "PUT on the tasks of a group": client.put(
            GROUP_TASKS.format(group_id=group.id), json=body
        ),
        "PATCH moving a task to an unknown group": client.patch(
            f"{API}/tasks/{existing.id}", json={"task_group_id": str(unknown)}
        ),
    }

    statuses = {name: response.status_code for name, response in attempts.items()}
    assert statuses == {
        "POST /tasks (no such route)": 404,
        "POST to an unknown group": 404,
        "POST with a group id in the body": 422,
        "POST with a null group id in the body": 422,
        "POST of a group carrying tasks": 422,
        "PUT on a task": 405,
        "PUT on the tasks of a group": 405,
        "PATCH moving a task to an unknown group": 422,
    }
    assert task_count(session) == 1
    session.refresh(existing)
    assert existing.task_group_id == group.id


def test_refused_attempts_are_answered_in_problem_details(
    client: TestClient,
) -> None:
    unknown_group = client.post(
        GROUP_TASKS.format(group_id=uuid4()), json={"title": "x"}
    )
    invalid_group = client.post(f"{API}/task-groups", json={"name": ""})

    assert (unknown_group.status_code, invalid_group.status_code) == (404, 422)
    for response in (unknown_group, invalid_group):
        assert response.headers["content-type"] == "application/problem+json"


def test_every_task_in_the_api_belongs_to_an_existing_group(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session, name="Work")
    other = create_task_group(session, name="Other")
    for title in ("A", "B", "C"):
        client.post(GROUP_TASKS.format(group_id=group.id), json={"title": title})
    mover = client.post(GROUP_TASKS.format(group_id=group.id), json={"title": "D"})
    client.patch(
        f"{API}/tasks/{mover.json()['id']}", json={"task_group_id": str(other.id)}
    )

    session.expire_all()
    tasks = session.exec(select(Task)).all()
    group_ids = {task.task_group_id for task in tasks}
    assert len(tasks) == 4
    assert group_ids <= {group.id, other.id}
