"""Integration tests for GET /health (RF14)."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.db import create_db_engine
from app.main import create_app


def test_health_is_ok_when_the_database_answers(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_responds_with_json(client: TestClient) -> None:
    response = client.get("/health")

    assert response.headers["content-type"] == "application/json"


def test_health_is_served_without_the_api_prefix(client: TestClient) -> None:
    assert client.get("/api/v1/health").status_code == 404


def test_health_is_service_unavailable_when_the_database_is_down(
    tmp_path: Path,
) -> None:
    unreachable = tmp_path / "missing-directory" / "tasks.db"
    engine = create_db_engine(f"sqlite:///{unreachable}")
    settings = Settings(_env_file=None, database_url=f"sqlite:///{unreachable}")

    # No lifespan: the app is up while its database is unreachable, as when the
    # database fails after a successful start. At startup the app refuses to run.
    broken_client = TestClient(create_app(settings, engine))
    response = broken_client.get("/health")

    engine.dispose()
    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "error"}


def test_health_is_documented_in_the_openapi_schema(client: TestClient) -> None:
    operation = client.get("/openapi.json").json()["paths"]["/health"]["get"]

    assert set(operation["responses"]) >= {"200", "503"}
