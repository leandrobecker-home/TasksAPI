"""Integration tests for the application factory (RT02)."""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.config import Settings
from app.main import API_TITLE, create_app


@pytest.fixture
def settings() -> Settings:
    """Settings that ignore any real ``.env`` and use an in-memory database."""
    return Settings(_env_file=None, database_url="sqlite://")


def test_create_app_returns_a_titled_fastapi_application(settings: Settings) -> None:
    app = create_app(settings)

    assert isinstance(app, FastAPI)
    assert app.title == API_TITLE


def test_injected_settings_and_engine_are_used(
    settings: Settings, engine: Engine
) -> None:
    app = create_app(settings, engine)

    assert app.state.settings is settings
    assert app.state.engine is engine


def test_engine_is_built_from_the_settings_when_not_injected(
    settings: Settings,
) -> None:
    app = create_app(settings)

    assert isinstance(app.state.engine, Engine)
    assert app.state.engine.url.render_as_string() == "sqlite://"


def test_each_call_builds_an_independent_application(settings: Settings) -> None:
    assert create_app(settings) is not create_app(settings)


def test_engine_created_by_the_factory_is_disposed_on_shutdown(
    settings: Settings,
) -> None:
    app = create_app(settings)

    with patch.object(app.state.engine, "dispose") as dispose:
        with TestClient(app):
            dispose.assert_not_called()

        dispose.assert_called_once()


def test_injected_engine_is_not_disposed_on_shutdown(
    settings: Settings, engine: Engine
) -> None:
    app = create_app(settings, engine)

    with patch.object(engine, "dispose") as dispose, TestClient(app):
        pass

    dispose.assert_not_called()
