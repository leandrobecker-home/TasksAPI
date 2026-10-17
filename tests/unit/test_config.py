"""Unit tests for the settings module (RT10)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings

ENV_VARS = ("DATABASE_URL", "LOG_LEVEL", "HOST", "PORT")


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove TASKS_* variables so the host environment never leaks into tests."""
    for name in ENV_VARS:
        monkeypatch.delenv(f"TASKS_{name}", raising=False)
    get_settings.cache_clear()


def make_settings(env_file: Path | None = None) -> Settings:
    """Build Settings ignoring any real ``.env`` unless a file is given."""
    return Settings(_env_file=env_file)


def test_defaults_when_nothing_is_set() -> None:
    settings = make_settings()

    assert settings.database_url == "sqlite:///./tasks.db"
    assert settings.log_level == "INFO"
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000


def test_environment_variables_override_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TASKS_DATABASE_URL", "sqlite:///./other.db")
    monkeypatch.setenv("TASKS_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("TASKS_HOST", "0.0.0.0")
    monkeypatch.setenv("TASKS_PORT", "9000")

    settings = make_settings()

    assert settings.database_url == "sqlite:///./other.db"
    assert settings.log_level == "DEBUG"
    assert settings.host == "0.0.0.0"
    assert settings.port == 9000


def test_values_are_read_from_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("TASKS_PORT=7000\nTASKS_LOG_LEVEL=WARNING\n", encoding="utf-8")

    settings = make_settings(env_file)

    assert settings.port == 7000
    assert settings.log_level == "WARNING"


def test_environment_variable_wins_over_env_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("TASKS_PORT=7000\n", encoding="utf-8")
    monkeypatch.setenv("TASKS_PORT", "7100")

    assert make_settings(env_file).port == 7100


def test_unknown_entries_in_env_file_are_ignored(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("UNRELATED=1\nTASKS_UNKNOWN=2\n", encoding="utf-8")

    assert make_settings(env_file).port == 8000


@pytest.mark.parametrize("value", ["info", "Info", "iNfO"])
def test_log_level_is_case_insensitive(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("TASKS_LOG_LEVEL", value)

    assert make_settings().log_level == "INFO"


@pytest.mark.parametrize("value", ["0", "-1", "65536", "abc", ""])
def test_invalid_port_fails_on_startup(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("TASKS_PORT", value)

    with pytest.raises(ValidationError) as error:
        make_settings()

    assert "port" in str(error.value)


@pytest.mark.parametrize("value", ["verbose", "TRACE", ""])
def test_invalid_log_level_fails_on_startup(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("TASKS_LOG_LEVEL", value)

    with pytest.raises(ValidationError) as error:
        make_settings()

    assert "log_level" in str(error.value)


def test_empty_database_url_fails_on_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TASKS_DATABASE_URL", "")

    with pytest.raises(ValidationError):
        make_settings()


def test_get_settings_builds_once_and_caches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TASKS_PORT", "8100")
    first = get_settings()

    monkeypatch.setenv("TASKS_PORT", "8200")

    assert get_settings() is first
    assert first.port == 8100
