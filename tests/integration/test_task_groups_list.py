"""Integration tests for GET /api/v1/task-groups (RF02)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from tests.factories import create_task_group

URL = "/api/v1/task-groups"


def names(body: dict[str, Any]) -> list[str]:
    return [item["name"] for item in body["items"]]


def make_groups(session: Session, count: int) -> None:
    for number in range(1, count + 1):
        create_task_group(session, name=f"Group {number:02d}")


# --- the listing format ---------------------------------------------------------------


def test_empty_listing(client: TestClient) -> None:
    response = client.get(URL)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"items": [], "page": 1, "page_size": 20, "total": 0}


def test_listing_has_exactly_the_documented_members(
    client: TestClient, session: Session
) -> None:
    create_task_group(session, name="Work", description="Job")

    body = client.get(URL).json()

    assert set(body) == {"items", "page", "page_size", "total"}
    assert set(body["items"][0]) == {
        "id",
        "name",
        "description",
        "created_at",
        "updated_at",
    }


def test_items_carry_the_group_data(client: TestClient, session: Session) -> None:
    group = create_task_group(session, name="Work", description="Job")

    item = client.get(URL).json()["items"][0]

    assert item["id"] == str(group.id)
    assert (item["name"], item["description"]) == ("Work", "Job")
    assert item["created_at"].endswith("Z")


# --- pagination -----------------------------------------------------------------------


def test_default_page_holds_twenty_items(client: TestClient, session: Session) -> None:
    make_groups(session, 25)

    body = client.get(URL).json()

    assert (body["page"], body["page_size"], body["total"]) == (1, 20, 25)
    assert len(body["items"]) == 20
    assert names(body)[0] == "Group 01"


def test_second_page_holds_the_rest(client: TestClient, session: Session) -> None:
    make_groups(session, 25)

    body = client.get(f"{URL}?page=2").json()

    assert body["page"] == 2
    assert names(body) == [f"Group {number}" for number in range(21, 26)]
    assert body["total"] == 25


def test_custom_page_size(client: TestClient, session: Session) -> None:
    make_groups(session, 25)

    body = client.get(f"{URL}?page=3&page_size=10").json()

    assert body["page_size"] == 10
    assert names(body) == [f"Group {number}" for number in range(21, 26)]


def test_pages_do_not_overlap_and_cover_everything(
    client: TestClient, session: Session
) -> None:
    make_groups(session, 25)

    collected: list[str] = []
    for page in (1, 2, 3):
        collected += names(client.get(f"{URL}?page={page}&page_size=10").json())

    assert collected == [f"Group {number:02d}" for number in range(1, 26)]


def test_a_page_beyond_the_end_is_empty_but_keeps_the_total(
    client: TestClient, session: Session
) -> None:
    make_groups(session, 3)

    body = client.get(f"{URL}?page=50").json()

    assert body["items"] == []
    assert body["total"] == 3


def test_the_maximum_page_size_is_accepted(
    client: TestClient, session: Session
) -> None:
    make_groups(session, 3)

    response = client.get(f"{URL}?page_size=100")

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
def test_invalid_pagination_is_400(client: TestClient, query: str) -> None:
    response = client.get(f"{URL}?{query}")

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["instance"] == URL


# --- ordering -------------------------------------------------------------------------


def test_groups_are_ordered_by_name_ignoring_case(
    client: TestClient, session: Session
) -> None:
    for name in ["banana", "Cherry", "apple", "Banana split"]:
        create_task_group(session, name=name)

    assert names(client.get(URL).json()) == [
        "apple",
        "banana",
        "Banana split",
        "Cherry",
    ]


# --- search (q) -----------------------------------------------------------------------


@pytest.mark.parametrize("q", ["work", "WORK", "Work", "  work  ", "ork", "home"])
def test_search_ignores_case_and_surrounding_spaces(
    client: TestClient, session: Session, q: str
) -> None:
    create_task_group(session, name="Homework")
    create_task_group(session, name="Leisure")

    body = client.get(URL, params={"q": q}).json()

    assert names(body) == ["Homework"]
    assert body["total"] == 1


def test_search_ignores_the_case_of_accented_letters(
    client: TestClient, session: Session
) -> None:
    create_task_group(session, name="Ação rápida")
    create_task_group(session, name="Other")

    assert names(client.get(URL, params={"q": "AÇÃO"}).json()) == ["Ação rápida"]


def test_search_without_matches_returns_an_empty_page(
    client: TestClient, session: Session
) -> None:
    create_task_group(session, name="Work")

    body = client.get(URL, params={"q": "zzz"}).json()

    assert (body["items"], body["total"]) == ([], 0)


@pytest.mark.parametrize("q", ["", "   "])
def test_blank_search_returns_everything(
    client: TestClient, session: Session, q: str
) -> None:
    make_groups(session, 3)

    assert client.get(URL, params={"q": q}).json()["total"] == 3


def test_search_total_counts_only_the_matches_across_pages(
    client: TestClient, session: Session
) -> None:
    for number in range(1, 6):
        create_task_group(session, name=f"Match {number}")
    create_task_group(session, name="Unrelated")

    body = client.get(URL, params={"q": "match", "page_size": 2}).json()

    assert (len(body["items"]), body["total"]) == (2, 5)


@pytest.mark.parametrize(("q", "expected"), [("%", "100% done"), ("_", "snake_case")])
def test_search_treats_wildcards_as_plain_text(
    client: TestClient, session: Session, q: str, expected: str
) -> None:
    create_task_group(session, name="Plain")
    create_task_group(session, name="100% done")
    create_task_group(session, name="snake_case")

    assert names(client.get(URL, params={"q": q}).json()) == [expected]


# --- documentation --------------------------------------------------------------------


def test_the_endpoint_and_its_parameters_are_documented(client: TestClient) -> None:
    operation = client.get("/openapi.json").json()["paths"][URL]["get"]
    parameters = {parameter["name"] for parameter in operation["parameters"]}

    assert parameters == {"q", "page", "page_size"}
    assert operation["tags"] == ["task-groups"]
    assert operation["summary"] == "List task groups"
