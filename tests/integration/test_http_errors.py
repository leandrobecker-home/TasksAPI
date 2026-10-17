"""Contract tests for routing errors and unexpected failures (RT14).

Unknown routes are ``404``, wrong methods are ``405`` and unhandled exceptions
are ``500`` without internal details. All of them are Problem Details.
"""

import logging

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

PROBLEM_MEMBERS = {"type", "title", "status", "detail", "instance"}


@pytest.fixture
def client_with_failures(app: FastAPI) -> TestClient:
    """A client that returns 500 responses instead of re-raising server errors."""

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret database password is hunter2")

    @app.get("/forbidden")
    def forbidden() -> None:
        raise HTTPException(
            status_code=403, detail="Not allowed", headers={"X-Reason": "demo"}
        )

    @app.get("/odd-status")
    def odd_status() -> None:
        raise HTTPException(status_code=499, detail="client closed request")

    return TestClient(app, raise_server_exceptions=False)


def test_unknown_route_is_404_problem_details(
    client_with_failures: TestClient,
) -> None:
    response = client_with_failures.get("/does-not-exist")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Not Found",
        "status": 404,
        "detail": "No endpoint matches this path.",
        "instance": "/does-not-exist",
    }


def test_unknown_route_under_the_api_prefix_is_also_404(
    client_with_failures: TestClient,
) -> None:
    response = client_with_failures.get("/api/v1/nothing-here")

    assert response.status_code == 404
    assert set(response.json()) == PROBLEM_MEMBERS


def test_wrong_method_is_405_problem_details(
    client_with_failures: TestClient,
) -> None:
    response = client_with_failures.post("/health")

    assert response.status_code == 405
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Method Not Allowed",
        "status": 405,
        "detail": "Method POST is not allowed on this path.",
        "instance": "/health",
    }


def test_405_keeps_the_allow_header(client_with_failures: TestClient) -> None:
    response = client_with_failures.delete("/health")

    assert "GET" in response.headers["allow"]


def test_explicit_http_exception_is_rendered_as_problem_details(
    client_with_failures: TestClient,
) -> None:
    response = client_with_failures.get("/forbidden")

    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Forbidden"
    assert response.json()["detail"] == "Not allowed"
    assert response.headers["x-reason"] == "demo"


def test_status_without_a_standard_phrase_gets_a_generic_title(
    client_with_failures: TestClient,
) -> None:
    response = client_with_failures.get("/odd-status")

    assert response.status_code == 499
    assert response.json()["title"] == "Error"
    assert response.json()["detail"] == "client closed request"


def test_unhandled_exception_is_500_problem_details(
    client_with_failures: TestClient,
) -> None:
    response = client_with_failures.get("/boom")

    assert response.status_code == 500
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Internal Server Error",
        "status": 500,
        "detail": "An unexpected error occurred.",
        "instance": "/boom",
    }


def test_500_does_not_expose_internal_details(
    client_with_failures: TestClient,
) -> None:
    body = client_with_failures.get("/boom").text

    for leaked in ("hunter2", "RuntimeError", "Traceback", "boom", ".py"):
        assert leaked not in body.replace('"/boom"', "")


def test_500_logs_the_traceback_server_side(
    client_with_failures: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="app.error_handlers"):
        client_with_failures.get("/boom")

    record = caplog.records[0]
    assert record.exc_info is not None
    assert isinstance(record.exc_info[1], RuntimeError)
    assert "GET /boom" in record.getMessage()


def test_application_keeps_serving_after_a_500(
    client_with_failures: TestClient,
) -> None:
    client_with_failures.get("/boom")

    assert client_with_failures.get("/health").status_code == 200


def test_405_lists_every_method_the_path_supports(app: FastAPI) -> None:
    """FastAPI keeps one route per method; Allow must still list all of them."""

    @app.get("/things/{thing_id}")
    def read_thing(thing_id: str) -> dict[str, str]:
        return {"id": thing_id}

    @app.patch("/things/{thing_id}")
    def change_thing(thing_id: str) -> dict[str, str]:
        return {"id": thing_id}

    @app.delete("/things/{thing_id}")
    def remove_thing(thing_id: str) -> dict[str, str]:
        return {"id": thing_id}

    response = TestClient(app).post("/things/1")

    assert response.status_code == 405
    assert response.headers["allow"] == "DELETE, GET, PATCH"


def test_405_allow_is_limited_to_the_path_that_was_requested(app: FastAPI) -> None:
    @app.get("/only-get")
    def only_get() -> None:
        return None

    @app.post("/other-path")
    def other_path() -> None:
        return None

    response = TestClient(app).put("/only-get")

    assert response.headers["allow"] == "GET"


def test_404_has_no_allow_header(client_with_failures: TestClient) -> None:
    assert "allow" not in client_with_failures.get("/does-not-exist").headers
