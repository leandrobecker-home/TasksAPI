"""Unit tests for the ``python -m app`` entry point."""

from collections.abc import Iterator
from unittest.mock import patch

import pytest

from app.__main__ import main
from app.config import get_settings


@pytest.fixture(autouse=True)
def fresh_settings() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_main_starts_uvicorn_with_the_configured_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TASKS_HOST", "0.0.0.0")
    monkeypatch.setenv("TASKS_PORT", "9001")
    monkeypatch.setenv("TASKS_LOG_LEVEL", "WARNING")

    with patch("app.__main__.uvicorn.run") as run:
        main()

    run.assert_called_once_with(
        "app.main:create_app",
        factory=True,
        host="0.0.0.0",
        port=9001,
        log_level="warning",
    )


def test_main_uses_the_default_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("HOST", "PORT", "LOG_LEVEL"):
        monkeypatch.delenv(f"TASKS_{name}", raising=False)

    with patch("app.__main__.uvicorn.run") as run:
        main()

    run.assert_called_once()
    assert run.call_args.kwargs["port"] == 8000
