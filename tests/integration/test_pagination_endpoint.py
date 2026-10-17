"""Integration tests for the pagination dependency and listing format (RF02)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.routes.dependencies import PaginationDep
from app.schemas.common import Page, build_page

TOTAL_ITEMS = 45


class Item(BaseModel):
    number: int


@pytest.fixture
def listing_client(app: FastAPI) -> TestClient:
    """A client for a throwaway listing endpoint over 45 in-memory items."""
    everything = [Item(number=number) for number in range(1, TOTAL_ITEMS + 1)]

    @app.get("/numbers", response_model=Page[Item])
    def list_numbers(pagination: PaginationDep) -> Page[Item]:
        window = everything[pagination.offset : pagination.offset + pagination.limit]
        return build_page(window, pagination, total=len(everything))

    return TestClient(app)


def test_first_page_uses_the_defaults(listing_client: TestClient) -> None:
    body = listing_client.get("/numbers").json()

    assert set(body) == {"items", "page", "page_size", "total"}
    assert (body["page"], body["page_size"], body["total"]) == (1, 20, TOTAL_ITEMS)
    assert [item["number"] for item in body["items"]] == list(range(1, 21))


def test_last_page_holds_the_remaining_items(listing_client: TestClient) -> None:
    body = listing_client.get("/numbers?page=3").json()

    assert body["page"] == 3
    assert [item["number"] for item in body["items"]] == [41, 42, 43, 44, 45]
    assert body["total"] == TOTAL_ITEMS


def test_page_beyond_the_end_is_empty_but_keeps_the_total(
    listing_client: TestClient,
) -> None:
    body = listing_client.get("/numbers?page=99").json()

    assert body["items"] == []
    assert body["total"] == TOTAL_ITEMS


def test_custom_page_size(listing_client: TestClient) -> None:
    body = listing_client.get("/numbers?page=2&page_size=10").json()

    assert body["page_size"] == 10
    assert [item["number"] for item in body["items"]] == list(range(11, 21))


def test_maximum_page_size_is_accepted(listing_client: TestClient) -> None:
    response = listing_client.get("/numbers?page_size=100")

    assert response.status_code == 200
    assert len(response.json()["items"]) == TOTAL_ITEMS


@pytest.mark.parametrize(
    "query",
    ["page=0", "page=-1", "page=abc", "page_size=0", "page_size=101", "page_size=-5"],
)
def test_invalid_pagination_is_400(listing_client: TestClient, query: str) -> None:
    response = listing_client.get(f"/numbers?{query}")

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"


def test_pagination_parameters_are_documented(listing_client: TestClient) -> None:
    operation = listing_client.get("/openapi.json").json()["paths"]["/numbers"]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}

    assert parameters["page"]["schema"]["minimum"] == 1
    assert parameters["page_size"]["schema"]["minimum"] == 1
    assert parameters["page_size"]["schema"]["maximum"] == 100
    assert parameters["page_size"]["schema"]["default"] == 20
