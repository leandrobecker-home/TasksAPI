"""Integration tests for GET /api/v1/task-groups/{group_id}/tasks (RF07)."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import TaskPriority, TaskStatus
from tests.factories import create_task, create_task_group

GROUPS = "/api/v1/task-groups"
START = datetime(2026, 1, 1, tzinfo=UTC)


def url(group_id: Any) -> str:
    return f"{GROUPS}/{group_id}/tasks"


def titles(body: dict[str, Any]) -> list[str]:
    return [item["title"] for item in body["items"]]


def make_tasks(session: Session, group: Any, count: int) -> None:
    """Create ``count`` tasks, numbered 01.. in creation order."""
    for number in range(1, count + 1):
        create_task(
            session,
            group,
            title=f"Task {number:02d}",
            created_at=START + timedelta(minutes=number),
        )


# --- the listing format -----------------------------------------------------


def test_empty_group_has_an_empty_listing(client: TestClient, session: Session) -> None:
    group = create_task_group(session)

    response = client.get(url(group.id))

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"items": [], "page": 1, "page_size": 20, "total": 0}


def test_listing_has_exactly_the_documented_members(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session)
    create_task(session, group)

    body = client.get(url(group.id)).json()

    assert set(body) == {"items", "page", "page_size", "total"}
    assert set(body["items"][0]) == {
        "id",
        "task_group_id",
        "title",
        "description",
        "status",
        "priority",
        "due_date",
        "created_at",
        "updated_at",
        "completed_at",
    }


def test_items_carry_the_task_data(client: TestClient, session: Session) -> None:
    group = create_task_group(session)
    task = create_task(
        session,
        group,
        title="Report",
        description="quarterly",
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
    )

    item = client.get(url(group.id)).json()["items"][0]

    assert item["id"] == str(task.id)
    assert item["task_group_id"] == str(group.id)
    assert (item["title"], item["description"]) == ("Report", "quarterly")
    assert (item["status"], item["priority"]) == ("in_progress", "high")
    assert item["created_at"].endswith("Z")


# --- only the tasks of this group ------------------------------------------


def test_only_the_tasks_of_the_group_are_listed(
    client: TestClient, session: Session
) -> None:
    work = create_task_group(session, name="Work")
    home = create_task_group(session, name="Home")
    create_task(session, work, title="Report")
    create_task(session, work, title="Meeting")
    create_task(session, home, title="Laundry")

    body = client.get(url(work.id)).json()

    assert sorted(titles(body)) == ["Meeting", "Report"]
    assert body["total"] == 2
    assert {item["task_group_id"] for item in body["items"]} == {str(work.id)}


def test_a_group_with_no_tasks_is_not_filled_by_other_groups(
    client: TestClient, session: Session
) -> None:
    empty = create_task_group(session, name="Empty")
    busy = create_task_group(session, name="Busy")
    make_tasks(session, busy, 3)

    body = client.get(url(empty.id)).json()

    assert (body["items"], body["total"]) == ([], 0)


def test_a_task_created_through_the_api_is_listed(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session)
    created = client.post(url(group.id), json={"title": "New"}).json()

    body = client.get(url(group.id)).json()

    assert [item["id"] for item in body["items"]] == [created["id"]]


# --- unknown group -------------------------------------------------------


def test_unknown_group_is_404(client: TestClient) -> None:
    missing = uuid4()

    response = client.get(url(missing))

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Not Found",
        "status": 404,
        "detail": f"Task group {missing} not found.",
        "instance": url(missing),
    }


def test_group_id_that_is_not_a_uuid_is_422(client: TestClient) -> None:
    response = client.get(url("not-a-uuid"))

    assert response.status_code == 422
    assert response.json()["detail"].startswith("group_id: ")


# --- ordering ------------------------------------------------------------


def test_the_newest_tasks_come_first(client: TestClient, session: Session) -> None:
    group = create_task_group(session)
    make_tasks(session, group, 4)

    body = client.get(url(group.id)).json()

    assert titles(body) == ["Task 04", "Task 03", "Task 02", "Task 01"]


# --- pagination (same rules as RF02) -----------------------------------


def test_default_page_holds_twenty_items(client: TestClient, session: Session) -> None:
    group = create_task_group(session)
    make_tasks(session, group, 25)

    body = client.get(url(group.id)).json()

    assert (body["page"], body["page_size"], body["total"]) == (1, 20, 25)
    assert len(body["items"]) == 20
    assert titles(body)[0] == "Task 25"


def test_second_page_holds_the_rest(client: TestClient, session: Session) -> None:
    group = create_task_group(session)
    make_tasks(session, group, 25)

    body = client.get(url(group.id), params={"page": 2}).json()

    assert body["page"] == 2
    assert titles(body) == [f"Task {number:02d}" for number in range(5, 0, -1)]
    assert body["total"] == 25


def test_custom_page_size(client: TestClient, session: Session) -> None:
    group = create_task_group(session)
    make_tasks(session, group, 25)

    body = client.get(url(group.id), params={"page": 3, "page_size": 10}).json()

    assert body["page_size"] == 10
    assert len(body["items"]) == 5


def test_pages_do_not_overlap_and_cover_everything(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session)
    make_tasks(session, group, 25)

    collected: list[str] = []
    for page in (1, 2, 3):
        params = {"page": page, "page_size": 10}
        collected += titles(client.get(url(group.id), params=params).json())

    assert collected == [f"Task {number:02d}" for number in range(25, 0, -1)]


def test_a_page_beyond_the_end_is_empty_but_keeps_the_total(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session)
    make_tasks(session, group, 3)

    body = client.get(url(group.id), params={"page": 50}).json()

    assert body["items"] == []
    assert body["total"] == 3


def test_the_maximum_page_size_is_accepted(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session)
    make_tasks(session, group, 3)

    response = client.get(url(group.id), params={"page_size": 100})

    assert response.status_code == 200
    assert response.json()["page_size"] == 100


@pytest.mark.parametrize(
    "query",
    [
        "page_size=101",
        "page_size=0",
        "page_size=-1",
        "page_size=abc",
        "page=0",
        "page=-1",
        "page=abc",
    ],
)
def test_invalid_pagination_is_400(
    client: TestClient, session: Session, query: str
) -> None:
    group = create_task_group(session)

    response = client.get(f"{url(group.id)}?{query}")

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"


# --- documentation ---------------------------------------------------------


def test_the_endpoint_and_its_parameters_are_documented(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"][f"{GROUPS}/{{group_id}}/tasks"]["get"]
    parameters = {parameter["name"] for parameter in operation["parameters"]}

    assert parameters == {"group_id", "page", "page_size"}
    assert operation["summary"] == "List the tasks of a group"
    assert operation["tags"] == ["tasks"]
