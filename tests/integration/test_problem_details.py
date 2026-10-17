"""Contract tests for domain errors rendered as Problem Details (RT14, RT05)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.errors import ConflictError, DomainError, InvalidReferenceError, NotFoundError

PROBLEM_MEMBERS = {"type", "title", "status", "detail", "instance"}


@pytest.fixture
def failing_app(app: FastAPI) -> FastAPI:
    """The test application plus one route per domain error."""

    @app.get("/fail/not-found")
    def not_found() -> None:
        raise NotFoundError("Task group not found")

    @app.get("/fail/conflict")
    def conflict() -> None:
        raise ConflictError("A task group with this name already exists")

    @app.get("/fail/invalid-reference")
    def invalid_reference() -> None:
        raise InvalidReferenceError("task_group_id: the group does not exist")

    @app.get("/fail/accents")
    def accents() -> None:
        raise NotFoundError("Grupo não encontrado: ação inválida")

    return app


@pytest.fixture
def failing_client(failing_app: FastAPI) -> TestClient:
    return TestClient(failing_app)


@pytest.mark.parametrize(
    ("path", "status_code", "title", "detail"),
    [
        ("/fail/not-found", 404, "Not Found", "Task group not found"),
        (
            "/fail/conflict",
            409,
            "Conflict",
            "A task group with this name already exists",
        ),
        (
            "/fail/invalid-reference",
            422,
            "Validation Error",
            "task_group_id: the group does not exist",
        ),
    ],
)
def test_domain_error_is_rendered_as_problem_details(
    failing_client: TestClient,
    path: str,
    status_code: int,
    title: str,
    detail: str,
) -> None:
    response = failing_client.get(path)

    assert response.status_code == status_code
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": path,
    }


def test_problem_details_have_exactly_the_five_rfc_members(
    failing_client: TestClient,
) -> None:
    body = failing_client.get("/fail/conflict").json()

    assert set(body) == PROBLEM_MEMBERS


def test_instance_is_the_path_without_the_query_string(
    failing_client: TestClient,
) -> None:
    body = failing_client.get("/fail/not-found?secret=123").json()

    assert body["instance"] == "/fail/not-found"


def test_problem_details_are_utf_8_encoded(failing_client: TestClient) -> None:
    response = failing_client.get("/fail/accents")

    assert "Grupo não encontrado: ação inválida" in response.content.decode("utf-8")
    assert response.json()["detail"] == "Grupo não encontrado: ação inválida"


def test_unmapped_domain_error_falls_back_to_its_own_status(
    app: FastAPI,
) -> None:
    class TeapotError(DomainError):
        status_code = 418
        title = "I'm a teapot"

    @app.get("/fail/teapot")
    def teapot() -> None:
        raise TeapotError("short and stout")

    response = TestClient(app).get("/fail/teapot")

    assert response.status_code == 418
    assert response.json()["title"] == "I'm a teapot"
