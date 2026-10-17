"""Contract tests for request validation errors (RT14).

Invalid query parameters are ``400``; an invalid body or path parameter is
``422``; malformed JSON is ``400``. All of them are Problem Details.
"""

from typing import Annotated
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, Query
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field


class ItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, Field(min_length=1, max_length=200)]


@pytest.fixture
def validating_client(app: FastAPI) -> TestClient:
    @app.get("/items")
    def list_items(
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> dict[str, int]:
        return {"page": page, "page_size": page_size}

    @app.get("/items/{item_id}")
    def get_item(item_id: UUID) -> dict[str, str]:
        return {"id": str(item_id)}

    @app.post("/items")
    def create_item(item: ItemInput) -> dict[str, str]:
        return {"title": item.title}

    @app.put("/items/{item_id}")
    def replace_item(item_id: UUID, item: ItemInput) -> dict[str, str]:
        return {"id": str(item_id), "title": item.title}

    return TestClient(app)


def assert_problem(response_json: dict[str, object], status: int, title: str) -> None:
    assert set(response_json) == {"type", "title", "status", "detail", "instance"}
    assert response_json["type"] == "about:blank"
    assert response_json["status"] == status
    assert response_json["title"] == title


@pytest.mark.parametrize(
    "query",
    ["page=abc", "page=0", "page=-1", "page_size=0", "page_size=101", "page_size=x"],
)
def test_invalid_query_parameter_is_400(
    validating_client: TestClient, query: str
) -> None:
    response = validating_client.get(f"/items?{query}")

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    assert_problem(response.json(), 400, "Validation Error")


def test_query_error_detail_names_the_parameter(
    validating_client: TestClient,
) -> None:
    detail = validating_client.get("/items?page_size=101").json()["detail"]

    assert detail.startswith("page_size: ")


def test_valid_query_parameters_are_accepted(validating_client: TestClient) -> None:
    response = validating_client.get("/items?page=2&page_size=100")

    assert response.status_code == 200
    assert response.json() == {"page": 2, "page_size": 100}


def test_path_parameter_that_is_not_a_uuid_is_422(
    validating_client: TestClient,
) -> None:
    response = validating_client.get("/items/not-a-uuid")

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert_problem(response.json(), 422, "Validation Error")
    assert response.json()["detail"].startswith("item_id: ")
    assert response.json()["instance"] == "/items/not-a-uuid"


@pytest.mark.parametrize(
    "payload",
    [{}, {"title": ""}, {"title": "x" * 201}, {"title": 123}, {"title": None}],
)
def test_invalid_body_is_422(validating_client: TestClient, payload: object) -> None:
    response = validating_client.post("/items", json=payload)

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert_problem(response.json(), 422, "Validation Error")
    assert response.json()["detail"].startswith("title: ")


def test_unknown_body_field_is_422(validating_client: TestClient) -> None:
    response = validating_client.post("/items", json={"title": "ok", "other": 1})

    assert response.status_code == 422
    assert response.json()["detail"].startswith("other: ")


def test_missing_body_is_422(validating_client: TestClient) -> None:
    response = validating_client.post("/items")

    assert response.status_code == 422
    assert_problem(response.json(), 422, "Validation Error")


def test_body_that_is_not_an_object_is_422(validating_client: TestClient) -> None:
    response = validating_client.post("/items", json=["a", "list"])

    assert response.status_code == 422
    assert_problem(response.json(), 422, "Validation Error")


@pytest.mark.parametrize("raw", ['{"title": ', "not json", '{"title": "x",}'])
def test_malformed_json_is_400(validating_client: TestClient, raw: str) -> None:
    response = validating_client.post(
        "/items", content=raw, headers={"content-type": "application/json"}
    )

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    assert_problem(response.json(), 400, "Bad Request")
    assert response.json()["detail"] == "Malformed JSON in the request body."


def test_body_error_wins_over_query_error(validating_client: TestClient) -> None:
    """A request with both kinds of error is reported as a 422."""
    response = validating_client.put(f"/items/{uuid4()}?page=0", json={"title": ""})

    assert response.status_code == 422


def test_several_errors_are_reported_together(validating_client: TestClient) -> None:
    response = validating_client.put("/items/not-a-uuid", json={"title": ""})

    detail = response.json()["detail"]
    assert response.status_code == 422
    assert "item_id: " in detail
    assert "title: " in detail
    assert "; " in detail
